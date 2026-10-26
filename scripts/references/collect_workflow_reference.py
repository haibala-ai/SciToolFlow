"""Collect an executed native answer only after a task-specific parent review.

This command does not generate scientific values, run an actor, or approve a task.
The independently authored review must already bind the task, trace and criteria.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from evaluation.integrity.traces import canonical_sha256
from evaluation.integrity.reference import validate_workflow_reference
from scripts.references.audit_workflow_design import rows


def collect(task, hidden, run_directory, review_path, output):
    output = output.resolve()
    if output in {
        (ROOT / name).resolve()
        for name in (
            "evaluation/data/references.jsonl",
            "evaluation/data/references.jsonl.gz",
        )
    }:
        raise ValueError("Draft collection cannot replace the active release")
    run = json.loads((run_directory / "candidate.json").read_text())
    review = json.loads(review_path.read_text())
    trace = Path(run["trace_path"]).resolve()
    digest = hashlib.sha256(trace.read_bytes()).hexdigest()
    if run["task_id"] != task["id"] or review.get("task_id") != task["id"]:
        raise ValueError("Native task and review identity differ")
    if review.get("task_sha256") != canonical_sha256(task):
        raise ValueError("Review does not bind the current public task")
    if review.get("trace_sha256") != digest:
        raise ValueError("Review does not bind the executed trajectory")
    if review.get("evaluation_sha256") != canonical_sha256(hidden["evaluation"]):
        raise ValueError("Review does not bind the current scientific criteria")
    existing = rows([output]) if output.exists() else {}
    if task["id"] in existing:
        raise ValueError("Reference already collected; revise explicitly after review")
    destination = output.parent / "reference_traces" / task["id"] / "trajectory.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.resolve() != trace:
        shutil.copyfile(trace, destination)
    actor = review["native_actor"]
    if actor.get("model_api_used") is not False:
        raise ValueError("Review must explicitly attest no model API generation")
    reference = {
        "id": task["id"],
        "question": task["question"],
        "inputs": task["inputs"],
        "answer_contract": task["answer_schema"],
        "expected_answer": run["final_answer"],
        "evaluation": hidden["evaluation"],
        "reference_trace": str(destination.relative_to(ROOT)),
        "native_provenance": {
            "actor_backend": "native_subagent",
            "actor_id": actor["id"],
            "model_api_used": False,
            "task_sha256": canonical_sha256(task),
            "trace_sha256": digest,
            "task_identity": {
                k: canonical_sha256(task)
                for k in [
                    "current_public_task_sha256",
                    "generation_task_sha256",
                    "review_task_sha256",
                ]
            },
        },
        "review": {
            "status": review["status"],
            "reviewer": review["reviewer"],
            "reviewed_trace_sha256": digest,
            "record": review,
            "record_sha256": canonical_sha256(review),
        },
    }
    manifest = run_directory / "generation_manifest.json"
    if manifest.exists():
        provenance = json.loads(manifest.read_text())
        if (
            provenance.get("public_task_sha256") != canonical_sha256(task)
            or provenance.get("model_api_used") is not False
        ):
            raise ValueError("Generation manifest/task mismatch")
        reference["native_provenance"]["generation_manifest"] = provenance
        reference["native_provenance"]["generation_manifest_sha256"] = canonical_sha256(
            provenance
        )
    catalog = json.loads((ROOT / "tools/catalog/catalog.json").read_text())
    calls = validate_workflow_reference(
        ROOT, task, reference, catalog["tools"], catalog
    )
    existing[task["id"]] = reference
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=output.name + ".", dir=output.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w") as stream:
            for key in sorted(existing):
                stream.write(
                    json.dumps(existing[key], ensure_ascii=False, allow_nan=False)
                    + "\n"
                )
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "collected_task": task["id"],
        "reviewed_references": len(existing),
        "scientific_calls": calls,
        "active_release_changed": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", required=True)
    parser.add_argument("--public", type=Path, required=True)
    parser.add_argument("--hidden", type=Path, required=True)
    parser.add_argument("--run-directory", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            collect(
                rows([args.public])[args.task],
                rows([args.hidden])[args.task],
                args.run_directory,
                args.review,
                args.output,
            )
        )
    )


if __name__ == "__main__":
    main()
