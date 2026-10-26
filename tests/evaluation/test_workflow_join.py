"""Legacy delimited inputs must be grounded in the actual upstream strings."""

import copy
import unittest

from evaluation.workflow import MissingEvidence, operand, predicate


class JoinedEvidenceTest(unittest.TestCase):
    def test_actual_strings_order_separator_and_empty_values_preserved(self):
        context = {"nodes": {"parsed": {"output": {"sequences": ["ACGT", "AGT"]}}}}
        before = copy.deepcopy(context)
        expression = {
            "operation": "join",
            "args": [
                {"source": "node", "node": "parsed", "path": "/sequences"},
                {"value": "."},
            ],
        }
        self.assertEqual(operand(expression, context), "ACGT.AGT")
        self.assertFalse(
            predicate({"left": expression, "op": "eq", "value": "AGT.ACGT"}, context)
        )
        self.assertEqual(
            operand(
                {"operation": "join", "args": [{"value": ["", "A"]}, {"value": "|"}]},
                {},
            ),
            "|A",
        )
        self.assertEqual(context, before)

    def test_missing_source_never_replaced_with_expected_string(self):
        with self.assertRaises(MissingEvidence):
            operand(
                {
                    "operation": "join",
                    "args": [
                        {"source": "node", "node": "absent", "path": "/sequences"},
                        {"value": "."},
                    ],
                },
                {},
            )

    def test_no_implicit_stringification_or_unbounded_join(self):
        for args in [
            [],
            [["A"]],
            [[], "."],
            ["ACGT", "."],
            [["A", 1], "."],
            [["A", None], "."],
            [[True], "."],
            [[["A"]], "."],
            [["A"], 1],
            [["A"], "." * 1001],
            [["A"] * 1001, "."],
            [["A" * 2000000, "B"], ""],
        ]:
            with self.subTest(argument_types=[type(a).__name__ for a in args]):
                with self.assertRaises(MissingEvidence):
                    operand(
                        {"operation": "join", "args": [{"value": a} for a in args]}, {}
                    )


if __name__ == "__main__":
    unittest.main()
