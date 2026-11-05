"""Public-task-only baseline runner with atomic, compatible checkpoints."""

from datetime import datetime
import hashlib
import json
import os
import time
from pathlib import Path
from uuid import uuid4

from baselines.common.batch import iter_tasks
from baselines.common.metrics import task_metrics

from src.utils.paths import project_root, load_environment
from tools.catalog import ToolCatalog
from tools import execute
from tasks.assets import load_agent_input
from tasks.datasets import dataset_files, load_dataset, select_tasks
from src.models.client import GenerationClient
from baselines.react.runtime import run_react
from baselines.react.trajectory import atomic_json
from evaluation.integrity.traces import canonical_sha256


def resume_rows(checkpoint, fingerprint, retry=False):
    if checkpoint.get("fingerprint") != fingerprint:
        raise ValueError(
            "Actor inputs, runtime, tools or settings changed; choose a new output"
        )
    rows = checkpoint.get("predictions", [])
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate checkpoint IDs")
    return [r for r in rows if not (retry and not r.get("completed"))]


def actor_file_hashes(root, dataset="full"):
    """Bind resume to public inputs and all executable actor/tool dependencies."""
    files = [
        root / "cli.py",
        root / "tools/catalog/catalog.json",
        root / "tools/graph/graph_store.json",
        root / "tools/graph/index_store.json",
        root / "tools/graph/tool_foundation_manifest.json",
        root / "configs/environments/routing.json",
        root / "baselines/react/config.json",
        root / "baselines/react/system_prompt.md",
    ]
    files.extend(root / name for name in dataset_files(dataset))
    for directory in ["baselines", "tools", "src"]:
        files.extend((root / directory).rglob("*.py"))
    # Only public dataset loaders execute in this harness. Authoring scripts,
    # private graders and source-suite tests are not actor dependencies.
    files.extend((root / "tasks").glob("*.py"))
    for directory in ["react", "scitoolagent"]:
        files.extend(
            [
                root / "baselines" / directory / "system_prompt.md",
                root / "baselines" / directory / "config.json",
            ]
        )
    files.extend((root / "baselines/scimas/prompts").glob("*.md"))
    files.append(root / "baselines/scimas/config.json")
    files.extend(
        root / "tools/graph/scimas" / name
        for name in [
            "graph.json",
            "manifest.json",
            "annotations.json",
            "embeddings.json.gz",
        ]
    )
    return {
        str(file.relative_to(root)): hashlib.sha256(file.read_bytes()).hexdigest()
        for file in sorted(set(files))
    }


