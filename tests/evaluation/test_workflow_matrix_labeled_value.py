import pytest
from evaluation.workflow import MissingEvidence, operand


def value(matrix, ids, first="a", second="b"):
    return operand(
        {
            "operation": "matrix_value_by_ids",
            "args": [
                {"value": matrix},
                {"value": ids},
                {"value": first},
                {"value": second},
            ],
        },
        {},
    )


def test_label_lookup_preserves_axes_sign_and_diagonal_without_inference():
    assert value([[3, -7], [9, 5]], ["b", "a"]) == 9
    assert value([[3, -7], [9, 5]], ["b", "a"], "b", "a") == -7
    assert value([[3, -7], [9, 5]], ["b", "a"], "a", "a") == 5


@pytest.mark.parametrize(
    "matrix,ids,first,second",
    [
        ([[0]], ["a"], "a", "a"),
        ([[0, 1], [1, 0]], ["a", "a"], "a", "a"),
        ([[0, 1], [1, 0]], ["a", ""], "a", ""),
        ([[0, 1], [1, 0]], ["a", 1], "a", 1),
        ([[0, 1], [1, 0]], ["a", "b"], "missing", "b"),
        ([[0, 1], [1, 0]], ["a", "b"], "a", "missing"),
        ([[0, 1], [1, 0]], ["a", "b"], 1, "b"),
        ([[0, 1], [1, 0]], ["a", "b"], "a", None),
        ([[0, 1], [1]], ["a", "b"], "a", "b"),
        ([[0, 1], [1, 0], [1, 2]], ["a", "b"], "a", "b"),
        ([[0, "1"], [1, 0]], ["a", "b"], "a", "b"),
        ([[0, True], [1, 0]], ["a", "b"], "a", "b"),
        ([[0, 1], [float("nan"), 0]], ["a", "b"], "a", "b"),
        ([[0, 1], [float("inf"), 0]], ["a", "b"], "a", "b"),
        ([[0, 1], None], ["a", "b"], "a", "b"),
        ([[0] * 21 for _ in range(21)], [str(i) for i in range(21)], "0", "1"),
        ([[0, 1], [1, 0]], ["a", "b" * 201], "a", "a"),
    ],
)
def test_all_axes_and_cells_must_be_complete_and_finite(matrix, ids, first, second):
    with pytest.raises(MissingEvidence):
        value(matrix, ids, first, second)
