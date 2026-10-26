"""Reordering training observations must preserve each feature/target pair."""

import copy
import unittest

from evaluation.workflow import MissingEvidence, operand, predicate


def paired(rows, targets):
    return {
        "operation": "paired_rows",
        "args": [{"value": rows}, {"value": targets}],
    }


class PairedRowsTests(unittest.TestCase):
    def test_shared_permutation_preserves_pairs_but_unpaired_shuffle_fails(self):
        expected = paired([[1, 2], [1, 3], [4, 5]], [9, 8, 7])
        rule = {
            "left": paired([[4, 5], [1, 2], [1, 3]], [7, 9, 8]),
            "op": "multiset_equal",
            "right": expected,
        }
        self.assertTrue(predicate(rule, {}))
        rule["left"] = paired([[4, 5], [1, 2], [1, 3]], [9, 7, 8])
        self.assertFalse(predicate(rule, {}))

    def test_duplicate_rows_keep_multiplicity_and_nulls(self):
        rule = {
            "left": paired([[1, None], [1, None], [2, 3]], ["a", "b", "c"]),
            "op": "multiset_equal",
            "right": paired([[1, None], [2, 3], [1, None]], ["b", "c", "a"]),
        }
        self.assertTrue(predicate(rule, {}))
        rule["right"] = paired([[1, None], [2, 3], [1, None]], ["a", "c", "a"])
        self.assertFalse(predicate(rule, {}))

    def test_invalid_alignment_and_unbounded_or_ragged_input_rejected(self):
        for rows, targets in [
            ([], []),
            ([[1]], []),
            ([[1], [2, 3]], [1, 2]),
            ([[]], [1]),
            ([{}], [1]),
            ([[1]] * 10001, [1] * 10001),
            ([[1] * 1001], [1]),
            ([[1] * 10] * 1819, [1] * 1819),
            ([[float("nan")]], [1]),
            ([[1]], [float("inf")]),
            ([[{}]], [1]),
            ([[1]], [[1], [2]]),
            ([[1]], [[]]),
            ([[1], [2]], [[1], [2, 3]]),
            ([[1], [2]], [[1], 2]),
            ([[1]], [[[1]]]),
            ([[1]], [[{}]]),
            ([[1]], [[float("inf")]]),
            ([[1]], [[float("nan")]]),
            ([[1]], [[1] * 1001]),
            ([[1, 2, 3]] * 3334, [[4, 5, 6]] * 3334),
        ]:
            with self.subTest(rows=str(rows)[:40]), self.assertRaises(MissingEvidence):
                operand(paired(rows, targets), {})

    def test_full_scientific_cohort_joint_permutation_over_one_thousand_rows(self):
        rows = [[i, i * 2, i % 7, 3, 4] for i in range(1503)]
        targets = [i / 8 for i in range(1503)]
        rule = {
            "left": paired(rows[::-1], targets[::-1]),
            "op": "multiset_equal",
            "right": paired(rows, targets),
            "atol": 1e-10,
        }
        self.assertTrue(predicate(rule, {}))
        # Full-capacity identical pairs do not need a quadratic matching graph.
        self.assertEqual(len(operand(paired([[1]] * 10000, [2] * 10000), {})), 10000)
        rule = {
            "left": paired(rows[::-1], targets),
            "op": "multiset_equal",
            "right": paired(rows, targets),
        }
        self.assertFalse(predicate(rule, {}))

    def test_truth_prediction_vectors_preserve_joint_alignment(self):
        rule = {
            "left": paired(["a", "b", "a"], ["a", "a", "b"]),
            "op": "multiset_equal",
            "right": paired(["b", "a", "a"], ["a", "b", "a"]),
        }
        self.assertTrue(predicate(rule, {}))
        rule["right"] = paired(["b", "a", "a"], ["a", "a", "a"])
        self.assertFalse(predicate(rule, {}))
        with self.assertRaises(MissingEvidence):
            operand(paired([1, [2]], [1, 2]), {})

    def test_two_coordinate_matrices_preserve_correspondence_and_all_cells(self):
        reference = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
        mobile = [[2, 1, 3], [5, 4, 6], [8, 7, 9]]
        rule = {
            "left": paired(reference[::-1], mobile[::-1]),
            "op": "multiset_equal",
            "right": paired(reference, mobile),
        }
        self.assertTrue(predicate(rule, {}))
        rule["left"] = paired(reference[::-1], mobile)
        self.assertFalse(predicate(rule, {}))
        self.assertEqual(
            operand(paired([1, 2], [[3, 4], [5, 6]]), {}), [[1, [3, 4]], [2, [5, 6]]]
        )
        self.assertEqual(
            len(operand(paired([[1, 2]] * 5000, [[3, 4]] * 5000), {})), 5000
        )

    def test_actual_scoped_inputs_and_source_evidence_are_not_mutated(self):
        context = {"call_arguments": {"x": [[2], [1]], "y": [20, 10]}}
        before = copy.deepcopy(context)
        expression = {
            "operation": "paired_rows",
            "args": [
                {"source": "call_arguments", "path": "/x"},
                {"source": "call_arguments", "path": "/y"},
            ],
        }
        self.assertEqual(operand(expression, context), [[[2], 20], [[1], 10]])
        self.assertEqual(context, before)


if __name__ == "__main__":
    unittest.main()
