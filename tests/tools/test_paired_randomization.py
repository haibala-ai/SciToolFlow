"""Independent assignment enumeration and scientific domain boundaries."""

from collections import Counter
from fractions import Fraction as F
import itertools
import unittest

from tools.implementations.machine_learning.randomization import (
    paired_randomization_test,
)


class PairedRandomizationTests(unittest.TestCase):
    def test_exhaustive_small_designs_against_literal_assignments(self):
        for n in range(2, 7):
            for differences in itertools.product([-1, 0, 1], repeat=n):
                null = Counter(
                    sum(s * d for s, d in zip(signs, differences))
                    for signs in itertools.product([-1, 1], repeat=n)
                )
                observed = sum(differences)
                for tail in ["two-sided", "greater", "less"]:
                    expected = sum(
                        count
                        for value, count in null.items()
                        if (
                            abs(value) >= abs(observed)
                            if tail == "two-sided"
                            else (
                                value >= observed
                                if tail == "greater"
                                else value <= observed
                            )
                        )
                    )
                    actual = paired_randomization_test(list(differences), [0] * n, tail)
                    self.assertEqual(actual["extreme_assignment_count"], expected)
                    self.assertEqual(actual["p_value_exact"], str(F(expected, 2**n)))
                    self.assertEqual(actual["unique_null_statistics"], len(null))

    def test_decimal_ties_and_zero_pairs_keep_assignment_multiplicity(self):
        result = paired_randomization_test(
            [0.1, 0.2, 0.3], [0, 0, 0], return_distribution=True
        )
        histogram = {
            r["mean_difference_exact"]: r["multiplicity"]
            for r in result["null_distribution"]
        }
        self.assertEqual(histogram["0"], 2)
        self.assertEqual(sum(histogram.values()), 8)
        self.assertEqual(result["p_value_exact"], "1/4")
        zero = paired_randomization_test([3, 4, 5], [3, 4, 5], return_distribution=True)
        self.assertEqual(zero["p_value_exact"], "1")
        self.assertEqual(
            zero["null_distribution"],
            [{"mean_difference": 0.0, "mean_difference_exact": "0", "multiplicity": 8}],
        )

    def test_pair_order_roles_and_common_unit_changes(self):
        a, b = [1, 4, 2, 6], [2, 2, 1, 5]
        base = paired_randomization_test(a, b, "greater")
        self.assertEqual(
            base["p_value"],
            paired_randomization_test(a[::-1], b[::-1], "greater")["p_value"],
        )
        swap = paired_randomization_test(b, a, "less")
        self.assertEqual(base["p_value"], swap["p_value"])
        self.assertEqual(
            base["observed_mean_difference"], -swap["observed_mean_difference"]
        )
        scaled = paired_randomization_test(
            [10 * v for v in a], [10 * v for v in b], "greater"
        )
        self.assertEqual(base["p_value"], scaled["p_value"])
        self.assertEqual(
            base["observed_mean_difference"] * 10, scaled["observed_mean_difference"]
        )

    def test_bound_enumerates_all_assignments_even_when_histogram_omitted(self):
        result = paired_randomization_test(
            [2**i for i in range(16)], [0] * 16, return_distribution=True
        )
        self.assertEqual(result["assignment_count"], 65536)
        self.assertEqual(result["unique_null_statistics"], 65536)
        self.assertEqual(result["p_value_exact"], "1/32768")
        self.assertIsNone(result["null_distribution"])
        self.assertEqual(
            result["distribution_status"], "omitted_above4096_unique_values"
        )

    def test_declared_underflow_does_not_silently_replace_exact_value(self):
        result = paired_randomization_test([5e-324, 0, 0], [0, 0, 0])
        self.assertEqual(result["observed_mean_difference"], 0.0)
        self.assertNotEqual(result["observed_mean_difference_exact"], "0")
        self.assertIn("/observed_mean_difference", result["numeric_underflow_fields"])
        self.assertEqual(result["p_value_exact"], "1")

    def test_invalid_inputs_are_rejected(self):
        cases = [
            {"sample_a": [1], "sample_b": [0]},
            {"sample_a": [0] * 17, "sample_b": [0] * 17},
            {"sample_b": [0, 0, 0]},
            {"sample_a": (1, 2)},
            *[
                {"sample_a": [1, v]}
                for v in [True, None, "2", float("inf"), float("nan"), 1e101, 10**1000]
            ],
            *[{"alternative": v} for v in ["Greater", True, None, []]],
            {"return_distribution": 1},
        ]
        for change in cases:
            with self.subTest(change=change), self.assertRaises(ValueError):
                paired_randomization_test(
                    **{"sample_a": [1, 2], "sample_b": [0, 0], **change}
                )


if __name__ == "__main__":
    unittest.main()
