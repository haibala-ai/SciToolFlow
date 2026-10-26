import pytest

from evaluation.workflow import MissingEvidence, operand, validate_workflow


def decode(operation, *values):
    return operand(
        {"operation": operation, "args": [{"value": value} for value in values]}, {}
    )


@pytest.mark.parametrize(
    "formula,expected",
    [
        ("C2 S2 N1 O4 F6", {"C": 2, "S": 2, "N": 1, "O": 4, "F": 6}),
        ("Mg1 C2 O1", {"Mg": 1, "C": 2, "O": 1}),
        (" H2O ", {"H": 2, "O": 1}),
        ("NaCl", {"Na": 1, "Cl": 1}),
    ],
)
def test_source_formula_counts(formula, expected):
    assert decode("molecular_formula_counts", formula) == expected


@pytest.mark.parametrize(
    "formula",
    [
        "",
        " ",
        None,
        123,
        True,
        "C0H2",
        "C01H2",
        "C2H6+",
        "[NH4]+",
        "Na0.5Cl0.5",
        "CuSO4.5H2O",
        "Ca(OH)2",
        "CH3COOH",
        "Xx2",
        "D2O",
        "C2 garbage",
        "H1000000001",
        "C999999999H2",
        "C" * 1001,
    ],
)
def test_ambiguous_or_invalid_formula_never_guessed(formula):
    with pytest.raises(MissingEvidence):
        decode("molecular_formula_counts", formula)


def test_formula_quantity_is_not_neutral_electron_count():
    # Charge is separate observed evidence: this is nuclear charge137,
    # and an observed molecular charge -1 gives138 electrons.
    counts = decode("molecular_formula_counts", "C2 S2 N1 O4 F6")
    numbers = {"C": 6, "S": 16, "N": 7, "O": 8, "F": 9}
    assert sum(counts[k] * numbers[k] for k in counts) == 137


@pytest.mark.parametrize(
    "left,right,expected",
    [
        ([6, 11, 27, 42], [6, 11, 27], [6, 11, 27]),
        ([], [], []),
        ([1], [], []),
        ([], [1], []),
        ([1, 3], [2, 4], []),
        ([0, 2], [0, 2], [0, 2]),
    ],
)
def test_complete_ordered_boundary_intersection(left, right, expected):
    assert decode("ordered_integer_intersection", left, right) == expected


@pytest.mark.parametrize(
    "bad",
    [
        None,
        {},
        "1",
        [True],
        [1.0],
        [-1],
        [1, 1],
        [2, 1],
        [10**9 + 1],
        list(range(10001)),
    ],
)
def test_invalid_boundaries_rejected(bad):
    with pytest.raises(MissingEvidence):
        decode("ordered_integer_intersection", bad, [1])


@pytest.mark.parametrize(
    "name,values",
    [
        ("molecular_formula_counts", []),
        ("molecular_formula_counts", ["H2O", "H2O"]),
        ("ordered_integer_intersection", [[1]]),
    ],
)
def test_decoder_arity_checked_in_workflow_definition(name, values):
    expression = {"operation": name, "args": [{"value": value} for value in values]}
    spec = {
        "schema_version": "workflow.v1",
        "nodes": [
            {
                "id": "source",
                "alternatives": [
                    {
                        "tools": ["Read"],
                        "output_rules": [{"left": expression, "op": "exists"}],
                    }
                ],
            }
        ],
        "outcomes": [
            {
                "id": "answer",
                "left": {"source": "answer", "path": "/value"},
                "op": "eq",
                "value": 1,
                "evidence_nodes": ["source"],
            }
        ],
    }
    with pytest.raises(ValueError):
        validate_workflow(spec)
