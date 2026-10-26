"""Validate every primary and distinct additional reference without tool/LLM calls."""

import argparse
import copy
import hashlib
import json
from pathlib import Path
from evaluation.integrity.reference import validate_workflow_reference
from evaluation.integrity.traces import canonical_sha256
from src.utils.io import read_jsonl
from src.utils.paths import project_root


def validate_references(root):
    root = Path(root).resolve()
    metadata = json.loads((root / "tasks/metadata.json").read_text())
    tasks = {r["id"]: r for r in read_jsonl(root / "tasks/questions.jsonl")}
    refs = {
        r["id"]: r for r in read_jsonl(root / "evaluation/data/references.jsonl.gz")
    }
    registry = json.loads((root / "tools/catalog/catalog.json").read_text())
    if len(tasks) != 500 or set(tasks) != set(refs):
        raise ValueError("Expected 500 aligned tasks and primary references")
    seen = set()
    for tid, reference in sorted(refs.items()):
        validate_workflow_reference(
            root, tasks[tid], reference, registry["tools"], registry
        )
        seen.add((tid, reference["native_provenance"]["trace_sha256"]))
    additional = read_jsonl(root / "evaluation/data/reference_runs.jsonl.gz")
    for row in additional:
        tid = row["id"]
        if tid not in refs or row["evaluation_sha256"] != canonical_sha256(
            refs[tid]["evaluation"]
        ):
            raise ValueError("Additional reference criterion identity differs")
        reference = copy.deepcopy(refs[tid])
        for key in [
            "expected_answer",
            "reference_trace",
            "native_provenance",
            "review",
        ]:
            reference[key] = row[key]
        identity = (tid, reference["native_provenance"]["trace_sha256"])
        if identity in seen:
            raise ValueError("Duplicated primary/additional reference execution")
        seen.add(identity)
        validate_workflow_reference(
            root, tasks[tid], reference, registry["tools"], registry
        )
    return {
        "status": "passed",
        "release": metadata["release"],
        "primary_references": len(refs),
        "additional_references": len(additional),
        "unique_reference_executions": len(seen),
        "new_model_api_calls": 0,
        "new_scientific_tool_calls": 0,
        "file_sha256": {
            name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in [
                "tasks/questions.jsonl",
                "evaluation/data/references.jsonl.gz",
                "evaluation/data/reference_runs.jsonl.gz",
                "tools/catalog/catalog.json",
            ]
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("results/reference_validation.json")
    )
    args = parser.parse_args()
    report = validate_references(project_root())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
