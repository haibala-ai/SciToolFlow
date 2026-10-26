"""Equivalent source-grounded arithmetic must not force incidental tool wrappers."""

import math
import unittest

from evaluation.workflow import MissingEvidence, operand


def expression(operation, *args):
    return {"operation": operation, "args": list(args)}


class NumericExpressionTests(unittest.TestCase):
    def test_actual_source_log1p_vector_changes_with_actual_observations(self):
        source = {"nodes": {"read": {"output": {"counts": [2, 5]}}}}
        values = expression(
            "array",
            *[
                expression(
                    "natural_log",
                    expression(
                        "add",
                        {"value": 1},
                        {"source": "node", "node": "read", "path": f"/counts/{i}"},
                    ),
                )
                for i in range(2)
            ],
        )
        self.assertEqual(operand(values, source), [math.log(3), math.log(6)])
        source["nodes"]["read"]["output"]["counts"][0] = 8
        self.assertEqual(operand(values, source), [math.log(9), math.log(6)])
        with self.assertRaises(MissingEvidence):
            operand(values, {})

    def test_natural_log_domain_and_arity(self):
        self.assertEqual(operand(expression("natural_log", {"value": 1}), {}), 0)
        for value in [0, -1, True, None, "1", float("nan"), float("inf"), [1]]:
            with self.subTest(value=value), self.assertRaises(MissingEvidence):
                operand(expression("natural_log", {"value": value}), {})
        with self.assertRaises(ValueError):
            operand(expression("natural_log"), {})

    def test_numeric_array_bounds_and_scalar_types(self):
        for values in [[], [True], [None], [[1]], [float("nan")], ["1"]]:
            with self.subTest(values=values), self.assertRaises(MissingEvidence):
                operand(expression("array", *[{"value": v} for v in values]), {})
        with self.assertRaises(MissingEvidence):
            operand(expression("array", *[{"value": 1}] * 10001), {})
        self.assertEqual(operand(expression("array", {"value": 0}), {}), [0])

    def test_exponential_uses_observed_scalar_and_rejects_invalid_results(self):
        source = {"nodes": {"fit": {"output": {"log_prediction": 2}}}}
        value = expression(
            "exponential",
            {"source": "node", "node": "fit", "path": "/log_prediction"},
        )
        self.assertEqual(operand(value, source), math.exp(2))
        source["nodes"]["fit"]["output"]["log_prediction"] = -1
        self.assertEqual(operand(value, source), math.exp(-1))
        with self.assertRaises(MissingEvidence):
            operand(value, {})
        for invalid in [True, None, "1", float("nan"), float("inf"), [1], 1000, -1000]:
            with self.subTest(value=invalid), self.assertRaises(MissingEvidence):
                operand(expression("exponential", {"value": invalid}), {})
        with self.assertRaises(ValueError):
            operand(expression("exponential"), {})

    def test_source_grounded_zero_extension_keeps_every_original_cell(self):
        context = {"nodes": {"raw": {"output": {"rows": [[1, -2], [3, 4]]}}}}
        source = {"source": "node", "node": "raw", "path": "/rows"}
        value = expression(
            "zero_pad_numeric_matrix", source, {"value": 3}, {"value": 4}
        )
        self.assertEqual(
            operand(value, context), [[1, -2, 0, 0], [3, 4, 0, 0], [0, 0, 0, 0]]
        )
        context["nodes"]["raw"]["output"]["rows"][1][1] = 9
        self.assertEqual(operand(value, context)[1][1], 9)
        with self.assertRaises(MissingEvidence):
            operand(value, {})
        rows = expression("numeric_rows", {"value": [1, 2]}, {"value": [3, 4]})
        self.assertEqual(operand(rows, {}), [[1, 2], [3, 4]])

    def test_zero_extension_rejects_truncation_bad_dimensions_and_non_numeric_cells(
        self,
    ):
        for matrix in [
            [],
            [[]],
            [[1], [2, 3]],
            [[True]],
            [[None]],
            [["1"]],
            [[float("nan")]],
            [[float("inf")]],
        ]:
            with self.subTest(matrix=matrix), self.assertRaises(MissingEvidence):
                operand(
                    expression(
                        "zero_pad_numeric_matrix",
                        {"value": matrix},
                        {"value": 3},
                        {"value": 3},
                    ),
                    {},
                )
        for rows, columns in [
            (1, 2),
            (2, 1),
            (True, 2),
            (2, 2.0),
            (2, 1001),
            (10001, 2),
            (100, 101),
        ]:
            with (
                self.subTest(rows=rows, columns=columns),
                self.assertRaises(MissingEvidence),
            ):
                operand(
                    expression(
                        "zero_pad_numeric_matrix",
                        {"value": [[1, 2], [3, 4]]},
                        {"value": rows},
                        {"value": columns},
                    ),
                    {},
                )
        for args in [[], [{"value": [[1]]}], [{"value": [[1]]}, {"value": 1}]]:
            with self.assertRaises(MissingEvidence):
                operand(expression("zero_pad_numeric_matrix", *args), {})


if __name__ == "__main__":
    unittest.main()
