"""Composition evidence must follow the actual source sequence, not a gold count."""

import unittest
from evaluation.workflow import MissingEvidence, operand


class CharacterCountTest(unittest.TestCase):
    def test_actual_sequence_change_updates_count_and_missing_evidence_fails(self):
        spec = {
            "operation": "count_occurrences",
            "args": [
                {"source": "node", "node": "observed", "path": "/sequence"},
                {"value": "C"},
            ],
        }
        context = {"nodes": {"observed": {"output": {"sequence": "ACCCY"}}}}
        self.assertEqual(operand(spec, context), 3)
        context["nodes"]["observed"]["output"]["sequence"] = "AY"
        self.assertEqual(operand(spec, context), 0)
        with self.assertRaises(MissingEvidence):
            operand(spec, {})

    def test_count_is_exact_case_sensitive_codepoint_not_regex_or_empty_substring(self):
        def count(text, char):
            return operand(
                {
                    "operation": "count_occurrences",
                    "args": [{"value": text}, {"value": char}],
                },
                {},
            )

        self.assertEqual(count("CcC", "C"), 2)
        self.assertEqual(count("a.a.*", "."), 2)
        self.assertEqual(count("éxé", "é"), 2)
        self.assertEqual(count("", "C"), 0)
        for text, char in [
            ("CC", ""),
            ("CCC", "CC"),
            ("CC", None),
            (None, "C"),
            (["C"], "C"),
            ("C" * 2000001, "C"),
        ]:
            with self.subTest(char=char), self.assertRaises(MissingEvidence):
                count(text, char)
