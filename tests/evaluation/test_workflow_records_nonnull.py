"""Complete-case evidence preserves explicit-null, identity and order boundaries."""

import copy
import unittest

from evaluation.workflow import MissingEvidence, operand, validate_workflow


def expr(rows, columns):
    return {
        "operation": "records_nonnull",
        "args": [{"value": rows}, {"value": columns}],
    }


class NonnullRecordsTests(unittest.TestCase):
    def test_only_explicit_null_is_missing(self):
        rows = [{"x": v, "id": i} for i, v in enumerate([0, False, "", "NA", None, 1])]
        before = copy.deepcopy(rows)
        self.assertEqual(operand(expr(rows, ["x"]), {}), rows[:4] + rows[5:])
        self.assertEqual(rows, before)

    def test_joint_fields_preserve_order_identity_and_duplicates(self):
        rows = [
            {"id": "b", "x": 0, "y": 2},
            {"id": "a", "x": None, "y": 1},
            {"id": "b", "x": 0, "y": 2},
            {"id": "c", "x": 3, "y": None},
        ]
        context = {"nodes": {"s": {"output": {"records": rows}}}}
        expression = {
            "operation": "records_nonnull",
            "args": [
                {"source": "node", "node": "s", "path": "/records"},
                {"value": ["x", "y"]},
            ],
        }
        self.assertEqual(operand(expression, context), [rows[0], rows[2]])
        expression["args"][1]["value"].reverse()
        self.assertEqual(operand(expression, context), [rows[0], rows[2]])

    def test_absent_fields_are_rejected_before_any_row_is_discarded(self):
        for rows in [[{"x": None}], [{"x": None, "y": 2}, {"x": None}]]:
            with self.assertRaises(MissingEvidence):
                operand(expr(rows, ["x", "y"]), {})

    def test_empty_cohort_is_valid_data(self):
        self.assertEqual(operand(expr([], ["x"]), {}), [])
        self.assertEqual(operand(expr([{"x": None}], ["x"]), {}), [])

    def test_bounded_distinct_fields_and_object_rows(self):
        for rows, columns in [
            ([1], ["x"]),
            ([{"x": 1}], []),
            ([{"x": 1}], ["x", "x"]),
            ([{"x": 1}], [1]),
            ([{"x": 1}], [""]),
            ([{"x": 1}] * 10001, ["x"]),
            ([{"x": 1, "y": 2}] * 5001, ["x", "y"]),
        ]:
            with self.subTest(columns=columns):
                with self.assertRaises(MissingEvidence):
                    operand(expr(rows, columns), {})

    def test_structural_validation_rejects_wrong_arity(self):
        spec = {
            "schema_version": "workflow.v1",
            "nodes": [
                {
                    "id": "n",
                    "alternatives": [
                        {
                            "tools": ["T"],
                            "output_rules": [
                                {
                                    "left": expr([{"x": 1}], ["x"]),
                                    "op": "type",
                                    "value": "array",
                                }
                            ],
                        }
                    ],
                }
            ],
            "outcomes": [
                {
                    "id": "a",
                    "left": {"source": "answer", "path": "/a"},
                    "op": "eq",
                    "value": 1,
                    "evidence_nodes": ["n"],
                }
            ],
        }
        validate_workflow(spec)
        spec["nodes"][0]["alternatives"][0]["output_rules"][0]["left"]["args"].pop()
        with self.assertRaises(ValueError):
            validate_workflow(spec)


if __name__ == "__main__":
    unittest.main()
