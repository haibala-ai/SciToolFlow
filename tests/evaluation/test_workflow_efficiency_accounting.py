"""Expose raw scientific-call cost separately from declared bounded allowances."""

import unittest

from evaluation.workflow import score_workflow
from tests.support.workflows import fixture, run, call


class EfficiencyAccountingTests(unittest.TestCase):
    def test_recovery_policy_cannot_hide_raw_cost(self):
        prediction = run()
        prediction["calls"].insert(
            0, call("retry", "ReadTable", {"dataset": "wrong"}, None, "error")
        )
        prediction["calls"].insert(
            1, call("explore", "InspectSchema", {}, {"kind": "table"})
        )
        result = score_workflow(fixture(), prediction)
        self.assertTrue(result["joint_pass"])
        self.assertEqual(result["scientific_calls"], 5)
        self.assertEqual(result["matched_scientific_calls"], 3)
        self.assertEqual(result["charged_scientific_calls"], 3)
        self.assertEqual(result["recovery_exempt_calls"], 1)
        self.assertEqual(result["exploration_exempt_calls"], 1)
        self.assertEqual(result["selection_efficiency"], 1)
        self.assertEqual(result["raw_selection_efficiency"], 3 / 5)

    def test_unrelated_failure_has_no_recovery_allowance(self):
        prediction = run()
        prediction["calls"].append(
            call("unrelated", "UnrelatedConversion", {}, None, "error")
        )
        result = score_workflow(fixture(), prediction)
        self.assertTrue(result["joint_pass"])
        self.assertEqual(result["recovery_exempt_calls"], 0)
        self.assertEqual(result["charged_scientific_calls"], 4)
        self.assertEqual(result["selection_efficiency"], 3 / 4)
        self.assertEqual(result["raw_selection_efficiency"], 3 / 4)
