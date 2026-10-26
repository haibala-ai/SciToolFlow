"""Count semantics are exact, finite and distinct from missing/Boolean values."""

import math
import pytest
from evaluation.workflow import MissingEvidence, predicate, validate_workflow


@pytest.mark.parametrize(
    "value,expected",
    [
        (0, True),
        (1, True),
        (6.0, True),
        (-1, True),
        (2.5, False),
        (6.000000000000001, False),
        (True, False),
        (False, False),
        (None, False),
        ("6", False),
        (math.nan, False),
        (math.inf, False),
        ([], False),
    ],
)
def test_integer_type_has_exact_json_number_semantics(value, expected):
    assert (
        predicate({"left": {"value": value}, "op": "type", "value": "integer"}, {})
        is expected
    )


@pytest.mark.parametrize("target", ["int", "count", None, {}, []])
def test_unknown_types_fail_closed_and_are_rejected_at_validation(target):
    rule = {"left": {"value": 6}, "op": "type", "value": target}
    with pytest.raises(MissingEvidence):
        predicate(rule, {})
    spec = {
        "schema_version": "workflow.v1",
        "nodes": [
            {"id": "n", "alternatives": [{"tools": ["T"], "output_rules": [rule]}]}
        ],
        "outcomes": [
            {
                "id": "answer",
                "left": {"source": "answer", "path": "/a"},
                "op": "eq",
                "value": 1,
                "evidence_nodes": ["n"],
            }
        ],
    }
    with pytest.raises(ValueError):
        validate_workflow(spec)
