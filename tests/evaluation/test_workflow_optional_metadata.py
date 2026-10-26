"""Exact optional metadata lookup must not replace unavailable science by a default."""

import math
import pytest
from evaluation.workflow import MissingEvidence, operand, validate_workflow


def lookup(obj, key):
    return operand(
        {
            "operation": "object_member_or_null",
            "args": [{"value": obj}, {"value": key}],
        },
        {},
    )


@pytest.mark.parametrize("value", [None, False, 0, 0.0, "", [], {}, [1, {"a": False}]])
def test_present_values_preserved(value):
    assert lookup({"count": value}, "count") == value
    assert type(lookup({"count": value}, "count")) is type(value)


def test_only_absent_exact_member_is_null():
    assert lookup({"number": 154}, "operation_count") is None
    assert lookup({"a": {"b": 6}}, "/a/b") is None
    assert lookup({"/a/b": 6}, "/a/b") == 6
    with pytest.raises(MissingEvidence):
        lookup(None, "count")


@pytest.mark.parametrize(
    "obj,key",
    [
        (1, "count"),
        ([], "count"),
        ({}, ""),
        ({}, "a" * 129),
        ({}, 1),
        ({"x": math.nan}, "count"),
        ({"x": math.inf}, "count"),
        ({"x": (1, 2)}, "count"),
        ({1: "a"}, "count"),
        ({"x": {1}}, "count"),
    ],
)
def test_invalid_or_nonfinite_evidence_rejected(obj, key):
    with pytest.raises(MissingEvidence):
        lookup(obj, key)


def test_exact_arity_registration():
    e = {
        "schema_version": "workflow.v1",
        "nodes": [
            {
                "id": "a",
                "alternatives": [
                    {
                        "tools": ["T"],
                        "output_rules": [
                            {
                                "left": {
                                    "operation": "object_member_or_null",
                                    "args": [
                                        {"value": {}},
                                        {"value": "x"},
                                        {"value": 0},
                                    ],
                                },
                                "op": "eq",
                                "value": None,
                            }
                        ],
                    }
                ],
            }
        ],
        "outcomes": [
            {
                "id": "a",
                "left": {"source": "answer", "path": "/a"},
                "op": "eq",
                "value": None,
                "evidence_nodes": ["a"],
            }
        ],
    }
    with pytest.raises(ValueError):
        validate_workflow(e)
