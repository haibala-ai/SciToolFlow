"""Explicit decoding preserves raw evidence and rejects ambiguous JSON."""

import unittest
import json

from evaluation.workflow import MissingEvidence, operand, predicate, score_workflow
from tests.support.workflows import fixture, run


class JsonValueTests(unittest.TestCase):
    def resolve(self, raw, path):
        return operand(
            {"operation": "json_value", "args": [{"value": raw}, {"value": path}]}, {}
        )

    def test_structured_value_null_and_escaped_pointer(self):
        raw = '{"source_sha256":"abc","a/b":[3,null]}'
        self.assertEqual(self.resolve(raw, "/source_sha256"), "abc")
        self.assertEqual(self.resolve(raw, "/a~1b/0"), 3)
        self.assertIsNone(self.resolve(raw, "/a~1b/1"))
        self.assertEqual(raw, '{"source_sha256":"abc","a/b":[3,null]}')

    def test_invalid_duplicate_nonfinite_or_large_evidence_rejected(self):
        for raw in [
            "not json",
            '{"a":1,"a":2}',
            '{"a":NaN}',
            '{"a":1e999}',
            " " * 2000001,
            {},
        ]:
            with self.subTest(raw=str(raw)[:40]), self.assertRaises(MissingEvidence):
                self.resolve(raw, "")

    def test_invalid_or_missing_pointer_rejected(self):
        for path in ["source", "/~2", "/~", "/absent", "/v/01"]:
            with self.subTest(path=path), self.assertRaises(MissingEvidence):
                self.resolve('{"v":[1,2]}', path)

    def test_real_raw_call_output_remains_a_string(self):
        raw = '{"source_sha256":"recorded-source"}'
        rule = {
            "left": {
                "operation": "json_value",
                "args": [{"source": "call_output"}, {"value": "/source_sha256"}],
            },
            "op": "eq",
            "value": "recorded-source",
        }
        context = {"call_output": raw}
        self.assertTrue(predicate(rule, context))
        self.assertEqual(context["call_output"], raw)

    def test_schema_and_capability_score_accept_explicit_json_decoding(self):
        reference, prediction = fixture(), run()
        reference["evaluation"]["nodes"][2]["alternatives"][0]["output_rules"] = [
            {
                "left": {
                    "operation": "json_value",
                    "args": [{"source": "call_output"}, {"value": "/ranking"}],
                },
                "op": "type",
                "value": "array",
            }
        ]
        reference["evaluation"]["outcomes"][0]["right"]["args"] = [
            {
                "operation": "json_value",
                "args": [{"source": "node", "node": "score"}, {"value": "/ranking"}],
            }
        ]
        prediction["calls"][2]["output"] = json.dumps(prediction["calls"][2]["output"])
        self.assertTrue(score_workflow(reference, prediction)["joint_pass"])
        self.assertIsInstance(prediction["calls"][2]["output"], str)


if __name__ == "__main__":
    unittest.main()
