"""Rank invariance preserves ties and whole observed pairs,not just marginals."""

import copy
import unittest
from evaluation.workflow import MissingEvidence, operand, predicate


def rank(values):
    return {"operation": "average_ranks", "args": [{"value": values}]}


class AverageRankEvidenceTests(unittest.TestCase):
    def test_increasing_encoding_and_joint_permutation_preserve_whole_pairs(self):
        x = [1, 2, 2, 4, 5]
        y = [9, 3, 7, 1, 6]
        permutation = [4, 1, 3, 0, 2]
        encoded = {1: -1e30, 2: 0, 4: 0.25, 5: 1e-1 + 1}
        pair = lambda a, b: {
            "operation": "paired_rows",
            "args": [rank(a), {"value": b}],
        }
        expected = pair(x, y)
        actual = pair([encoded[x[i]] for i in permutation], [y[i] for i in permutation])
        self.assertTrue(
            predicate({"left": actual, "op": "multiset_equal", "right": expected}, {})
        )
        # Same rank and richness marginals cannot hide an independent reorder.
        wrong = pair([encoded[x[i]] for i in permutation], list(reversed(y)))
        self.assertFalse(
            predicate({"left": wrong, "op": "multiset_equal", "right": expected}, {})
        )
        # Merging or reversing categories changes the scientific ordinal scale.
        for wrong_x in [[0, 0, 0, 1, 2], [-v for v in x]]:
            self.assertFalse(
                predicate(
                    {
                        "left": pair(wrong_x, y),
                        "op": "multiset_equal",
                        "right": expected,
                    },
                    {},
                )
            )

    def test_ties_exact_values_order_and_live_source_binding(self):
        values = [3.0, 1, 1.0, 2, -0.0, 0]
        before = copy.deepcopy(values)
        self.assertEqual(operand(rank(values), {}), [6.0, 3.5, 3.5, 5.0, 1.5, 1.5])
        self.assertEqual(values, before)
        self.assertEqual(operand(rank([1.0, 1.0000000000000002]), {}), [1.0, 2.0])
        context = {"nodes": {"read": {"output": {"moisture": values}}}}
        expression = {
            "operation": "average_ranks",
            "args": [{"source": "node", "node": "read", "path": "/moisture"}],
        }
        self.assertEqual(operand(expression, context), [6.0, 3.5, 3.5, 5.0, 1.5, 1.5])
        values[0] = -1
        self.assertEqual(operand(expression, context), [1.0, 4.5, 4.5, 6.0, 2.5, 2.5])

    def test_invalid_types_nonfinite_and_resource_bounds(self):
        for values in [
            [],
            [True],
            [None],
            ["1"],
            [[1]],
            [float("inf")],
            [float("nan")],
            [10**1000],
            [0] * 10001,
        ]:
            with (
                self.subTest(values_type=str(type(values))),
                self.assertRaises(MissingEvidence),
            ):
                operand(rank(values), {})
        for args in [[], [{"value": [1]}, {"value": [2]}]]:
            with self.assertRaises(MissingEvidence):
                operand({"operation": "average_ranks", "args": args}, {})
        self.assertEqual(operand(rank([4] * 10000), {}), [5000.5] * 10000)


if __name__ == "__main__":
    unittest.main()
