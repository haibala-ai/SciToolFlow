"""Public dataset loading and persistent phase-one planning artifacts."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from tasks.datasets import load_dataset
from tasks.assets import load_agent_input
from src.models.client import GenerationClient
from src.utils.io import atomic_json
from .assets import asset_previews, public_asset_scope
from .knowledge import ToolKnowledge
from .planner import Planner, PlanningFailure
from src.models.embedding_profiles import embedding_backend
from src.utils.paths import load_environment
from baselines.common.monitor import start_monitor


def run_planning(args):
    load_environment()
    os.environ["SCITOOL_EMBEDDING_BACKEND"] = embedding_backend(getattr(args, "embedding_backend", None))
    dataset = load_dataset(args.dataset)
    tasks = dataset.select(args.tasks)
    folder = Path(args.output)
    folder.mkdir(parents=True, exist_ok=True)
    if any((folder / (task["id"] + ".json")).exists() for task in tasks):
        raise ValueError(
            "Planning output already exists; choose a new output directory"
        )
    rows = []
    status, active, client = 'running', [], None
    session_started_at = datetime.now(timezone.utc).isoformat()

    def progress():
        atomic_json(folder/'progress.json', {
            'status':status, 'stage':'graph_planning', 'dataset':args.dataset,
            'baseline':'scimas', 'model':args.model or getattr(client, 'model', None),
            'backend':args.backend, 'runner_pid':os.getpid(),
            'session_started_at':session_started_at, 'concurrency':1,
            'selected_tasks':len(tasks), 'recorded_predictions':len(rows),
            'active_tasks':active,
        })

    progress()
    start_monitor(folder)
    try:
        knowledge = ToolKnowledge()
        client = GenerationClient(backend=args.backend)
        if args.model:
            client.model = args.model
        planner = Planner(knowledge, client, max_requests=args.max_model_requests,
                          max_output_tokens=args.max_output_tokens, timeout=args.task_timeout)
        for task in tasks:
            active = [task['id']]
            progress()
            public = load_agent_input(task, dataset.asset_root)
            try:
                with public_asset_scope(dataset.asset_root):
                    report = planner.plan(
                        public,
                        dataset=args.dataset,
                        assets=asset_previews(public, dataset.asset_root),
                    )
            except PlanningFailure as failure:
                report = failure.report
            atomic_json(folder / (task["id"] + ".json"), report)
            rows.append(
                {
                    "id": task["id"],
                    "status": report["status"],
                    "requests": len(report["steps"]),
                }
            )
            atomic_json(
                folder / "summary.json",
                {
                    "dataset": args.dataset,
                    "stage": "graph_planning",
                    "tasks": rows,
                    "scientific_calls": 0,
                },
            )
            active = []
            progress()
        status = 'finished'
    except KeyboardInterrupt:
        status = 'interrupted'
        raise
    except BaseException:
        status = 'failed'
        raise
    finally:
        active = []
        progress()
        if client is not None:
            client.close()
    return {
        "dataset": args.dataset,
        "planned": sum(r["status"] == "planned" for r in rows),
        "failed": sum(r["status"] != "planned" for r in rows),
        "output": str(folder),
    }
