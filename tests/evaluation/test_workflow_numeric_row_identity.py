"""Actual prediction/feature identity, independent of the submitted row ordering."""

import copy
import unittest
from evaluation.workflow import MissingEvidence, operand


def lookup(rows, values, row):
    return operand(
        {
            "operation": "numeric_value_for_row",
            "args": [{"value": rows}, {"value": values}, {"value": row}],
        },
        {},
    )


class NumericRowIdentityTest(unittest.TestCase):
    def test_complete_exact_keys_and_joint_permutation(self):
        rows, values = [[2**54, 2], [2**54 + 1, 2], [9, 3]], [11, 22, 33]
        before = copy.deepcopy((rows, values))
        self.assertEqual(lookup(rows, values, [2**54 + 1, 2]), 22)
        self.assertEqual(lookup(rows[::-1], values[::-1], [2**54 + 1, 2]), 22)
        self.assertNotEqual(lookup(rows, values[1:] + values[:1], [2**54 + 1, 2]), 22)
        self.assertEqual((rows, values), before)
        for target in [[2**54], [2, 2**54], [2**54, 2.000000000000001]]:
            with self.assertRaises(MissingEvidence):
                lookup(rows, values, target)

    def test_duplicate_agreement_includes_unselected_rows(self):
        self.assertEqual(lookup([[1], [1.0], [2]], [3, 3.0, 4], [1]), 3)
        with self.assertRaises(MissingEvidence):
            lookup([[1], [2], [2]], [3, 4, 5], [1])

    def test_live_node_arguments_and_observations_are_used(self):
        context = {
            "nodes": {
                "predict": {
                    "arguments": {"features": [[1, 2], [3, 4]]},
                    "output": {"predictions": [8, 9]},
                }
            }
        }
        expression = {
            "operation": "numeric_value_for_row",
            "args": [
                {"source": "node_arguments", "node": "predict", "path": "/features"},
                {"source": "node", "node": "predict", "path": "/predictions"},
                {"value": [3, 4]},
            ],
        }
        self.assertEqual(operand(expression, context), 9)
        context["nodes"]["predict"]["output"]["predictions"] = [9, 8]
        self.assertEqual(operand(expression, context), 8)

    def test_all_numeric_cells_types_shapes_and_resource_limits(self):
        for bad in [True, "2", None, float("nan"), float("inf"), 10**1000]:
            for rows, values, row in [
                ([[1], [bad]], [2, 3], [1]),
                ([[1], [2]], [2, bad], [1]),
                ([[1]], [2], [bad]),
            ]:
                with self.subTest(bad=repr(bad)), self.assertRaises(MissingEvidence):
                    lookup(rows, values, row)
        for rows, values, row in [
            ([], [], []),
            ([[1], [2, 3]], [1, 2], [1]),
            ([[1]], [], [1]),
            ([[1] * 1001], [2], [1] * 1001),
            ([[1, 2]] * 6667, [3] * 6667, [1, 2]),
        ]:
            with self.assertRaises(MissingEvidence):
                lookup(rows, values, row)
        self.assertEqual(lookup([[1]] * 10000, [2] * 10000, [1]), 2)
        with self.assertRaises(MissingEvidence):
            operand(
                {"operation": "numeric_value_for_row", "args": [{"value": [[1]]}]}, {}
            )
