"""Piecewise-linear evidence equivalence and published optional defaults."""

import copy
import unittest

from evaluation.workflow import (
    operand,
    predicate,
    score_workflow,
    validate_workflow,
    MissingEvidence,
)
from tests.support.workflows import fixture, run


def source_curve_rule():
    return {
        "path": "",
        "op": "curve_equivalent",
        "atol": 1e-10,
        "rtol": 1e-10,
        "x_atol": 1e-12,
        "x_rtol": 1e-12,
        "right": {
            "operation": "curve_spec",
            "args": [
                {"value": [0, 1, 2, 3]},
                {"value": [2, 4, 3, 5]},
                {"value": 1},
                {
                    "operation": "common_interval",
                    "args": [{"value": [0, 1, 2, 3]}, {"value": [0.5, 1.5, 2.5]}],
                },
            ],
        },
    }


class CurveEquivalentTest(unittest.TestCase):
    def test_clipped_baseline_and_added_union_grid(self):
        rule = source_curve_rule()
        minimal = {"x": [0.5, 1, 2, 2.5], "y": [2, 3, 2, 3]}
        union = {
            "x": [0.5, 0.75, 1, 1.5, 2, 2.25, 2.5],
            "y": [2, 2.5, 3, 2.5, 2, 2.5, 3],
        }
        self.assertTrue(predicate(rule, {}, minimal))
        self.assertTrue(predicate(rule, {}, union))
        # Same piecewise-linear scientific area despite a different exact grid.
        area = lambda curve: sum(
            (b - a) * (u + v) / 2
            for a, b, u, v in zip(
                curve["x"], curve["x"][1:], curve["y"], curve["y"][1:]
            )
        )
        self.assertEqual(area(minimal), area(union))

    def test_omitted_knot_rejected_even_when_endpoints_match(self):
        self.assertFalse(
            predicate(source_curve_rule(), {}, {"x": [0.5, 2.5], "y": [2, 3]})
        )
        # Dropping the interior kink is invalid even if its area happened to match.
        self.assertFalse(
            predicate(source_curve_rule(), {}, {"x": [0.5, 1, 2.5], "y": [2, 3, 3]})
        )

    def test_wrong_baseline_or_one_wrong_interpolated_point_rejected(self):
        for y in ([3, 4, 3, 4], [2, 3, 2, 3.1]):
            self.assertFalse(
                predicate(source_curve_rule(), {}, {"x": [0.5, 1, 2, 2.5], "y": y})
            )

    def test_extrapolation_and_incomplete_interval_rejected(self):
        for x, y in [
            ([0, 1, 2, 2.5], [1, 3, 2, 3]),
            ([0.5, 1, 2, 3], [2, 3, 2, 4]),
            ([1, 2, 2.5], [3, 2, 3]),
        ]:
            self.assertFalse(predicate(source_curve_rule(), {}, {"x": x, "y": y}))
        spec = source_curve_rule()["right"]
        spec["args"][3] = {"value": [-1, 2]}
        with self.assertRaises(MissingEvidence):
            operand(spec, {})

    def test_nonmonotonic_duplicates_nonfinite_and_booleans_rejected(self):
        for actual in [
            {"x": [0.5, 2, 1, 2.5], "y": [2, 2, 3, 3]},
            {"x": [0.5, 1, 1, 2, 2.5], "y": [2, 3, 3, 2, 3]},
            {"x": [0.5, 1, 2, 2.5], "y": [2, float("nan"), 2, 3]},
            {"x": [0.5, True, 2, 2.5], "y": [2, 3, 2, 3]},
            {"x": [0.5, 1, 2, 2.5], "y": [2, 3, 2]},
        ]:
            self.assertFalse(predicate(source_curve_rule(), {}, actual))

    def test_no_overlap_or_invalid_source_fails_closed(self):
        for grids in [
            [[0, 1], [2, 3]],
            [[0, 1], [1, 2]],
            [[0, 0], [0, 1]],
            [[0, 1], [0, True]],
        ]:
            with self.assertRaises(MissingEvidence):
                operand(
                    {
                        "operation": "common_interval",
                        "args": [{"value": a} for a in grids],
                    },
                    {},
                )
        spec = source_curve_rule()["right"]
        spec["args"][0] = {"value": [0, 2, 1, 3]}
        with self.assertRaises(MissingEvidence):
            operand(spec, {})

    def test_tolerances_and_schema_validation(self):
        spec = fixture()["evaluation"]
        spec["nodes"][0]["alternatives"][0]["input_rules"] = [source_curve_rule()]
        validate_workflow(spec)
        spec["nodes"][0]["alternatives"][0]["input_rules"][0]["x_atol"] = -1
        with self.assertRaises(ValueError):
            validate_workflow(spec)
        rule = source_curve_rule()
        self.assertTrue(
            predicate(
                rule, {}, {"x": [0.5 - 1e-13, 1, 2, 2.5 + 1e-13], "y": [2, 3, 2, 3]}
            )
        )
        self.assertFalse(
            predicate(rule, {}, {"x": [0.5 - 1e-3, 1, 2, 2.5], "y": [2, 3, 2, 3]})
        )

    def test_full_capability_matching_on_transformed_arguments(self):
        ref, prediction = fixture(), run()
        ref["evaluation"]["nodes"][2]["bindings"] = []
        ref["evaluation"]["nodes"][2]["alternatives"][0]["input_rules"] = [
            source_curve_rule()
        ]
        prediction["calls"][2]["arguments"] = {"x": [0.5, 1, 2, 2.5], "y": [2, 3, 2, 3]}
        self.assertTrue(score_workflow(ref, prediction)["joint_pass"])
        prediction["calls"][2]["arguments"]["y"][1] = 4
        self.assertFalse(score_workflow(ref, prediction)["planning_pass"])
        prediction["calls"][2]["_effective_arguments"] = {"alpha": 1.0}
        self.assertFalse(score_workflow(ref, prediction)["planning_pass"])


