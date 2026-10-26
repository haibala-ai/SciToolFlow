"""Observed transform parameters bind scientific arrays without refitting them."""

import unittest
from evaluation.workflow import operand, MissingEvidence


class ColumnAffineTests(unittest.TestCase):
    def test_uses_actual_parameter_observations_and_preserves_row_order(self):
        context = {"nodes": {"s": {"output": {"mean": [10, 3], "scale": [2, 1]}}}}
        e = {
            "operation": "column_affine",
            "args": [
                {"value": [[12, 3], [8, 5]]},
                {"source": "node", "node": "s", "path": "/mean"},
                {"source": "node", "node": "s", "path": "/scale"},
            ],
        }
        self.assertEqual(operand(e, context), [[1.0, 0.0], [-1.0, 2.0]])
        context["nodes"]["s"]["output"]["mean"][0] = 8
        self.assertEqual(operand(e, context), [[2.0, 0.0], [0.0, 2.0]])
        with self.assertRaises(MissingEvidence):
            operand(e, {})

    def test_no_imputation_shape_repair_or_zero_scale_inference(self):
        cases = [
            ([], [], []),
            ([[1]], [], []),
            ([[1], [2, 3]], [0], [1]),
            ([[True]], [0], [1]),
            ([[None]], [0], [1]),
            ([[1]], [False], [1]),
            ([[1]], [0], [True]),
            ([[1]], [0], [0]),
            ([[1]], [0], [-1]),
            ([[1]], [0], [float("inf")]),
            ([[1]], [float("nan")], [1]),
            ([[1]], [0], [1, 2]),
            ([[1] * 101] * 100, [0] * 101, [1] * 101),
            ([[1e308]], [-1e308], [1]),
        ]
        for matrix, offset, scale in cases:
            with (
                self.subTest(matrix_shape=(len(matrix), len(offset))),
                self.assertRaises(MissingEvidence),
            ):
                operand(
                    {
                        "operation": "column_affine",
                        "args": [
                            {"value": matrix},
                            {"value": offset},
                            {"value": scale},
                        ],
                    },
                    {},
                )
        with self.assertRaises(MissingEvidence):
            operand({"operation": "column_affine", "args": [{"value": [[1]]}]}, {})


class ExpressionArityValidationTests(unittest.TestCase):
    def spec(self, left, target):
        return {
            "schema_version": "workflow.v1",
            "nodes": [
                {
                    "id": "s",
                    "alternatives": [
                        {
                            "tools": ["T"],
                            "output_rules": [
                                {"path": "", "op": "type", "value": "object"}
                            ],
                        }
                    ],
                }
            ],
            "outcomes": [
                {
                    "id": "result",
                    "left": left,
                    "op": "eq",
                    "value": target,
                    "evidence_nodes": ["s"],
                }
            ],
        }

    def test_bad_expression_is_a_specification_error_not_a_model_failure(self):
        from evaluation.workflow import validate_workflow

        bad = {
            "operation": "records_matching",
            "args": [
                {"value": []},
                {"value": "group"},
                {"value": "eq"},
                {"value": "A"},
            ],
        }
        with self.assertRaisesRegex(ValueError, "argument count"):
            validate_workflow(
                self.spec(
                    {
                        "operation": "array",
                        "args": [{"source": "answer", "path": "/record"}, bad],
                    },
                    [],
                )
            )

    def test_literal_scientific_record_is_not_parsed_as_expression(self):
        from evaluation.workflow import validate_workflow

        validate_workflow(
            self.spec(
                {"source": "answer", "path": "/record"},
                {"operation": "records_matching", "args": []},
            )
        )

    def test_misspelled_operation_is_rejected_before_model_scoring(self):
        from evaluation.workflow import validate_workflow

        spec = self.spec({"source": "answer", "path": "/record"}, 2)
        spec["outcomes"][0].pop("value")
        spec["outcomes"][0]["right"] = {
            "operation": "absolute",
            "args": [{"value": -2}],
        }
        with self.assertRaisesRegex(ValueError, "Unknown operand operation"):
            validate_workflow(spec)

    def test_schema_accepts_bounded_variadic_matrix_rows(self):
        import json
        from pathlib import Path
        from jsonschema import Draft202012Validator

        schema = json.loads(
            (
                Path(__file__).resolve().parents[2] / "evaluation/workflow/schema.json"
            ).read_text()
        )
        validator = Draft202012Validator(
            {"$ref": "#/$defs/operand", "$defs": schema["$defs"]}
        )
        expression = {"operation": "numeric_rows", "args": [{"value": [1, 2]}] * 5}
        validator.validate(expression)
        self.assertEqual(operand(expression, {}), [[1, 2]] * 5)
        with self.assertRaises(MissingEvidence):
            operand(
                {
                    "operation": "numeric_rows",
                    "args": [{"value": [1, 2]}, {"value": [3]}],
                },
                {},
            )

    def test_all_declared_fixed_arity_operations_reject_missing_arguments(self):
        from evaluation.workflow import validate_workflow

        for name in [
            "record_value",
            "join",
            "abs",
            "zero_pad_numeric_matrix",
            "curve_spec",
        ]:
            spec = self.spec({"source": "answer", "path": "/record"}, 2)
            spec["outcomes"][0].pop("value")
            spec["outcomes"][0]["right"] = {"operation": name, "args": []}
            with (
                self.subTest(operation=name),
                self.assertRaisesRegex(ValueError, "argument count"),
            ):
                validate_workflow(spec)
