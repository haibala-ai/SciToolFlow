"""Real legacy text evidence must bind downstream numeric arguments exactly."""

import json
from pathlib import Path
import unittest
from jsonschema import Draft202012Validator
from evaluation.workflow import MissingEvidence, operand, predicate


def expr(operation, *args):
    return {"operation": operation, "args": list(args)}


def literal(value):
    return {"value": value}


class TextMatrixEvidenceTests(unittest.TestCase):
    def test_actual_legacy_output_scientific_notation_and_changed_data(self):
        start = "- **Lattice Parameters**: `"
        text = "Header\n" + start + "5.0 1e-9 -2.5E-3\n0 4. .2\n1 0 +3`\n"
        parsing = expr(
            "numeric_matrix",
            expr(
                "text_between",
                {"source": "node", "node": "cell"},
                literal(start),
                literal("`"),
            ),
        )
        ctx = {
            "nodes": {"cell": {"output": text}},
            "call_arguments": {
                "values": [[5.0, 1e-9, -0.0025], [0.0, 4.0, 0.2], [1.0, 0.0, 3.0]]
            },
        }
        rule = {
            "left": {"source": "call_arguments", "path": "/values"},
            "op": "eq",
            "right": parsing,
            "atol": 1e-14,
        }
        self.assertTrue(predicate(rule, ctx))
        ctx["nodes"]["cell"]["output"] = text.replace("5.0", "5.1")
        self.assertFalse(predicate(rule, ctx))
        with self.assertRaises(MissingEvidence):
            operand(parsing, {})

    def test_markers_cannot_fallback_to_expected_or_ambiguous_text(self):
        for raw, start, end in [
            ("none", "A", "B"),
            ("A1B A2B", "A", "B"),
            ("A1", "A", "B"),
            ("A1B", "", "B"),
            ("A1B", "A", ""),
            (1, "A", "B"),
            ("A" + "1" * 2000001 + "B", "A", "B"),
        ]:
            with self.subTest(raw=str(raw)[:30]), self.assertRaises(MissingEvidence):
                operand(
                    expr("text_between", literal(raw), literal(start), literal(end)), {}
                )

    def test_only_rectangular_finite_whitespace_numbers(self):
        for text in [
            "",
            "1 2\n3",
            "1 2\n\n3 4",
            "1,2",
            "NaN",
            "inf",
            "1e999",
            "1_000",
            '__import__("os")',
            "True",
            "1;2",
            "1 " * 1001,
            "1\n" * 1001,
            ("1 " * 11 + "\n") * 910,
        ]:
            with self.subTest(text=text[:30]), self.assertRaises(MissingEvidence):
                operand(expr("numeric_matrix", literal(text)), {})
        self.assertEqual(
            operand(expr("numeric_matrix", literal(" \t1e-2 -0\n+.5 4.\n")), {}),
            [[0.01, -0.0], [0.5, 4.0]],
        )

    def test_declared_expression_schema_matches_vector_bounds(self):
        schema = json.loads(
            (
                Path(__file__).resolve().parents[2] / "evaluation/workflow/schema.json"
            ).read_text()
        )
        validator = Draft202012Validator(
            {"$ref": "#/$defs/operand", "$defs": schema["$defs"]}
        )
        validator.validate(expr("array", *[literal(i) for i in range(8)]))
        validator.validate(expr("numeric_matrix", literal("1 0\n0 1")))
        validator.validate(
            expr("text_between", literal("A1B"), literal("A"), literal("B"))
        )
        self.assertTrue(list(validator.iter_errors(expr("add", *[literal(1)] * 5))))
        self.assertTrue(
            list(validator.iter_errors(expr("array", *[literal(1)] * 10001)))
        )


if __name__ == "__main__":
    unittest.main()
