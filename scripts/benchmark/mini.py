"""Build or validate the balanced Mini-200 subset from its reviewed selection."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from src.utils.paths import project_root

DOMAINS = ("Chemical", "Material", "Biology", "MachineLearning")
REQUIRED_SOURCE_FILES = {
    "tasks/questions.jsonl",
    "tasks/index.json",
    "tasks/asset_manifest.json",
    "evaluation/data/references.jsonl.gz",
    "evaluation/data/reference_runs.jsonl.gz",
    "tools/catalog/catalog.json",
}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def validate_selection(selection, questions, index):
    """Enforce quotas, original identities and complete author annotations."""
    entries = selection.get("tasks", [])
    identifiers = [entry["id"] for entry in entries]
    source_ids = [entry["source_id"] for entry in entries]
    if len(identifiers) != 200 or len(set(identifiers)) != 200:
        raise ValueError("Mini requires exactly 200 unique task IDs")
    if identifiers != [f"FLOW-{i:04d}" for i in range(1, 201)]:
        raise ValueError("Mini IDs must be contiguous FLOW-0001..FLOW-0200")
    if len(set(source_ids)) != 200 or source_ids != sorted(source_ids):
        raise ValueError("Mini source IDs must be unique and retain source order")
    by_id = {row["id"]: row for row in questions}
    by_index = {row["id"]: row for row in index["tasks"]}
    if (
        len(questions) != 500
        or len(index["tasks"]) != 500
        or len(by_id) != 500
        or set(by_id) != set(by_index)
    ):
        raise ValueError("Expected 500 aligned source questions and index entries")
    domains = Counter()
    for entry in entries:
        tid = entry["id"]
        source_id = entry["source_id"]
        if source_id not in by_id:
            raise ValueError("Unknown source task: " + source_id)
        original, indexed = by_id[source_id], by_index[source_id]
        if indexed["category"] == "high_difficulty":
            raise ValueError("High-difficulty tasks cannot enter Mini: " + tid)
        if (entry["domain"], entry["category"]) != (
            original["domain"],
            indexed["category"],
        ):
            raise ValueError("Selection metadata differs from source: " + tid)
        for key in ("scientific_goal", "shared_prerequisite", "join_requirement"):
            if not isinstance(entry.get(key), str) or not entry[key].strip():
                raise ValueError("Missing decomposition annotation: " + tid)
        branches = entry.get("parallel_subtasks")
        if (
            not isinstance(branches, list)
            or len(branches) < 2
            or any(not isinstance(b, str) or not b.strip() for b in branches)
            or len(set(branches)) != len(branches)
        ):
            raise ValueError("Need distinct, nonempty scientific branches: " + tid)
        domains[original["domain"]] += 1
    if domains != Counter({domain: 50 for domain in DOMAINS}):
        raise ValueError("Mini must contain exactly 50 tasks in each discipline")
    return [{**by_id[entry["source_id"]], "id": entry["id"]} for entry in entries]


def subset_files(root):
    """Derive public Mini rows, changing only their top-level task IDs."""
    folder = root / "tasks/mini"
    selection_raw = (folder / "selection.json").read_bytes()
    selection = json.loads(selection_raw)
    identities = selection["source_files_sha256"]
    if set(identities) != REQUIRED_SOURCE_FILES:
        raise ValueError("Selection must bind all canonical source files")
    for name, expected in identities.items():
        if digest((root / name).read_bytes()) != expected:
            raise ValueError("Source changed; review the subset again: " + name)
    source = (root / "tasks/questions.jsonl").read_bytes().splitlines(keepends=True)
    questions = [json.loads(line) for line in source]
    index = json.loads((root / "tasks/index.json").read_bytes())
    selected = validate_selection(selection, questions, index)
    question_bytes = b"".join(
        (json.dumps(row, ensure_ascii=False) + "\n").encode() for row in selected
    )
    ids_bytes = (
        "mini_id\tfull_id\n"
        + "".join(
            f'{entry["id"]}\t{entry["source_id"]}\n' for entry in selection["tasks"]
        )
    ).encode()
    metadata = {
        "schema_version": "scitoolflow.subset.v2",
        "name": "SciToolFlow Mini-200",
        "version": "20261104.1",
        "dataset": "mini",
        "id_range": ["FLOW-0001", "FLOW-0200"],
        "id_mapping": "tasks/mini/ids.tsv",
        "source_release": selection["source_release"],
        "tasks": len(selected),
        "domains": dict(sorted(Counter(row["domain"] for row in selected).items())),
        "categories": dict(
            sorted(Counter(e["category"] for e in selection["tasks"]).items())
        ),
        "excluded_high_difficulty_tasks": 100,
        "selection_focus": "scientific subtask decomposition and parallel scheduling",
        "selection_support": dict(
            sorted(Counter(e["support"] for e in selection["tasks"]).items())
        ),
        "evaluation_schema": "workflow.v1",
        "asset_release_root": "tasks",
        "references": "evaluation/data/references.jsonl.gz",
        "references_visible_to_agent": False,
        "annotations_are_agent_input": False,
        "independent_test_split": False,
        "sha256": {
            "questions.jsonl": digest(question_bytes),
            "ids.tsv": digest(ids_bytes),
            "selection.json": digest(selection_raw),
        },
    }
    return selected, {
        "questions.jsonl": question_bytes,
        "ids.tsv": ids_bytes,
        "metadata.json": json_bytes(metadata),
    }


def verify_references(root, selected):
    """Check the unchanged gold, actual executions, contracts and second reviews."""
    from evaluation.integrity.reference import validate_workflow_reference
    from evaluation.integrity.traces import read_trajectory, execution_calls
    from evaluation.workflow import score_workflow
    from src.utils.io import read_jsonl
    from tasks.assets import load_agent_input
    from tools.catalog import ToolCatalog

    refs = {
        row["id"]: row
        for row in read_jsonl(root / "evaluation/data/references.jsonl.gz")
    }
    catalog = ToolCatalog(root)
    from tasks.datasets import load_dataset

    dataset = load_dataset("mini", root)
    originals = {row["id"]: row for row in read_jsonl(root / "tasks/questions.jsonl")}
    calls = 0
    for task in selected:
        load_agent_input(task, root / "tasks")
        source_id = dataset.source_id(task["id"])
        calls += validate_workflow_reference(
            root,
            originals[source_id],
            refs[source_id],
            catalog.tools,
            catalog.registry(),
        )
        # Compare the runtime reference view without rewriting/re-signing a trace.
        reference = refs[source_id]
        trajectory = read_trajectory(root / reference["reference_trace"])
        mapped = score_workflow(
            {**reference, "id": task["id"]},
            {
                "id": task["id"],
                "completed": trajectory["status"] == "completed",
                "status": trajectory["status"],
                "final_answer": trajectory["final_answer"],
                "calls": execution_calls(trajectory),
            },
            aliases=catalog.aliases,
            tool_contracts=catalog.tools,
        )
        if not mapped["joint_pass"] or mapped["pending_review"]:
            raise ValueError(
                "Mini reference projection changes the verdict: " + task["id"]
            )
    return {
        "verified_primary_references": len(selected),
        "verified_namespace_mappings": len(selected),
        "reference_scientific_calls": calls,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "check"))
    parser.add_argument(
        "--references",
        action="store_true",
        help="Also verify all 200 original reference executions offline",
    )
    args = parser.parse_args(argv)
    root = project_root()
    selected, outputs = subset_files(root)
    folder = root / "tasks/mini"
    for name, raw in outputs.items():
        path = folder / name
        if args.action == "check":
            if not path.is_file() or path.read_bytes() != raw:
                raise ValueError("Mini artifact missing or stale: " + name)
        else:
            path.write_bytes(raw)
    report = {
        "status": "passed",
        "action": args.action,
        "tasks": len(selected),
        "domains": dict(Counter(r["domain"] for r in selected)),
        "high_difficulty_tasks": 0,
    }
    if args.references:
        report.update(verify_references(root, selected))
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
