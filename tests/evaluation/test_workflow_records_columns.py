"""Scientific row pairs must come from the actual matched record output."""

import copy
import unittest

from evaluation.workflow import MissingEvidence, operand, predicate


class RecordColumnEvidenceTest(unittest.TestCase):
    def test_explicit_identity_cannot_hide_behind_an_identity_free_route(self):
        expression = lambda records, field: {
            "operation": "record_field_presence",
            "args": [{"value": records}, {"value": field}],
        }
        self.assertEqual(
            operand(expression([{"id": "A"}, {}, {"id": None}], "id"), {}),
            [True, False, True],
        )
        self.assertEqual(
            operand(expression([{"id": "A"}, {}], "ID"), {}), [False, False]
        )
        for records, field in [
            ([], "id"),
            ([1], "id"),
            ([{}], ""),
            ([{}], ["id"]),
            ([{}] * 10001, "id"),
        ]:
            with self.assertRaises(MissingEvidence):
                operand(expression(records, field), {})

    def expression(self, records, columns):
        return {
            "operation": "records_columns",
            "args": [{"value": records}, {"value": columns}],
        }

    def test_actual_join_projection_preserves_pairing_keys_and_null(self):
        context = {
            "nodes": {
                "join": {
                    "output": {
                        "records": [
                            {"id": "B", "cover": 2, "soil.pH": 5.1, "optional": None},
                            {"id": "A", "cover": 7, "soil.pH": 4.3, "optional": 0},
                        ]
                    }
                }
            }
        }
        before = copy.deepcopy(context)
        expr = {
            "operation": "records_columns",
            "args": [
                {"source": "node", "node": "join", "path": "/records"},
                {"value": ["cover", "soil.pH", "optional"]},
            ],
        }
        self.assertEqual(operand(expr, context), [[2, 5.1, None], [7, 4.3, 0]])
        self.assertFalse(
            predicate(
                {
                    "left": expr,
                    "op": "multiset_equal",
                    "value": [[2, 4.3, None], [7, 5.1, 0]],
                },
                context,
            )
        )
        self.assertEqual(context, before)

    def test_missing_source_or_field_does_not_become_null(self):
        for expr in [
            self.expression([{"x": 1}], ["absent"]),
            {
                "operation": "records_columns",
                "args": [{"source": "node", "node": "absent"}, {"value": ["x"]}],
            },
        ]:
            with self.assertRaises(MissingEvidence):
                operand(expr, {})

    def test_caller_chosen_column_is_an_evidence_role_not_a_literal_name(self):
        expression = {
            "operation": "records_columns",
            "args": [
                {"source": "call_arguments", "path": "/records"},
                {
                    "operation": "scalar_array",
                    "args": [{"source": "call_arguments", "path": "/value_column"}],
                },
            ],
        }
        for name in ["delta", "change", "uptake change"]:
            context = {
                "call_arguments": {
                    "records": [{name: 2, "ignored": 99}, {name: -1}],
                    "value_column": name,
                }
            }
            self.assertEqual(operand(expression, context), [[2], [-1]])
            context["call_arguments"]["value_column"] = "absent"
            with self.assertRaises(MissingEvidence):
                operand(expression, context)

    def test_scalar_array_keeps_types_bounds_and_numeric_array_contract(self):
        expression = lambda values: {
            "operation": "scalar_array",
            "args": [{"value": v} for v in values],
        }
        self.assertEqual(
            operand(expression(["column", True, None, 2.5]), {}),
            ["column", True, None, 2.5],
        )
        for invalid in [[], [[]], [{}], [float("nan")], [float("inf")], [0] * 10001]:
            with self.assertRaises(MissingEvidence):
                operand(expression(invalid), {})
        with self.assertRaises(MissingEvidence):
            operand({"operation": "array", "args": [{"value": "column"}]}, {})

    def test_invalid_shape_nested_values_and_resource_bounds_reject(self):
        for records, columns in [
            ([], ["x"]),
            ([1], ["x"]),
            ([{}], []),
            ([{"x": 1}], ["x", "x"]),
            ([{"x": 1}], [True]),
            ([{"x": []}], ["x"]),
            ([{"x": {}}], ["x"]),
            ([{"x": float("nan")}], ["x"]),
            ([{"x": float("inf")}], ["x"]),
            ([{"x": 1}] * 10001, ["x"]),
            ([{"x": 1, "y": 2}] * 5001, ["x", "y"]),
        ]:
            with self.subTest(record_count=len(records), columns=columns):
                with self.assertRaises(MissingEvidence):
                    operand(self.expression(records, columns), {})


if __name__ == "__main__":
    unittest.main()
