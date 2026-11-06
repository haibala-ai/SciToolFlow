"""File-transported native actor using the production ReAct loop, without model APIs.

The actor receives only its public request directory and the broker command. The
broker accepts one bounded decision per pending request; scientific execution is
still routed through registered workers. Isolation is a public-data/tool boundary,
not a claim that the Codex process has a separate OS account.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.utils.io import atomic_json


FORBIDDEN_GENERATION_HELPERS = {"CodeInterpreterTools", "PaperQA"}


def invoke_native_tool(name, arguments, *, catalog, execute_tool, **kwargs):
    """Keep reference authorship API-free even if an actor selects an LLM helper.

    Ordinary scientific models and source APIs are tools; these two helpers ask
    an additional language model to reason or generate code/answers instead.
    This restriction applies to native reference generation only.
    """
    canonical = catalog.canonical(name)
    if canonical in FORBIDDEN_GENERATION_HELPERS:
        return {
            "tool": canonical,
            "status": "blocked",
            "output": None,
            "error_type": "ReferenceGenerationHelperDisabled",
            "error": (
                "Native references may not delegate reasoning to another LLM. "
                "Use registered scientific computations or stop if unavailable."
            ),
        }
    return execute_tool(name, arguments, catalog=catalog, **kwargs)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--task", required=True)
    p.add_argument("--dataset", choices=["full", "mini"], default="full")
    p.add_argument("--actor-model", default="gpt-6.1-terra")
    p.add_argument("--directory", type=Path, required=True)
    p.add_argument(
        "--task-source",
        type=Path,
        default=ROOT / "tasks/full/questions.jsonl",
        help="Public candidate task JSONL; never a reference/answer file",
    )
    p.add_argument(
        "--task-root",
        type=Path,
        default=ROOT / "tasks/full",
        help="Public asset directory for this candidate release",
    )
    p.add_argument("--task-timeout", type=float, default=7200)
    p.add_argument("--actor-turn-timeout", type=float, default=600)
    a = p.parse_args()
    directory = a.directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    actor = directory / "actor"
    actor.mkdir(exist_ok=True)
    if (directory / "candidate.json").exists() or (actor / "request.json").exists():
        raise ValueError("Native reference directory already contains a run")
    task = next(
        json.loads(l)
        for l in a.task_source.read_text().splitlines()
        if l.strip() and json.loads(l)["id"] == a.task
    )
    allowed = {
        "id",
        "domain",
        "question",
        "question_language",
        "inputs",
        "files",
        "answer_schema",
        "unit_annotations",
        "Parameter",
    }
    if set(task) - allowed:
        raise ValueError("Native actor source contains nonpublic task fields")
    from evaluation.integrity.traces import canonical_sha256

    raw_task_sha256 = canonical_sha256(task)
    from tasks.assets import load_agent_input

    task = load_agent_input(task, a.task_root)
    atomic_json(actor / "public_task.json", task)
    broker = """import json,pathlib,sys,time
if sys.argv[1:] in (['--help'],['-h']):
 print('Read public task and observations: python broker.py (or python broker.py poll). Submit one ReAct JSON decision: python broker.py submit < decision.json.');sys.exit()
p=pathlib.Path(__file__).resolve().parent
req=json.loads((p/'request.json').read_text())
if len(sys.argv)==1 or sys.argv[1:]==['poll']:
 print(json.dumps(req,ensure_ascii=False));sys.exit()
if sys.argv[1:]!=['submit']:raise ValueError('Use broker.py to poll or broker.py submit with one JSON decision on stdin')
x=json.load(sys.stdin)
text=json.dumps(x,ensure_ascii=False,allow_nan=False)
if len(text)>40000:raise ValueError('Decision exceeds bounded transport')
reply=p/('reply_'+str(req['turn'])+'.json')
if reply.exists():raise ValueError('One decision per request')
tmp=reply.with_suffix('.tmp');tmp.write_text(text);tmp.replace(reply)
for _ in range(1200):
 time.sleep(.1)
 if (p/'finished.json').exists():print((p/'finished.json').read_text());break
 now=json.loads((p/'request.json').read_text())
 if now['turn']!=req['turn']:print(json.dumps(now,ensure_ascii=False));break
