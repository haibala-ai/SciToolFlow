"""Finite numbers, missing execution versus source ambiguity, and bounded slices."""

import unittest
from evaluation.workflow import operand, predicate, score_workflow, MissingEvidence
from tests.support.workflows import fixture, run


class WorkflowBoundaryTest(unittest.TestCase):
    def test_nonfinite_does_not_pass_negated_comparison(self):
        for value in [
            float("nan"),
            float("inf"),
            -float("inf"),
            [float("nan")],
            {"value": float("inf")},
        ]:
            self.assertFalse(predicate({"op": "ne", "value": 0}, {}, value))
        self.assertTrue(predicate({"op": "ne", "value": 0}, {}, 1))

    def test_reduction_overflow_is_missing_evidence(self):
        for op in ["sum", "mean"]:
            with self.assertRaises(MissingEvidence):
                operand({"operation": op, "args": [{"value": [1e308, 1e308]}]}, {})

    def branch_fixture(self):
        ref, prediction = fixture(), run()
        ref["evaluation"]["branches"] = [
            {
                "id": "confirm",
                "when": {
                    "left": {"source": "node", "node": "audit", "path": "/decision"},
                    "op": "eq",
                    "value": True,
                },
            }
        ]
        ref["evaluation"]["nodes"][-1]["branch"] = "confirm"
        prediction["calls"][1]["output"]["decision"] = True
        return ref, prediction

    def test_unexecuted_prerequisite_is_failure_not_pending(self):
        ref, prediction = self.branch_fixture()
        prediction["calls"].pop(1)
        result = score_workflow(ref, prediction)
        self.assertFalse(result["joint_pass"])
        self.assertFalse(result["pending_review"])
        self.assertEqual(
            result["unresolved_conditions"][0]["reason"],
            "missing_prerequisite_execution",
        )

    def test_executed_prerequisite_missing_field_remains_independent_pending(self):
        ref, prediction = self.branch_fixture()
        prediction["calls"][1]["output"].pop("decision")
        result = score_workflow(ref, prediction)
        self.assertFalse(result["joint_pass"])
        self.assertTrue(result["pending_review"])
        self.assertIn("unavailable_condition_value", result["pending_review_reasons"])

    def test_no_prediction_is_never_pending_for_unexecuted_condition(self):
        ref, _ = self.branch_fixture()
        result = score_workflow(ref, None)
        self.assertFalse(result["pending_review"])
        self.assertFalse(result["joint_pass"])

    def test_slice_string_and_list_are_half_open_and_do_not_mutate_source(self):
        for source, expected in [("ABCDEFGH", "ABCD"), ([1, 2, 3, 4, 5], [1, 2, 3, 4])]:
            result = operand(
                {
                    "operation": "slice",
                    "args": [{"value": source}, {"value": 0}, {"value": 4}],
                },
                {},
            )
            self.assertEqual(result, expected)
            self.assertEqual(len(source), 8 if isinstance(source, str) else 5)

    def test_slice_rejects_negative_boolean_float_reversed_and_outside_indices(self):
        for start, stop in [(-1, 4), (False, 4), (0, True), (0.0, 4), (4, 2), (0, 9)]:
            with self.assertRaises(MissingEvidence):
                operand(
                    {
                        "operation": "slice",
                        "args": [
                            {"value": "ABCDEFGH"},
                            {"value": start},
                            {"value": stop},
                        ],
                    },
                    {},
                )
        with self.assertRaises(MissingEvidence):
            operand(
                {
                    "operation": "slice",
                    "args": [{"value": 3}, {"value": 0}, {"value": 1}],
                },
                {},
            )

    def test_slice_may_return_empty_but_does_not_replace_domain_validation(self):
        self.assertEqual(
            operand(
                {
                    "operation": "slice",
                    "args": [{"value": "ABCD"}, {"value": 2}, {"value": 2}],
                },
                {},
            ),
            "",
        )
        self.assertEqual(
            operand(
                {
                    "operation": "slice",
                    "args": [{"value": [1, 2]}, {"value": 2}, {"value": 2}],
                },
                {},
            ),
            [],
        )


class RequiredAssignmentTest(unittest.TestCase):
    def test_optional_high_weight_cannot_displace_a_complete_required_route(self):
        import copy

        ref, prediction = fixture(), run()
        optional = copy.deepcopy(ref["evaluation"]["nodes"][-1])
        optional.update(id="optional_extra", required=False, weight=100)
        ref["evaluation"]["nodes"].insert(2, optional)
        result = score_workflow(ref, prediction)
        self.assertTrue(result["joint_pass"])
        self.assertTrue(
            next(n for n in result["nodes"] if n["id"] == "score")["matched"]
        )
        self.assertFalse(
            next(n for n in result["nodes"] if n["id"] == "optional_extra")["matched"]
        )

    def test_no_undeclared_default_recovery_exemption(self):
        import copy

        ref, prediction = fixture(), run()
        ref["evaluation"].pop("efficiency")
        failed = copy.deepcopy(prediction["calls"][0])
        failed.update(
            observation_id="failed",
            status="error",
            output=None,
            error="temporary error",
        )
        prediction["calls"].insert(0, failed)
        result = score_workflow(ref, prediction)
        self.assertTrue(result["joint_pass"])
        self.assertEqual(result["exempt_observations"], [])
        self.assertEqual(result["selection_efficiency"], 0.75)


if __name__ == "__main__":
    unittest.main()
