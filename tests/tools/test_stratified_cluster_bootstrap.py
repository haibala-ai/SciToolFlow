"""Scientific weighting, design preservation, identity and error boundaries."""

import copy
import itertools
import math
import unittest
from tools.implementations.machine_learning.stratified_bootstrap import (
    stratified_cluster_mean_interval,
)


class StratifiedClusterBootstrapTests(unittest.TestCase):
    def setUp(self):
        # Unequal row counts: six rows still represent only four independent
        # clusters. Fixed stratum weights differ from raw cluster proportions.
        self.args = dict(
            values=[0, 0, 2, 10, 14, 14],
            groups=["a", "a", "b", "c", "d", "d"],
            strata=["low"] * 3 + ["high"] * 3,
            stratum_weights=[
                {"stratum": "low", "weight": 0.25},
                {"stratum": "high", "weight": 0.75},
            ],
            resamples=10000,
            seed=42,
        )

    def test_fixed_weights_cluster_units_and_exact_bootstrap_support(self):
        result = stratified_cluster_mean_interval(**self.args)
        self.assertEqual(result["mean"], 9.25)
        self.assertEqual((result["group_count"], result["stratum_count"]), (4, 2))
        exact = sorted(
            0.25 * sum(a) / 2 + 0.75 * sum(b) / 2
            for a in itertools.product([0, 2], repeat=2)
            for b in itertools.product([10, 14], repeat=2)
        )
        # Extreme percentile quantiles coincide with the exact16outcome
        # distribution, not a normal approximation or independent row bootstrap.
        self.assertEqual(result["interval"], [exact[0], exact[-1]])
        self.assertEqual(
            [row["cluster_count"] for row in result["stratum_summaries"]], [2, 2]
        )

    def test_row_and_weight_order_do_not_change_canonical_rng_result(self):
        perm = [5, 0, 3, 1, 4, 2]
        args = copy.deepcopy(self.args)
        for field in ["values", "groups", "strata"]:
            args[field] = [args[field][i] for i in perm]
        args["stratum_weights"].reverse()
        self.assertEqual(
            stratified_cluster_mean_interval(**args),
            stratified_cluster_mean_interval(**self.args),
        )

    def test_repeated_rows_do_not_create_independent_units(self):
        args = copy.deepcopy(self.args)
        for field in ["values", "groups", "strata"]:
            args[field] *= 3
        first = stratified_cluster_mean_interval(**self.args)
        second = stratified_cluster_mean_interval(**args)
        self.assertEqual(first["mean"], second["mean"])
        self.assertEqual(first["interval"], second["interval"])
        self.assertEqual(second["group_count"], 4)

    def test_invalid_weight_design_is_rejected(self):
        variants = [
            [],
            [{"stratum": "low", "weight": 1}],
            [{"stratum": "low", "weight": 0.5}, {"stratum": "low", "weight": 0.5}],
            [{"stratum": "low", "weight": 0.25}, {"stratum": "high", "weight": 0.74}],
            [{"stratum": "low", "weight": 0}, {"stratum": "high", "weight": 1}],
            [
                {"stratum": "low", "weight": float("nan")},
                {"stratum": "high", "weight": 1},
            ],
        ]
        for weights in variants:
            with self.subTest(weights=weights), self.assertRaises(ValueError):
                stratified_cluster_mean_interval(
                    **dict(self.args, stratum_weights=weights)
                )

    def test_global_cluster_cannot_cross_strata(self):
        args = copy.deepcopy(self.args)
        args["groups"][3] = "a"
        with self.assertRaisesRegex(ValueError, "exactly one stratum"):
            stratified_cluster_mean_interval(**args)

    def test_nonfinite_boolean_and_single_cluster_errors(self):
        for values in [[True, 0, 2, 10, 14, 14], [0, 0, 2, 10, 14, float("inf")]]:
            with self.assertRaises(ValueError):
                stratified_cluster_mean_interval(**dict(self.args, values=values))
        with self.assertRaises(ValueError):
            stratified_cluster_mean_interval(
                **dict(self.args, groups=["a", "a", "a", "c", "d", "d"])
            )
        with self.assertRaises(ValueError):
            stratified_cluster_mean_interval(**dict(self.args, seed=-1))
        with self.assertRaises(ValueError):
            stratified_cluster_mean_interval(**dict(self.args, resamples=True))


if __name__ == "__main__":
    unittest.main()
