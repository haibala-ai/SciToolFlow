"""Public dataset loading and persistent phase-one planning artifacts."""

import json
from pathlib import Path
from tasks.datasets import load_dataset
from tasks.assets import load_agent_input
from src.models.client import GenerationClient
from src.utils.io import atomic_json
from .assets import asset_previews, public_asset_scope
from .knowledge import ToolKnowledge
from .planner import Planner, PlanningFailure


def run_planning(args):
    dataset = load_dataset(args.dataset)
    tasks = dataset.select(args.tasks)
    folder = Path(args.output)
    folder.mkdir(parents=True, exist_ok=True)
    if any((folder / (task["id"] + ".json")).exists() for task in tasks):
        raise ValueError(
            "Planning output already exists; choose a new output directory"
        )
    knowledge = ToolKnowledge()
    client = GenerationClient(backend=args.backend)
    if args.model:
        client.model = args.model
    planner = Planner(
        knowledge,
        client,
        max_requests=args.max_model_requests,
        max_output_tokens=args.max_output_tokens,
        timeout=args.task_timeout,
    )
    rows = []
    try:
        for task in tasks:
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
    finally:
        client.close()
    return {
        "dataset": args.dataset,
        "planned": sum(r["status"] == "planned" for r in rows),
        "failed": sum(r["status"] != "planned" for r in rows),
        "output": str(folder),
    }