else:print('Decision accepted; next request not ready. Invoke broker.py without arguments to poll.')
"""
    (actor / "broker.py").write_text(broker)
    atomic_json(
        actor / "transport.json",
        {
            "read_request": "python broker.py",
            "submit_decision": "python broker.py submit < decision.json",
            "model_api_used": False,
            "forbidden_generation_helpers": sorted(FORBIDDEN_GENERATION_HELPERS),
            "allowed_actor_access": ["public_task.json", "request.json", "broker.py"],
            "isolation_boundary": "Public-data and tool-broker boundary, not a separate OS account",
        },
    )
    from tools.catalog import ToolCatalog
    from tools import execute
    from baselines.react.runtime import run_react
    from src.utils.paths import load_environment

    load_environment()
    os.environ["SCITOOLFLOW_WORK_DIR"] = str(directory / "work")
    os.environ["SCITOOLFLOW_ARTIFACTS_DIR"] = str(directory / "artifacts")
    # Match the production runner's per-task directories. File-based scientific
    # tools deliberately reject a nonexistent or shared artifact read root.
    (directory / "work").mkdir(exist_ok=True)
    (directory / "artifacts").mkdir(exist_ok=True)
    catalog = ToolCatalog(ROOT)
    # Parent-only provenance, outside the actor's allowed request directory.
    # Record source bytes before execution; no credentials or hidden tasks.
    source_paths = {
        ROOT / "scripts/references/native_reference_session.py",
        ROOT / "tools/catalog/catalog.json",
        ROOT / "cli.py",
    }
    for folder in ["baselines", "tools/runtime", "tasks", "src"]:
        source_paths.update((ROOT / folder).rglob("*.py"))
    source_paths.update(
        ROOT / spec["source"]["file"] for spec in catalog.tools.values()
    )
    atomic_json(
        directory / "generation_manifest.json",
        {
            "actor_backend": "native_subagent",
            "model": a.actor_model,
            "dataset": a.dataset,
            "model_api_used": False,
            "forbidden_generation_helpers": sorted(FORBIDDEN_GENERATION_HELPERS),
            "task_id": a.task,
            "public_task_sha256": raw_task_sha256,
            "source_sha256": {
                str(path.relative_to(ROOT)): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in sorted(source_paths)
            },
            "input_asset_sha256": {
                str(path): hashlib.sha256(Path(path).read_bytes()).hexdigest()
                for path in task["files"]
            },
            "isolation_boundary": "Public task context and tool broker; not a separate OS account",
        },
    )

    class Client:
        backend = "native_subagent"
        model = a.actor_model
        supports_response_schema = False

        def __init__(self):
            self.turn = 0

        def request(self, messages, **kwargs):
            self.turn += 1
            atomic_json(
                actor / "request.json",
                {
                    "turn": self.turn,
                    "max_output_tokens": kwargs["max_tokens"],
                    "messages": messages,
                    "model_api_used": False,
                },
            )
            reply = actor / ("reply_" + str(self.turn) + ".json")
            deadline = time.monotonic() + a.actor_turn_timeout
            while not reply.exists():
                if time.monotonic() > deadline:
                    raise TimeoutError("Native actor response deadline")
                time.sleep(0.1)
            text = reply.read_text()
            return {"text": text, "truncated": False, "usage": None}

    result = run_react(
        task["question"],
        catalog=catalog,
        client=Client(),
        invoke=lambda n, args, **kw: invoke_native_tool(
            n, args, catalog=catalog, execute_tool=execute, **kw
        ),
        trace_dir=directory / "trajectories",
        case_id=a.task,
        dataset=a.dataset,
        inputs=task["inputs"],
        files=task["files"],
        answer_schema=task["answer_schema"],
        task_timeout=a.task_timeout,
        protocol_schema_guard=False,
    )
    atomic_json(directory / "candidate.json", result)
    atomic_json(
        actor / "finished.json",
        {
            "status": result["status"],
            "failure_reason": result["failure_reason"],
            "candidate_stored_for_parent_review": True,
        },
    )


if __name__ == "__main__":
    main()