def run_task(payload):
    """One process, model client and writable namespace per task."""
    from argparse import Namespace

    row, options, output_name, namespace = payload
    args = Namespace(**options)
    root = project_root()
    output = Path(output_name)
    task_id = row["id"]
    os.environ["SCITOOLFLOW_WORK_DIR"] = str(
        root / ".local/work/batches" / namespace / task_id / "tools"
    )
    os.environ["SCITOOLFLOW_ARTIFACTS_DIR"] = str(
        output.parent / "tool_artifacts" / task_id / namespace
    )
    Path(os.environ["SCITOOLFLOW_WORK_DIR"]).mkdir(parents=True, exist_ok=True)
    Path(os.environ["SCITOOLFLOW_ARTIFACTS_DIR"]).mkdir(parents=True, exist_ok=True)
    load_environment()
    catalog = ToolCatalog(root)
    baseline = getattr(args, "baseline", "react")
    runtime = run_react
    if baseline == "scitoolagent":
        from baselines.scitoolagent.runtime import run_scitoolagent

        runtime = run_scitoolagent
    elif baseline == "scimas":
        from baselines.scimas.runtime import run_scimas

        runtime = run_scimas
    client = GenerationClient(args.backend)
    if args.model:
        client.model = args.model
    try:
        asset_root = root / (
            "tasks/mini" if getattr(args, "dataset", "full") == "mini" else "tasks/full"
        )
        task = load_agent_input(row, asset_root)
        budget = args.max_calls
        print(
            "[run] "
            + task["id"]
            + " scientific_limit="
            + (str(budget) if budget is not None else "unlimited")
            + " model_requests="
            + str(getattr(args, "max_model_requests", 400)),
            flush=True,
        )
        started = time.monotonic()
        try:
            from baselines.scimas.assets import public_asset_scope

            with public_asset_scope(asset_root):
                result = runtime(
                    task["question"],
                    catalog=catalog,
                    client=client,
                    invoke=lambda n, a, **kwargs: execute(
                        n, a, catalog=catalog, **kwargs
                    ),
                    trace_dir=output.parent / "trajectories",
                    case_id=task["id"],
                    dataset=getattr(args, "dataset", "full"),
                    inputs=task["inputs"],
                    files=task["files"],
                    answer_schema=task["answer_schema"],
                    max_iterations=args.max_steps,
                    max_model_requests=getattr(args, "max_model_requests", 400),
                    max_calls=budget,
                    max_actions=args.max_actions,
                    max_protocol_errors=args.max_protocol_errors,
                    max_failures_per_action=args.max_failures_per_action,
                    max_identical_tool_steps=args.max_identical_tool_steps,
                    answer_schema_guard=args.answer_schema_guard,
                    protocol_schema_guard=getattr(args, "protocol_schema_guard", True),
                    max_discovery_calls=args.max_discovery_calls,
                    max_reasoning_turns=args.max_think_steps,
                    max_consecutive_thinks=args.max_consecutive_thinks,
                    max_context_chars=args.max_context_chars,
                    max_output_tokens=args.max_output_tokens,
                    task_timeout=args.task_timeout,
                    tool_timeout=args.tool_timeout,
                )
            calls = result["calls"]
            prediction = {
                "id": task["id"],
                "public_task_sha256": canonical_sha256(row),
                "dataset": getattr(args, "dataset", "full"),
                "baseline": baseline,
                "completed": result["status"] == "completed",
                "status": result["status"],
                "tool_path": [c["tool"] for c in calls if c["tool"] != "DescribeTools"],
                "calls": calls,
                "final_answer": result["final_answer"],
                "failure_reason": result["failure_reason"],
                "trace_path": result["trace_path"],
                "trace_sha256": hashlib.sha256(
                    Path(result["trace_path"]).read_bytes()
                ).hexdigest(),
                "stats": result["stats"],
                "duration_seconds": result["duration_seconds"],
                "resource_usage": result["resource_usage"],
                "embedding_usage": result.get("embedding_usage"),
                "metrics": result.get("metrics")
                or task_metrics(
                    result["resource_usage"],
                    calls,
                    runtime_seconds=result["duration_seconds"],
                    finished=True,
                ),
            }
        except Exception as error:
            prediction = {
                "id": task["id"],
                "dataset": getattr(args, "dataset", "full"),
                "baseline": baseline,
                "completed": False,
                "status": "failed",
                "tool_path": [],
                "calls": [],
                "final_answer": None,
                "failure_reason": type(error).__name__ + ": " + str(error)[:1000],
                "metrics": task_metrics(
                    None, None, runtime_seconds=time.monotonic() - started
                ),
            }
        return prediction
    finally:
        client.close()


