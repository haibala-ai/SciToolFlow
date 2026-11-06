"""Public-task-only baseline runner with atomic, compatible checkpoints."""

from datetime import datetime, timezone
import hashlib
import json
import os
import time
from pathlib import Path
from uuid import uuid4

from baselines.common.batch import iter_tasks
from baselines.common.metrics import task_metrics
from baselines.common.monitor import start_monitor
from src.models.communication import CommunicationCircuit, infrastructure_failure

from src.utils.paths import project_root, load_environment
from tools.catalog import ToolCatalog
from tools import execute
from tasks.assets import load_agent_input
from tasks.datasets import dataset_files, load_dataset, select_tasks
from src.models.client import GenerationClient
from baselines.react.runtime import run_react
from baselines.react.trajectory import atomic_json
from evaluation.integrity.traces import canonical_sha256
from baselines.scimas.ablation.policy import resolve_ablation, runtime_options
from src.models.embedding_profiles import embedding_backend, graph_root


def resume_rows(checkpoint, fingerprint, retry=False, retry_infrastructure=False):
    if checkpoint.get("fingerprint") != fingerprint:
        raise ValueError(
            "Actor inputs, runtime, tools or settings changed; choose a new output"
        )
    rows = checkpoint.get("predictions", [])
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate checkpoint IDs")
    return [r for r in rows if not (
        not r.get("completed") and (retry or (
            retry_infrastructure and r.get("infrastructure_failure")
        ))
    )]


def actor_file_hashes(root, dataset="full"):
    """Bind resume to public inputs and all executable actor/tool dependencies."""
    retrieval = graph_root(root)
    files = [
        root / "cli.py",
        root / "tools/catalog/catalog.json",
        retrieval / "graph_store.json",
        retrieval / "index_store.json",
        retrieval / "tool_foundation_manifest.json",
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
        retrieval / "scimas" / name
        for name in [
            "graph.json",
            "manifest.json",
            "annotations.json",
            "embeddings.json.gz",
        ]
    )
    if embedding_backend() == "local":
        files.extend([
            root / "configs/services/qwen3_embedding.json",
            root / "scripts/services/embedding_service.py",
        ])
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
    os.environ["SCITOOL_EMBEDDING_BACKEND"] = embedding_backend(getattr(args, "embedding_backend", None))
    catalog = ToolCatalog(root)
    baseline = getattr(args, "baseline", "react")
    intervention = runtime_options(baseline, getattr(args, "scimas_ablation", "full"))
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
        asset_root = root / "tasks" / getattr(args, "dataset", "full")
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
                    **intervention,
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
                "embedding_identity": result.get("embedding_identity"),
                "metrics": result.get("metrics")
                or task_metrics(
                    result["resource_usage"],
                    calls,
                    runtime_seconds=result["duration_seconds"],
                    finished=True,
                ),
            }
            failure = result.get("infrastructure_failure")
            if not failure and result["status"] != "completed":
                requests = result.get("resource_usage", {}).get("requests", [])
                failure = requests[-1].get("infrastructure_failure") if requests else None
            if failure:
                prediction["infrastructure_failure"] = failure
                prediction["metrics"].update(runtime_seconds=None, runtime_reportable=False)
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
                    None, None, runtime_seconds=time.monotonic() - started,
                    finished=True, infrastructure_failure=infrastructure_failure(error),
                ),
            }
            if infrastructure_failure(error):
                prediction["infrastructure_failure"] = infrastructure_failure(error)
        if baseline == "scimas":
            prediction["ablation"] = resolve_ablation(
                intervention["scimas_ablation"]
            ).document()
        return prediction
    finally:
        client.close()


