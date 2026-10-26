import pytest

from evaluation.workflow import MissingEvidence, operand


def choose(left, right, equal=None, unequal=None):
    return {
        "operation": "select_if_text_equal",
        "args": [
            {"value": left},
            {"value": right},
            {"value": "original"} if equal is None else equal,
            {"value": "fresh"} if unequal is None else unequal,
        ],
    }


def test_unchanged_input_reuses_actual_original_observation():
    expression = choose(
        "CCO",
        "CCO",
        {"source": "node", "node": "original", "path": "/inchi"},
        {"source": "node", "node": "fresh", "path": "/inchi"},
    )
    context = {"nodes": {"original": {"output": {"inchi": "InChI=1S/C2H6O"}}}}
    assert operand(expression, context) == "InChI=1S/C2H6O"
    expression["args"][1] = {"value": "OCC"}
    with pytest.raises(MissingEvidence):
        operand(expression, context)


def test_changed_input_requires_actual_fresh_result():
    expression = choose(
        "CCO",
        "OCC",
        {"source": "node", "node": "missing"},
        {"source": "node", "node": "fresh", "path": "/inchi"},
    )
    context = {"nodes": {"fresh": {"output": {"inchi": "InChI=1S/C2H6O"}}}}
    assert operand(expression, context) == "InChI=1S/C2H6O"


def test_no_canonicalization_or_case_folding_of_input_identity():
    assert operand(choose("CCO", "OCC"), {}) == "fresh"
    assert operand(choose("C", "c"), {}) == "fresh"
    assert operand(choose(" CCO", "CCO"), {}) == "fresh"


@pytest.mark.parametrize("bad", [None, True, 1, 1.0, [], {}, "", "a" * 2000001])
def test_missing_or_invalid_comparison_never_falls_back(bad):
    with pytest.raises(MissingEvidence):
        operand(choose(bad, "C"), {})


def test_missing_comparison_not_hidden_by_an_available_branch():
    expression = choose("C", "C")
    expression["args"][0] = {"source": "node", "node": "missing"}
    with pytest.raises(MissingEvidence):
        operand(expression, {})


def test_only_selected_arithmetic_branch_is_evaluated():
    bad = {"operation": "divide", "args": [{"value": 1}, {"value": 0}]}
    assert operand(choose("C", "C", {"value": 1}, bad), {}) == 1
    with pytest.raises(MissingEvidence):
        operand(choose("C", "N", {"value": 1}, bad), {})
