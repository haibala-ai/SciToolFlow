import unittest
from unittest.mock import patch
from evaluation.workflow import operand, MissingEvidence
from evaluation.workflow.values import _json_size
import json


class EvidenceCacheTests(unittest.TestCase):
    def test_one_size_check_per_same_immutable_object_within_score(self):
        value = [{"x": i} for i in range(1000)]
        context = {"_json_sizes": {}}
        with patch("evaluation.workflow.values.json.dumps", wraps=json.dumps) as dump:
            self.assertEqual(_json_size(value, context), _json_size(value, context))
            self.assertEqual(dump.call_count, 1)
        value[0]["x"] = "changed"
        self.assertNotEqual(
            _json_size(value, {"_json_sizes": {}}),
            _json_size([{"x": i} for i in range(1000)], {"_json_sizes": {}}),
        )

    def test_new_score_and_standalone_checks_do_not_reuse_stale_validation(self):
        value = {"x": 1}
        self.assertGreater(_json_size(value, {"_json_sizes": {}}), 0)
        value["x"] = float("nan")
        with self.assertRaises(ValueError):
            _json_size(value, {"_json_sizes": {}})
        with self.assertRaises(MissingEvidence):
            operand(
                {
                    "operation": "value_at_pointer",
                    "args": [{"value": value}, {"value": "/x"}],
                },
                {},
            )
