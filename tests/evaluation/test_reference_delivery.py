"""Delivery references are self-contained; compression preserves real evidence."""

import copy
import gzip
import json
from pathlib import Path
import pytest
from evaluation.integrity.reference import task_identity
from evaluation.integrity.traces import (
    canonical_sha256,
    read_trajectory,
    trajectory_bytes,
)
from scripts.benchmark.index_tasks import task_categories
from src.utils.io import read_jsonl

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def identity_case():
    task = {
        "id": "FLOW-test",
        "question": "Infer the given physical model",
        "inputs": {"x": 2},
        "files": [],
        "answer_schema": {"type": "object"},
    }
    provenance = {
        "task_identity": {
            "current_public_task_sha256": canonical_sha256(task),
            "generation_task_sha256": "a" * 64,
            "review_task_sha256": "b" * 64,
        }
    }
    return task, provenance


def test_self_contained_identity_requires_no_source_files(identity_case):
    task, provenance = identity_case
    assert task_identity(task, provenance) == provenance["task_identity"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("question", "Different question"),
        ("inputs", {"x": 3}),
        ("files", ["other.csv"]),
        ("answer_schema", {"type": "string"}),
    ],
)
def test_task_changes_cannot_borrow_reference_identity(identity_case, field, value):
    task, provenance = identity_case
    task[field] = value
    with pytest.raises(ValueError, match="identity mismatch"):
        task_identity(task, provenance)


@pytest.mark.parametrize("field", ["generation_task_sha256", "review_task_sha256"])
def test_original_evidence_identities_are_required(identity_case, field):
    task, provenance = identity_case
    provenance["task_identity"][field] = "invalid"
    with pytest.raises(ValueError):
        task_identity(task, provenance)


def test_compression_preserves_exact_bytes_and_complete_observations(tmp_path):
    raw = b'{ "steps" : [{"calls":[{"output":{"data":[1,2,3]}}]}] }\n'
    path = tmp_path / "primary.json.gz"
    path.write_bytes(gzip.compress(raw, mtime=0))
    assert trajectory_bytes(path) == raw
    assert read_trajectory(path)["steps"][0]["calls"][0]["output"]["data"] == [1, 2, 3]


def test_nonfinite_observations_are_rejected_even_when_compressed(tmp_path):
    path = tmp_path / "bad.json.gz"
    path.write_bytes(gzip.compress(b'{"value":NaN}'))
    with pytest.raises(ValueError, match="Nonfinite"):
        read_trajectory(path)


def test_category_document_lists_exactly_500_tasks_with_expected_counts():
    from collections import Counter

    categories = task_categories(ROOT)
    tasks = read_jsonl(ROOT / "tasks/full/questions.jsonl")
    assert set(categories) == {r["id"] for r in tasks}
    index = json.loads((ROOT / "tasks/full/index.json").read_text())
    assert categories == {r["id"]: r["category"] for r in index["tasks"]}
    assert Counter(categories.values()) == {
        "high_difficulty": 100,
        "tool_composition": 50,
        "standard": 350,
    }
    assert Counter(
        r["domain"] for r in tasks if categories[r["id"]] == "high_difficulty"
    ) == {"Chemical": 25, "Material": 25, "Biology": 25, "MachineLearning": 25}


def test_delivery_has_no_duplicate_or_process_partitioned_reference_runs():
    refs = read_jsonl(ROOT / "evaluation/data/references.jsonl.gz")
    additional = read_jsonl(ROOT / "evaluation/data/reference_runs.jsonl.gz")
    assert len(refs) == 500 and len(additional) == 281
    seen = set()
    for ref in refs + additional:
        identity = (ref["id"], ref["native_provenance"]["trace_sha256"])
        assert identity not in seen
        seen.add(identity)
        assert isinstance(ref["review"]["record"], dict)
        assert isinstance(ref["native_provenance"]["generation_manifest"], dict)
        assert ref["reference_trace"].startswith(
            "evaluation/data/trajectories/" + ref["id"] + "/"
        )
        assert (ROOT / ref["reference_trace"]).is_file()
