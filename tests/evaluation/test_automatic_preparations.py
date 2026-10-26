"""Automatic contract reads are authenticated without changing scientific order."""

import copy
import pytest
from evaluation.integrity.traces import execution_calls, verify_trajectory


@pytest.fixture
def evidence():
    def call(name, identifier):
        return {
            "tool": name,
            "observation_id": identifier,
            "arguments": {"x": 1},
            "status": "success",
            "output": {"value": 2},
        }

    first, second = call("Measure", "o001"), call("Compare", "o002")
    doc = dict(call("DescribeTools", "d001"), kind="discovery", automatic=True)
    trace = {
        "baseline": "scitoolagent",
        "task_id": "FLOW-TEST",
        "status": "completed",
        "final_answer": {"value": 2},
        "failure_reason": None,
        "steps": [
            {"type": "tools", "calls": [first]},
            {"type": "tools", "calls": [second]},
        ],
        "preparations": [doc],
    }
    prediction = {
        "id": "FLOW-TEST",
        "completed": True,
        "status": "completed",
        "final_answer": trace["final_answer"],
        "failure_reason": None,
        "calls": copy.deepcopy([doc, first, second]),
    }
    registry = {"tools": {k: {} for k in ["Measure", "Compare", "DescribeTools"]}}
    return trace, prediction, registry


def test_automatic_reads_are_counted_and_verified(evidence):
    trace, prediction, registry = evidence
    actual = verify_trajectory(trace, prediction, registry)
    assert len(actual) == 3
    assert [c["tool"] for c in actual if c["tool"] != "DescribeTools"] == [
        "Measure",
        "Compare",
    ]


@pytest.mark.parametrize("change", ["missing", "output", "duplicate", "science_order"])
def test_missing_altered_duplicate_or_reordered_evidence_rejected(evidence, change):
    trace, prediction, registry = evidence
    if change == "missing":
        prediction["calls"].pop(0)
    elif change == "output":
        prediction["calls"][0]["output"] = {"invented": True}
    elif change == "duplicate":
        trace["steps"][0]["calls"].append(copy.deepcopy(trace["preparations"][0]))
    else:
        prediction["calls"][1:] = list(reversed(prediction["calls"][1:]))
    with pytest.raises(ValueError):
        verify_trajectory(trace, prediction, registry)


@pytest.mark.parametrize(
    "field,value", [("tool", "Measure"), ("automatic", False), ("kind", "scientific")]
)
def test_preparations_cannot_hide_scientific_calls(evidence, field, value):
    trace, _, _ = evidence
    trace["preparations"][0][field] = value
    with pytest.raises(ValueError, match="automatic DescribeTools"):
        execution_calls(trace)
