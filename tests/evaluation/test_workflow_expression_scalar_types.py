"""Catch provably impossible expression types before scoring valid routes."""

import unittest

from evaluation.workflow import operand, validate_workflow


def literal(value):
    return {"value": value}


def expression(name, *args):
    return {"operation": name, "args": list(args)}


def specification(value):
    return {
        "schema_version": "workflow.v1",
        "nodes": [
            {
                "id": "calculation",
                "alternatives": [
                    {
                        "tools": ["MatrixMultiply"],
                        "input_rules": [{"path": "/right", "op": "eq", "right": value}],
                        "output_rules": [
                            {"path": "/product", "op": "type", "value": "array"}
                        ],
                    }
                ],
            }
        ],
        "outcomes": [
            {
                "id": "result",
                "left": {"source": "answer", "path": "/value"},
                "op": "eq",
                "value": 1,
                "evidence_nodes": ["calculation"],
            }
        ],
    }


class ExpressionScalarTypeTests(unittest.TestCase):
    def test_nested_array_rejected_and_matrix_constructor_retains_orientation(self):
        a = expression("array", literal(2))
        b = expression("array", literal(1))
        for name in ["array", "scalar_array"]:
            with (
                self.subTest(name=name),
                self.assertRaisesRegex(ValueError, "Scalar operand"),
            ):
                validate_workflow(specification(expression(name, a, b)))
        matrix = expression("numeric_rows", a, b)
        validate_workflow(specification(matrix))
        self.assertEqual(operand(matrix, {}), [[2], [1]])

    def test_numeric_and_json_scalar_contracts_differ(self):
        for value in [True, None, "1", [1], {"value": 1}]:
            with (
                self.subTest(value=value),
                self.assertRaisesRegex(ValueError, "Scalar operand"),
            ):
                validate_workflow(specification(expression("array", literal(value))))
        validate_workflow(
            specification(
                expression("scalar_array", literal(None), literal(True), literal("1"))
            )
        )

    def test_unknown_observed_type_is_not_guessed_from_path(self):
        value = expression(
            "array", {"source": "node", "node": "calculation", "path": "/number"}
        )
        # Use an answer target to keep this a valid explicit dependency context.
        spec = specification(literal([1]))
        spec["outcomes"][0]["right"] = value
        spec["outcomes"][0].pop("value")
        validate_workflow(spec)
        self.assertEqual(
            operand(value, {"nodes": {"calculation": {"output": {"number": 3}}}}), [3]
        )

    def test_literal_scientific_data_is_not_recursively_interpreted_as_code(self):
        payload = {"operation": "array", "args": [{"value": [1]}]}
        validate_workflow(specification(literal(payload)))


if __name__ == "__main__":
    unittest.main()
