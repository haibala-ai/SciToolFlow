"""File-transported native actor using the production ReAct loop, without model APIs.

The actor receives only its public request directory and the broker command. The
broker accepts one bounded decision per pending request; scientific execution is
still routed through registered workers. Isolation is a public-data/tool boundary,
not a claim that the Codex process has a separate OS account.
"""

import argparse
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scitoolflow.io import atomic_json


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--task", required=True)
    p.add_argument("--directory", type=Path, required=True)
    a = p.parse_args()
    directory = a.directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    actor = directory / "actor"
    actor.mkdir(exist_ok=True)
    task = next(
        json.loads(l)
        for l in (ROOT / "tasks/questions.jsonl").read_text().splitlines()
        if json.loads(l)["id"] == a.task
    )
    from scitoolflow.benchmark.assets import load_agent_input

    task = load_agent_input(task, ROOT / "tasks")
    atomic_json(actor / "public_task.json", task)
    broker = """import json,pathlib,sys,time
p=pathlib.Path(__file__).resolve().parent
req=json.loads((p/'request.json').read_text())
if len(sys.argv)==1:
 print(json.dumps(req,ensure_ascii=False));sys.exit()
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
else:print('Decision accepted; next request not ready. Invoke broker without input to poll.')
"""
    (actor / "broker.py").write_text(broker)
    from tools.catalog import ToolCatalog
    from tools.executor import execute
    from baselines.react.runtime import run_react
    from scitoolflow.paths import load_environment

    load_environment()
    os.environ["SCITOOLFLOW_WORK_DIR"] = str(directory / "work")
    os.environ["SCITOOLFLOW_ARTIFACTS_DIR"] = str(directory / "artifacts")
    catalog = ToolCatalog(ROOT)

    class Client:
        backend = "native_subagent"
        model = "codex-native-clean-actor"
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
            deadline = time.monotonic() + min(600, kwargs.get("timeout", 600))
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
        invoke=lambda n, args, **kw: execute(n, args, catalog=catalog, **kw),
        trace_dir=directory / "trajectories",
        case_id=a.task,
        inputs=task["inputs"],
        files=task["files"],
        answer_schema=task["answer_schema"],
        max_calls=task["max_tool_calls"],
        task_timeout=1800,
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
