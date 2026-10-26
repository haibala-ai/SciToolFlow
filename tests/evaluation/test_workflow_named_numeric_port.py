import pytest
from evaluation.workflow import MissingEvidence, operand, validate_workflow


def port(value, paths=None):
    return operand(
        {
            "operation": "named_numeric_port",
            "args": [
                {"value": value},
                {
                    "value": (
                        ["/formula_mass_u", "/molar_mass"] if paths is None else paths
                    )
                },
            ],
        },
        {},
    )


@pytest.mark.parametrize(
    "value,expected",
    [
        ({"formula_mass_u": 18.015}, 18.015),
        ({"molar_mass": 18.015}, 18.015),
        ({"molar_mass": 0}, 0),
        ({"molar_mass": -1}, -1),
    ],
)
def test_exactly_one_finite_explicit_port(value, expected):
    assert port(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        {},
        {"value": 18.015},
        {"molar_mass": None},
        {"molar_mass": "18.015"},
        {"molar_mass": True},
        {"molar_mass": float("nan")},
        {"molar_mass": float("inf")},
        {"molar_mass": 18.015, "formula_mass_u": 18.015},
        {"molar_mass": 18.015, "formula_mass_u": None},
        {"molar_mass": [18.015]},
        [18.015],
    ],
)
def test_missing_ambiguous_or_non_numeric_never_coerced(value):
    with pytest.raises(MissingEvidence):
        port(value)


@pytest.mark.parametrize(
    "paths",
    [
        ["/molar_mass", "/molar_mass"],
        ["molar_mass"],
        ["/bad~2escape"],
        [None],
        [""],
        ["/a"] * 9,
        [],
    ],
)
def test_invalid_or_duplicated_pointer_contract_rejected(paths):
    with pytest.raises(MissingEvidence):
        port({"molar_mass": 18.015}, paths)


def test_nested_explicit_port_and_escaped_key():
    assert port({"a/b": {"mass": 18.015}}, ["/a~1b/mass"]) == 18.015


def test_static_workflow_arity_is_checked():
    expr = {"operation": "named_numeric_port", "args": [{"source": "call_output"}]}
    spec = {
        "schema_version": "workflow.v1",
        "nodes": [
            {
                "id": "m",
                "alternatives": [
                    {
                        "tools": ["Mass"],
                        "output_rules": [{"left": expr, "op": "finite"}],
                    }
                ],
            }
        ],
        "outcomes": [
            {
                "id": "result",
                "left": {"source": "answer", "path": "/m"},
                "op": "eq",
                "value": 18.015,
                "evidence_nodes": ["m"],
            }
        ],
    }
    with pytest.raises(ValueError):
        validate_workflow(spec)
