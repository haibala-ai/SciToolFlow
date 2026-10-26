"""Cohort evidence follows complete actual records without a filter wrapper."""

import copy
import unittest

from evaluation.workflow import MissingEvidence, operand, predicate


def expression(records, conditions):
    return {
        "operation": "records_matching",
        "args": [{"value": records}, {"value": conditions}],
    }


class RecordMatchingTests(unittest.TestCase):
    def test_complete_source_selection_preserves_pairing_order_and_repeats(self):
        rows = [
            {"day": 1, "arm": "A", "x": 5, "y": 11},
            {"day": 2, "arm": "A", "x": 7, "y": 19},
            {"day": 1, "arm": "B", "x": 3, "y": 17},
            {"day": 1, "arm": "A", "x": 5, "y": 11},
        ]
        context = {"nodes": {"read": {"output": {"records": rows}}}}
        before = copy.deepcopy(context)
        selected = {
            "operation": "records_matching",
            "args": [
                {"source": "node", "node": "read", "path": "/records"},
                {"value": {"day": 1, "arm": "A"}},
            ],
        }
        project = {
            "operation": "records_columns",
            "args": [selected, {"value": ["x", "y"]}],
        }
        self.assertEqual(operand(project, context), [[5, 11], [5, 11]])
        self.assertFalse(
            predicate(
                {"left": project, "op": "multiset_equal", "value": [[5, 11]]}, context
            )
        )
        rows[0]["y"] = 13
        self.assertEqual(operand(project, context), [[5, 13], [5, 11]])
        rows[0]["y"] = 11
        self.assertEqual(context, before)

    def test_literal_typed_values_empty_selection_and_no_mutation(self):
        rows = [
            {"k": value, "nested_unselected": {"keep": [1, 2]}}
            for value in [True, 1, 1.0, "1", None, " A", "A", "a"]
        ]
        before = copy.deepcopy(rows)
        for condition, indices in [
            (True, [0]),
            (1, [1, 2]),
            ("1", [3]),
            (None, [4]),
            ("A", [6]),
            (".*", []),
        ]:
            with self.subTest(condition=condition):
                self.assertEqual(
                    operand(expression(rows, {"k": condition}), {}),
                    [rows[i] for i in indices],
                )
        self.assertEqual(rows, before)
        self.assertEqual(
            operand(expression([{"a.b": 1}], {"a.b": 1}), {}), [{"a.b": 1}]
        )

    def test_missing_field_cannot_be_hidden_by_another_mismatch(self):
        for rows in [[{"arm": "B"}], [{"arm": "A", "day": 1}, {"arm": "B"}]]:
            with self.assertRaises(MissingEvidence):
                operand(expression(rows, {"arm": "A", "day": 1}), {})

    def test_invalid_inputs_and_work_bounds_reject(self):
        bad = [
            ([], {"k": 1}),
            ([1], {"k": 1}),
            ([{}], {}),
            ([{"k": 1}], {"k": []}),
            ([{"k": 1}], {"k": {}}),
            ([{"k": float("nan")}], {"k": 1}),
            ([{"k": []}], {"k": None}),
            ([{"k": 1}], {"k": float("inf")}),
            ([{"k": 1}], {True: 1}),
            ([{"k": 1}] * 10001, {"k": 1}),
            ([{str(i): i for i in range(21)}], {str(i): i for i in range(21)}),
            ([{"a": 1, "b": 2, "c": 3}] * 6667, {"a": 1, "b": 2, "c": 3}),
            ([{"k": "a" * 2000000}], {"k": "a"}),
        ]
        for rows, conditions in bad:
            with self.subTest(rows=len(rows), fields=len(conditions)):
                with self.assertRaises(MissingEvidence):
                    operand(expression(rows, conditions), {})
        for args in [
            [],
            [{"value": [{"k": 1}]}],
            [{"value": [{"k": 1}]}, {"value": {"k": 1}}, {"value": 0}],
        ]:
            with self.assertRaises(MissingEvidence):
                operand({"operation": "records_matching", "args": args}, {})
