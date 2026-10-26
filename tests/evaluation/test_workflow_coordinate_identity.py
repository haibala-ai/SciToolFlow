"""Whole coordinate-set identity follows IDs; independent reorders cannot pass."""

import copy
import unittest
from evaluation.workflow import MissingEvidence, operand, predicate


def lookup(ids, sets, identity):
    return {
        "operation": "coordinate_set_for_id",
        "args": [{"value": ids}, {"value": sets}, {"value": identity}],
    }


class CoordinateIdentityTests(unittest.TestCase):
    def setUp(self):
        self.a = [[0, 0, 0], [1, 0, 0], [0, 2, 0]]
        self.b = [[0, 0, 0], [2, 0, 0], [0, 4, 0]]

    def test_joint_set_reorder_keeps_identity_independent_reorder_does_not(self):
        expected = {"value": self.a}
        for ids, sets in [
            (["a", "b"], [self.a, self.b]),
            (["b", "a"], [self.b, self.a]),
        ]:
            self.assertTrue(
                predicate(
                    {"left": lookup(ids, sets, "a"), "op": "eq", "right": expected}, {}
                )
            )
        for ids, sets in [
            (["b", "a"], [self.a, self.b]),
            (["a", "b"], [self.b, self.a]),
        ]:
            self.assertFalse(
                predicate(
                    {"left": lookup(ids, sets, "a"), "op": "eq", "right": expected}, {}
                )
            )

    def test_complete_points_order_scale_and_live_actual_binding(self):
        context = {
            "nodes": {
                "batch": {"arguments": {"ids": ["a", "b"], "sets": [self.a, self.b]}}
            }
        }
        expression = {
            "operation": "coordinate_set_for_id",
            "args": [
                {"source": "node_arguments", "node": "batch", "path": "/ids"},
                {"source": "node_arguments", "node": "batch", "path": "/sets"},
                {"value": "b"},
            ],
        }
        self.assertEqual(operand(expression, context), self.b)
        for changed in [
            [self.b[1], self.b[0], self.b[2]],
            [[x * 10 for x in p] for p in self.b],
        ]:
            context["nodes"]["batch"]["arguments"]["sets"][1] = changed
            self.assertNotEqual(operand(expression, context), self.b)
        before = copy.deepcopy(self.a)
        selected = operand(lookup(["a", "b"], [self.a, self.b], "a"), {})
        selected[0][0] = 99
        self.assertEqual(self.a, before)

    def test_all_input_sets_validated_not_only_the_requested_one(self):
        for bad in [True, None, "1", float("nan"), float("inf"), 10**1000]:
            wrong = copy.deepcopy(self.b)
            wrong[0][0] = bad
            with self.subTest(bad=repr(bad)), self.assertRaises(MissingEvidence):
                operand(lookup(["a", "b"], [self.a, wrong], "a"), {})
        for ids, sets, identity in [
            (["a", "a"], [self.a, self.b], "a"),
            (["a", 1], [self.a, self.b], "a"),
            (["a", "b"], [self.a, self.b], "missing"),
            (["a", "b"], [self.a, self.b[:2]], "a"),
            (["a", "b"], [self.a, [[0, 0]] * 3], "a"),
            (["a"], [self.a], "a"),
        ]:
            with (
                self.subTest(ids=ids, identity=identity),
                self.assertRaises(MissingEvidence),
            ):
                operand(lookup(ids, sets, identity), {})

    def test_bounds_and_arity(self):
        for ids, sets in [
            ([str(i) for i in range(21)], [self.a] * 21),
            (["a", "b"], [[[0, 0, 0]] * 257] * 2),
            ([str(i) for i in range(20)], [[[0, 0, 0]] * 167] * 20),
        ]:
            with self.assertRaises(MissingEvidence):
                operand(lookup(ids, sets, ids[0]), {})
        ids = [str(i) for i in range(20)]
        sets = [[[0, 0, 0]] * 166] * 20
        self.assertEqual(len(operand(lookup(ids, sets, "19"), {})), 166)
        for args in [[], [{"value": ["a", "b"]}]]:
            with self.assertRaises(MissingEvidence):
                operand({"operation": "coordinate_set_for_id", "args": args}, {})


if __name__ == "__main__":
    unittest.main()
