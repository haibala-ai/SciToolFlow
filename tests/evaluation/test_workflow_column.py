"""Class probabilities must be selected from the actual ordered model output."""

import copy
import unittest

from evaluation.workflow import MissingEvidence, operand, predicate


class MatrixColumnEvidenceTest(unittest.TestCase):
    def test_actual_positive_class_column_retains_row_alignment(self):
        context = {
            "nodes": {
                "prediction": {
                    "output": {
                        "classes": ["negative", "positive"],
                        "probabilities": [[0.9, 0.1], [0.2, 0.8], [0.5, 0.5]],
                    }
                }
            }
        }
        before = copy.deepcopy(context)
        expression = {
            "operation": "column",
            "args": [
                {"source": "node", "node": "prediction", "path": "/probabilities"},
                {"value": 1},
            ],
        }
        self.assertEqual(operand(expression, context), [0.1, 0.8, 0.5])
        self.assertFalse(
            predicate(
                {"left": expression, "op": "eq", "value": [0.8, 0.1, 0.5]}, context
            )
        )
        self.assertEqual(context, before)

    def test_missing_node_is_not_replaced_with_expected_vector(self):
        with self.assertRaises(MissingEvidence):
            operand(
                {
                    "operation": "column",
                    "args": [
                        {"source": "node", "node": "absent", "path": "/probabilities"},
                        {"value": 1},
                    ],
                },
                {},
            )

    def test_invalid_rectangles_indices_and_nested_values_rejected(self):
        for matrix, index in [
            ([], 0),
            ([[0.1, 0.9]], True),
            ([[0.1]], -1),
            ([[0.1]], 1),
            ([[0.1], [0.1, 0.9]], 0),
            ([{}], 0),
            ([[{}]], 0),
            ([[float("nan")]], 0),
            ([[1]] * 10001, 0),
            ([[1] * 1001], 0),
        ]:
            with (
                self.subTest(matrix=str(matrix)[:30], index=index),
                self.assertRaises(MissingEvidence),
            ):
                operand(
                    {
                        "operation": "column",
                        "args": [{"value": matrix}, {"value": index}],
                    },
                    {},
                )


if __name__ == "__main__":
    unittest.main()
