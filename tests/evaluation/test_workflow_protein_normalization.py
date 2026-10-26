"""Source identity survives legitimate tool normalization, not sequence edits."""

import copy
import unittest

from evaluation.workflow import MissingEvidence, operand, predicate


def normalized(source):
    return {"operation": "normalize_protein_strings", "args": [source]}


class ProteinNormalizationTests(unittest.TestCase):
    def test_complete_source_binding_and_multiplicity(self):
        rule = {
            "left": normalized({"source": "call_arguments", "path": "/sequences"}),
            "op": "multiset_equal",
            "right": normalized({"source": "inputs", "path": "/sequences"}),
        }
        context = {
            "inputs": {"sequences": ["ACD", "GG", "ACD"]},
            "call_arguments": {"sequences": [" aCd** \n", "g\u00a0g", "acd*"]},
        }
        self.assertTrue(predicate(rule, context))
        context["call_arguments"]["sequences"][-1] = "ACE"
        self.assertFalse(predicate(rule, context))
        context["call_arguments"]["sequences"] = ["ACD", "GG"]
        self.assertFalse(predicate(rule, context))

    def test_legacy_public_normalization_preserves_list(self):
        source = [" aC d* \n", "G g **", "\u00a0ac\t", "AAA", "aaa", "\u017f"]
        original = copy.deepcopy(source)
        self.assertEqual(
            operand(normalized({"value": source}), {}),
            ["ACD", "GG", "AC", "AAA", "AAA", "S"],
        )
        self.assertEqual(source, original)
        self.assertEqual(
            operand(normalized({"value": ["A" * 10000]}), {}), ["A" * 10000]
        )

    def test_types_budgets_and_internal_symbols_fail(self):
        bad = [
            [],
            [[]],
            ["AAAA"],
            [[False]],
            [[1]],
            [[None]],
            [[""]],
            [["***"]],
            [["AA*AA"]],
            [["AX"]],
            [["A" * 10001]],
            [["A"] * 101],
            [["A" + " " * 2000000]],
            [["A"], ["A"]],
            [["A-A"]],
            [["A>header"]],
        ]
        for arguments in bad:
            with self.subTest(summary=str(arguments)[:50]):
                with self.assertRaises(MissingEvidence):
                    operand(
                        {
                            "operation": "normalize_protein_strings",
                            "args": [{"value": a} for a in arguments],
                        },
                        {},
                    )