def run_batch(args):
    baseline = getattr(args, "baseline", "react")
    variant = getattr(args, "scimas_ablation", "full")
    runtime_options(baseline, variant)  # Validate before client or output creation.
    root = project_root()
    load_environment()
    selected_embedding = embedding_backend(getattr(args, "embedding_backend", None))
    os.environ["SCITOOL_EMBEDDING_BACKEND"] = selected_embedding
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
        / (baseline + ("_" + variant if baseline == "scimas" and variant != "full" else "")
           + "_" + dataset.name + "_" + timestamp)
        / "predictions.json"
    )
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    settings = {
        k: v
        for k, v in vars(args).items()
        if k not in {"output", "resume", "retry_failed", "retry_infrastructure", "func", "command"}
    }
    settings.update(
        embedding_backend=selected_embedding,
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
    if baseline == "scimas":
        policy = resolve_ablation(variant)
        settings["scimas_ablation"] = policy.variant
        settings["scimas_execution"] = {
            **policy.document(),
            "config": policy.apply(json.loads(
                (root / "baselines/scimas/config.json").read_text()
            )),
        }
    fingerprint = hashlib.sha256(
        json.dumps(settings, sort_keys=True).encode()
    ).hexdigest()
    predictions = []
    attempt_history = []
    if output.exists():
        if not args.resume:
            raise ValueError("Output exists; use --resume or another output")
        checkpoint = json.loads(output.read_text())
        predictions = resume_rows(checkpoint, fingerprint, args.retry_failed,
                                  getattr(args, "retry_infrastructure", False))
        kept = {p["id"] for p in predictions}
        attempt_history = checkpoint.get("attempt_history", []) + [
            p for p in checkpoint.get("predictions", []) if p["id"] not in kept
        ]
    completed_ids = {r["id"] for r in predictions}

    def save():
        atomic_json(
            output,
            {
                "schema_version": "scitoolflow.predictions.v1",
                "fingerprint": fingerprint,
                "settings": settings,
                "predictions": predictions,
                "attempt_history": attempt_history,
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
                **({"ablation": policy.document()} if baseline == "scimas" else {}),
                "tasks": [
                    {
                        "id": row["id"],
                        "status": row["status"],
                        "completed": row.get("completed", False),
                        "trace_path": row.get("trace_path"),
                        "failure_reason": row.get("failure_reason"),
                        "infrastructure_failure": row.get("infrastructure_failure"),
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
    options["embedding_backend"] = selected_embedding
    jobs = [
        (row["id"], (row, options, str(output), namespace))
        for row in selected
        if row["id"] not in completed_ids
    ]
    task_order = {row["id"]: i for i, row in enumerate(selected)}
    active_ids = []
    status = "running"
    circuit = CommunicationCircuit(getattr(args, "network_failure_threshold", 3))
    session_started = time.monotonic()
    session_started_at = datetime.now(timezone.utc).isoformat()

    def progress(active=None):
        nonlocal active_ids
        if active is not None:
            active_ids = active
        atomic_json(
            output.parent / "progress.json",
            {
                "status": status,
                "dataset": dataset.name,
                "baseline": baseline,
                "model": client.model,
                "backend": client.backend,
                "fingerprint": fingerprint,
                "runner_pid": os.getpid(),
                "session_started_at": session_started_at,
                "tool_concurrency_per_task": settings['scimas_execution']['config']['tool_concurrency'] if baseline == 'scimas' else 1,
                **({"ablation": policy.document()} if baseline == "scimas" else {}),
                "updated_at": datetime.now().astimezone().isoformat(),
                "concurrency": concurrency,
                "selected_tasks": len(selected),
                "recorded_predictions": len(predictions),
                "completed_tasks": sum(bool(p.get("completed")) for p in predictions),
                "active_tasks": active_ids,
                "pending_tasks": max(0, len(selected) - len(predictions) - len(active_ids)),
                "session_wall_runtime_seconds": max(0, time.monotonic() - session_started),
                "communication_circuit": circuit.snapshot(),
                "infrastructure_failures": sum(bool(p.get("infrastructure_failure")) for p in predictions),
            },
        )

    save()
    progress()
    start_monitor(output.parent)
    # The metadata-only client owns no requests, and is not passed to workers.
    client.close()
    scheduled = iter_tasks(jobs, run_task, concurrency, progress,
                           should_schedule=lambda: not circuit.open)
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
            if response.get("infrastructure_failure"):
                prediction["infrastructure_failure"] = response["infrastructure_failure"]
            if baseline == "scimas":
                prediction.setdefault("ablation", policy.document())
            predictions.append(prediction)
            circuit.observe(prediction)
            if circuit.open:
                status = "paused_infrastructure"
            predictions.sort(key=lambda p: task_order[p["id"]])
            save()
            progress()
            print(
                f"[done] {task_id} status={prediction['status']} recorded={len(predictions)}/{len(selected)}",
                flush=True,
            )
        status = "paused_infrastructure" if circuit.open else "finished"
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
