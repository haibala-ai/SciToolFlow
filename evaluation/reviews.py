"""Fingerprint-bound independent semantic review files."""

from pathlib import Path
import json


def review_callback(path):
    """Bind explicit independent reviews to the exact normalized request hashes."""
    if path is None:
        return None
    raw = json.loads(Path(path).read_text())
    rows = raw.get("tasks", raw.get("reviews", [])) if isinstance(raw, dict) else raw
    indexed = {}
    for row in rows:
        if row["id"] in indexed:
            raise ValueError("Duplicate semantic review ID")
        if not all(
            row.get(k)
            for k in [
                "reference_sha256",
                "prediction_sha256",
                "reviewer",
                "rationale",
                "reviewed_at",
            ]
        ):
            raise ValueError(
                "Reviews require request hashes, reviewer, rationale and reviewed_at"
            )
        indexed[row["id"]] = row

    def decide(request):
        row = indexed.get(request["id"])
        if row is None:
            return {}
        if any(row[k] != request[k] for k in ["reference_sha256", "prediction_sha256"]):
            raise ValueError("Semantic review hash mismatch: " + request["id"])
        if request.get("requires_independent_review") and row.get(
            "reviewer_kind"
        ) not in {"human", "independent_scientific_review"}:
            raise ValueError(
                "Changed source requires an explicitly independent scientific review: "
                + request["id"]
            )
        verdict = {}
        for key in ["planning_pass", "answer_pass"]:
            if key in row:
                if type(row[key]) is not bool:
                    raise ValueError("Semantic verdict must be boolean")
                verdict[key] = row[key]
        return {
            **verdict,
            "reviewer": row["reviewer"],
            "rationale": row["rationale"],
            "reviewed_at": row["reviewed_at"],
            "reviewer_kind": row.get("reviewer_kind", "unspecified"),
        }

    return decide