def run_batch(args):
    root = project_root()
    load_environment()
    from tools.runtime.scope import tool_allowed

    # Reject an invalid execution-scope setting before spending model requests.
    tool_allowed("DescribeTools")
    os.environ["SCITOOL_MAX_INPUT_TOKENS"] = str(args.max_input_tokens)
    os.environ["SCITOOLFLOW_ENABLE_MODEL_THINKING"] = (
        "1" if args.enable_model_thinking else "0"
    )
    dataset = load_dataset(getattr(args, "dataset", "full"), root)
    selected = dataset.select(args.tasks)
    baseline = getattr(args, "baseline", "react")
    concurrency = getattr(args, "concurrency", 1)
    if concurrency < 1 or (args.backend == "local" and concurrency > 1):
        raise ValueError(
            "Concurrent tasks require an API/vLLM backend and a positive concurrency"
        )
    client = GenerationClient(args.backend)
    if args.model:
        client.model = args.model
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if client.backend == "api" and not client.model:
        raise ValueError("Configure --model or SCITOOLFLOW_API_MODEL for the API actor")
    provider = client.public_settings()
    output = (
        Path(args.output)
        if args.output
        else root
        / "results"
        / (baseline + "_" + dataset.name + "_" + timestamp)
        / "predictions.json"
    )
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    settings = {
        k: v
        for k, v in vars(args).items()
        if k not in {"output", "resume", "retry_failed", "func", "command"}
    }
    settings.update(
        model=client.model,
        backend=client.backend,
        dataset=dataset.name,
        actor_file_hashes=actor_file_hashes(root, dataset.name),
        sampling=provider.get(
            "sampling",
            (
                {
                    k: os.getenv("SCITOOLFLOW_VLLM_" + k)
                    for k in [
                        "TEMPERATURE",
                        "TOP_P",
                        "TOP_K",
                        "REPETITION_PENALTY",
                        "JSON_MODE",
                    ]
                }
                if client.backend == "vllm"
                else {"decoding": "greedy_or_same_weight_resident_service"}
            ),
        ),
        provider=provider,
        endpoint=provider["endpoint"],
        resource_policy={
            "version": "task-resources.v1",
            "max_model_requests": getattr(args, "max_model_requests", 400),
            "task_seconds": args.task_timeout,
            "scientific_calls": args.max_calls,
            "decisions": args.max_steps,
            "discovery_calls": args.max_discovery_calls,
            "think_steps": args.max_think_steps,
            "consecutive_thinks": args.max_consecutive_thinks,
        },
        execution_scope=os.getenv("SCITOOL_TOOL_SCOPE", "all"),
        task_isolation="independent_process_and_writable_directories",
    )
    fingerprint = hashlib.sha256(
        json.dumps(settings, sort_keys=True).encode()
    ).hexdigest()
    predictions = []
    if output.exists():
        if not args.resume:
            raise ValueError("Output exists; use --resume or another output")
        predictions = resume_rows(
            json.loads(output.read_text()), fingerprint, args.retry_failed
        )
    completed_ids = {r["id"] for r in predictions}

    def save():
        atomic_json(
            output,
            {
                "schema_version": "scitoolflow.predictions.v1",
                "fingerprint": fingerprint,
                "settings": settings,
                "predictions": predictions,
            },
        )
        # A compact table for analysis, bound to the same attempt/checkpoint.
        # Rebuild on resume so an explicit failed-task retry replaces its row.
        atomic_json(
            output.parent / "task_metrics.json",
            {
                "schema_version": "scitoolflow.task_metrics.v1",
                "fingerprint": fingerprint,
                "dataset": dataset.name,
                "baseline": baseline,
                "tasks": [
                    {
                        "id": row["id"],
                        "status": row["status"],
                        "completed": row.get("completed", False),
                        "trace_path": row.get("trace_path"),
                        **row["metrics"],
                    }
                    for row in predictions
                ],
            },
        )

    # The parent is the sole checkpoint writer; actor processes never see private references.
    namespace = output.parent.name + "-" + uuid4().hex[:12]
    options = {k: v for k, v in vars(args).items() if k not in {"func", "command"}}
    options["dataset"] = dataset.name
    jobs = [
        (row["id"], (row, options, str(output), namespace))
        for row in selected
        if row["id"] not in completed_ids
    ]
    task_order = {row["id"]: i for i, row in enumerate(selected)}
    active_ids = []
    status = "running"

    def progress(active=None):
        nonlocal active_ids
        if active is not None:
            active_ids = active
        atomic_json(
            output.parent / "progress.json",
            {
                "status": status,
                "dataset": dataset.name,
                "updated_at": datetime.now().astimezone().isoformat(),
                "concurrency": concurrency,
                "selected_tasks": len(selected),
                "recorded_predictions": len(predictions),
                "completed_tasks": sum(bool(p.get("completed")) for p in predictions),
                "active_tasks": active_ids,
            },
        )

    save()
    progress()
    # The metadata-only client owns no requests, and is not passed to workers.
    client.close()
    scheduled = iter_tasks(jobs, run_task, concurrency, progress)
    try:
        for task_id, response in scheduled:
            prediction = (
                response.get("result")
                if response["ok"]
                else {
                    "id": task_id,
                    "dataset": dataset.name,
                    "baseline": baseline,
                    "completed": False,
                    "status": "failed",
                    "tool_path": [],
                    "calls": [],
                    "final_answer": None,
                    "failure_reason": response["error"],
                    "metrics": task_metrics(None, None),
                }
            )
            predictions.append(prediction)
            predictions.sort(key=lambda p: task_order[p["id"]])
            save()
            progress()
            print(
                f"[done] {task_id} status={prediction['status']} recorded={len(predictions)}/{len(selected)}",
                flush=True,
            )
        status = "finished"
    except KeyboardInterrupt:
        status = "interrupted"
        raise
    except BaseException:
        status = "failed"
        raise
    finally:
        scheduled.close()
        progress([])
    print(
        json.dumps(
            {
                "output": str(output),
                "predictions": len(predictions),
                "completed": sum(p["completed"] for p in predictions),
            },
            ensure_ascii=False,
        )
    )
    return output
