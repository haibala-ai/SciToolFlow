import copy
import unittest
from evaluation.workflow.constants import compact, expand, digest, resolve
from evaluation.workflow import operand, validate_workflow, MissingEvidence


class ConstantTests(unittest.TestCase):
    def test_exact_round_trip_and_shared_storage(self):
        data = [[float(i), i / 3] for i in range(500)]
        spec = {
            "schema_version": "workflow.v1",
            "nodes": [
                {
                    "id": "n",
                    "capability": "n",
                    "alternatives": [
                        {
                            "tools": ["T"],
                            "input_rules": [
                                {
                                    "left": {"source": "call_arguments", "path": "/x"},
                                    "op": "eq",
                                    "right": {"value": data},
                                }
                            ],
                            "output_rules": [
                                {"path": "", "op": "eq", "right": {"value": data}}
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
                    "right": {"value": 1},
                    "evidence_nodes": ["n"],
                }
            ],
        }
        c = compact(spec)
        self.assertEqual(expand(c), spec)
        self.assertEqual(len(c["constants"]), 1)
        validate_workflow(c)
        expression = c["nodes"][0]["alternatives"][0]["input_rules"][0]["right"]
        self.assertEqual(operand(expression, {"constants": c["constants"]}), data)

    def test_tampered_or_missing_content_is_rejected(self):
        key = digest([1, 2, 3])
        expr = {"operation": "literal_constant", "args": [{"value": key}]}
        with self.assertRaises(MissingEvidence):
            operand(expr, {"constants": {}})
        from evaluation.workflow.constants import validate

        with self.assertRaises(ValueError):
            validate({key: [1, 2, 4]})

    def test_text_is_data_never_executed(self):
        text = "raise RuntimeError('must not execute')" * 100
        spec = {"nodes": [{"value": text}, {"value": text}]}
        c = compact(spec)
        self.assertEqual(resolve(c["nodes"][0], c["constants"]), text)
        self.assertEqual(expand(c), spec)


if __name__ == "__main__":
    unittest.main()
