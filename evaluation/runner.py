"""Load predictions and run the same scoring protocol for every baseline."""

from pathlib import Path
import json
from tools.catalog import ToolCatalog
from scitoolflow.io import read_jsonl
from .validation import validate_package
from .files import normalizer
from .reviews import review_callback
from .scoring import evaluate_v2


def evaluate_package(root, predictions, output, reviews=None, task_ids=None):
    root = Path(root).resolve()
    validate_package(root)
    refs = read_jsonl(root / "evaluation/references.jsonl")
    if task_ids is not None:
        ids = set(task_ids)
        if not ids or ids - {r["id"] for r in refs}:
            raise ValueError("Unknown or empty scoring selection")
        refs = [r for r in refs if r["id"] in ids]
    path = Path(predictions)
    predicted = (
        json.loads(path.read_text()) if path.suffix == ".json" else read_jsonl(path)
    )
    if isinstance(predicted, dict):
        recorded_task_hash = (
            predicted.get("settings", {})
            .get("actor_file_hashes", {})
            .get("tasks/questions.jsonl")
        )
        if recorded_task_hash:
            import hashlib

            current_task_hash = hashlib.sha256(
                (root / "tasks/questions.jsonl").read_bytes()
            ).hexdigest()
            if current_task_hash != recorded_task_hash:
                raise ValueError(
                    "Task release changed since these predictions were generated. "
                    "Use the matching frozen task/reference release; do not compare old answers with revised contracts."
                )
        predicted = predicted["predictions"]
    result = evaluate_v2(
        refs,
        predicted,
        output,
        registry=ToolCatalog(root).registry(),
        trace_root=root,
        normalize_value=normalizer(root),
        semantic=review_callback(reviews),
    )
    result["summary"].update(
        scoring_protocol="scitoolflow-0.3",
        selection="all" if task_ids is None else sorted(task_ids),
        describe_tools_excluded_from_planning_and_call_budget=True,
        partial_leaf_credit="Unique scientific leaves; overlapping field rules do not add weight.",
    )
    Path(output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result