class EffectiveDefaultsTest(unittest.TestCase):
    def test_omitted_equals_published_default_without_mutating_raw(self):
        ref, prediction = fixture(), run()
        ref["evaluation"]["nodes"][2]["alternatives"][0]["input_rules"] = [
            {"path": "/alpha", "op": "eq", "value": 1.0}
        ]
        contracts = {
            "ScoreCandidates": {
                "parameters": [
                    {
                        "name": "alpha",
                        "required": False,
                        "default": "1.0",
                        "default_value": 1.0,
                    }
                ]
            }
        }
        before = copy.deepcopy(prediction)
        self.assertTrue(
            score_workflow(ref, prediction, tool_contracts=contracts)["joint_pass"]
        )
        self.assertEqual(prediction, before)
        prediction["calls"][2]["arguments"]["alpha"] = 1.0
        self.assertTrue(
            score_workflow(ref, prediction, tool_contracts=contracts)["joint_pass"]
        )
        for value in [2.0, None]:
            prediction["calls"][2]["arguments"]["alpha"] = value
            self.assertFalse(
                score_workflow(ref, prediction, tool_contracts=contracts)[
                    "planning_pass"
                ]
            )
        prediction["calls"][2]["arguments"].pop("alpha")
        self.assertFalse(score_workflow(ref, prediction)["planning_pass"])
        prediction["calls"][2]["_effective_arguments"] = {"alpha": 1.0}
        self.assertFalse(score_workflow(ref, prediction)["planning_pass"])

    def test_defaulted_values_also_apply_to_explicit_data_bindings(self):
        ref, prediction = fixture(), run()
        ref["evaluation"]["nodes"][2]["bindings"][0]["argument"] = "/defaults"
        contracts = {
            "ScoreCandidates": {
                "parameters": [
                    {
                        "name": "defaults",
                        "required": False,
                        "default_value": prediction["calls"][0]["output"]["rows"],
                    }
                ]
            }
        }
        self.assertTrue(
            score_workflow(ref, prediction, tool_contracts=contracts)["joint_pass"]
        )
        prediction["calls"][2]["arguments"]["defaults"] = None
        self.assertFalse(
            score_workflow(ref, prediction, tool_contracts=contracts)["planning_pass"]
        )


if __name__ == "__main__":
    unittest.main()
