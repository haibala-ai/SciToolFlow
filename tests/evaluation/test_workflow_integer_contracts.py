"""Integer answer identities stay exact without tightening continuous fields."""

import copy
import math
import unittest

from evaluation.authoring.integer_contracts import apply
from evaluation.workflow import predicate


class IntegerAnswerContractTests(unittest.TestCase):
    def fixture(self):
        public = {
            "answer_schema": {
                "type": "object",
                "properties": {
                    "count": {"type": "integer"},
                    "mass": {"type": "number"},
                    "groups": {
                        "type": "object",
                        "additionalProperties": {"type": "integer"},
                    },
                },
            }
        }

        def outcome(key, value):
            return {
                "id": key,
                "left": {"source": "answer", "path": "/" + key},
                "op": "eq",
                "value": value,
                "atol": 1e-7,
                "rtol": 1e-6,
            }

        hidden = {
            "evaluation": {
                "outcomes": [
                    outcome("count", 0),
                    outcome("mass", 2),
                    outcome("groups", {"A": 3, "B": 12}),
                ]
            }
        }
        return public, hidden

    def test_public_integer_counts_reject_fractional_and_boolean_values(self):
        public, h = self.fixture()
        apply(public, h)
        rule = h["evaluation"]["outcomes"][0]
        for value in [1e-9, math.nextafter(0, 1), True, False, 1, -1]:
            with self.subTest(value=value):
                self.assertFalse(predicate(rule, {"answer": {"count": value}}))
        self.assertTrue(predicate(rule, {"answer": {"count": 0}}))
        self.assertTrue(predicate(rule, {"answer": {"count": 0.0}}))

    def test_count_map_is_exact_and_continuous_mass_tolerance_is_retained(self):
        public, h = self.fixture()
        before = copy.deepcopy(public)
        apply(public, h)
        mass, groups = h["evaluation"]["outcomes"][1:]
        self.assertTrue(predicate(mass, {"answer": {"mass": 2 + 1e-7}}))
        self.assertFalse(
            predicate(groups, {"answer": {"groups": {"A": 3 + 1e-9, "B": 12}}})
        )
        self.assertEqual(public, before)

    def test_mixed_targets_are_reported_without_tightening_continuous_leaf(self):
        public = {
            "answer_schema": {
                "properties": {
                    "result": {
                        "type": "object",
                        "properties": {
                            "n": {"type": "integer"},
                            "mean": {"type": "number"},
                        },
                    }
                }
            }
        }
        h = {
            "evaluation": {
                "outcomes": [
                    {
                        "id": "result",
                        "left": {"source": "answer", "path": "/result"},
                        "op": "eq",
                        "value": {"n": 3, "mean": 2.5},
                        "atol": 1e-7,
                        "rtol": 1e-6,
                    }
                ]
            }
        }
        decisions = apply(public, h)
        self.assertEqual(
            decisions[0]["status"],
            "mixed_continuous_and_integer_target_requires_leafwise_review",
        )
        self.assertEqual(h["evaluation"]["outcomes"][0]["rtol"], 1e-6)


if __name__ == "__main__":
    unittest.main()
