"""Explicit nullable numeric semantics never replace absent scientific evidence."""

import copy
import unittest
from evaluation.workflow import MissingEvidence, operand, validate_workflow


class NumericNullDefaultTests(unittest.TestCase):
    def expression(self, value, fallback):
        return dict(
            operation="coalesce_number", args=[dict(value=value), dict(value=fallback)]
        )

    def test_only_explicit_null_uses_finite_fallback(self):
        for value, expected in [(None, 1), (0, 0), (-2, -2), (0.5, 0.5)]:
            self.assertEqual(operand(self.expression(value, 1), {}), expected)

    def test_observed_null_does_not_mutate_actual_arguments(self):
        context = dict(call_arguments=dict(bounds=[[0, None]]))
        before = copy.deepcopy(context)
        e = dict(
            operation="coalesce_number",
            args=[dict(source="call_arguments", path="/bounds/0/1"), dict(value=1)],
        )
        self.assertEqual(operand(e, context), 1)
        self.assertEqual(context, before)

    def test_absent_selector_is_not_imputed(self):
        for selector in [
            dict(source="call_arguments", path="/absent"),
            dict(source="node", node="absent", path="/value"),
        ]:
            with self.assertRaises(MissingEvidence):
                operand(
                    dict(operation="coalesce_number", args=[selector, dict(value=0)]),
                    dict(call_arguments={}),
                )

    def test_zero_is_not_truthy_default_and_invalid_types_fail(self):
        for value, fallback in [
            (False, 1),
            (True, 1),
            ("0", 1),
            ([], 1),
            ({}, 1),
            (float("nan"), 1),
            (float("inf"), 1),
            (None, None),
            (None, False),
            (None, "1"),
            (0, float("nan")),
        ]:
            with (
                self.subTest(value=str(value), fallback=str(fallback)),
                self.assertRaises(MissingEvidence),
            ):
                operand(self.expression(value, fallback), {})

    def test_invalid_fallback_evidence_is_not_hidden(self):
        with self.assertRaises(MissingEvidence):
            operand(
                dict(
                    operation="coalesce_number",
                    args=[dict(value=3), dict(source="call_output", path="/absent")],
                ),
                dict(call_output={}),
            )

    def test_static_arity_is_enforced(self):
        for count in [0, 1, 3]:
            with self.assertRaises(ValueError):
                validate_workflow(
                    dict(
                        schema_version="workflow.v1",
                        nodes=[
                            dict(
                                id="n",
                                alternatives=[
                                    dict(
                                        tools=["DescribeNumericData"],
                                        output_rules=[
                                            dict(
                                                left=dict(
                                                    operation="coalesce_number",
                                                    args=[dict(value=None)] * count,
                                                ),
                                                op="eq",
                                                value=1,
                                            )
                                        ],
                                    )
                                ],
                            )
                        ],
                        outcomes=[
                            dict(
                                id="a",
                                left=dict(source="answer", path="/value"),
                                op="eq",
                                value=1,
                            )
                        ],
                    )
                )


if __name__ == "__main__":
    unittest.main()
