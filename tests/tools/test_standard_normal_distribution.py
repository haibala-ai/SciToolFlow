"""Independent high-precision tails and inverse probabilities, plus domains."""

import math
import unittest

import mpmath as mp
from tools.implementations.machine_learning.normal_distribution import (
    standard_normal_distribution as evaluate,
)


class StandardNormalTests(unittest.TestCase):
    def test_maximum_batch_preserves_alignment(self):
        result = evaluate("cdf", [0] * 10000)
        self.assertEqual(result["results"], [0.5] * 10000)
        self.assertEqual(result["rounded_zero_indices"], [])
        self.assertEqual(result["rounded_one_indices"], [])

    def test_cdf_and_sf_against_high_precision_erfc(self):
        xs = [-40, -20, -9, -2, 0, 0.5, 3, 8, 9, 20, 40, 1e6, -1e6]
        for op in ("cdf", "sf"):
            actual = evaluate(op, xs)
            with mp.workdps(100):
                for i, x in enumerate(xs):
                    z = mp.mpf(x) if op == "cdf" else -mp.mpf(x)
                    small = mp.erfc(abs(z) / mp.sqrt(2)) / 2
                    result = small if z <= 0 else 1 - small
                    logp = mp.log(small) if z <= 0 else mp.log1p(-small)
                    logq = mp.log1p(-small) if z <= 0 else mp.log(small)
                    self.assertTrue(
                        math.isclose(
                            actual["results"][i],
                            float(result),
                            abs_tol=0,
                            rel_tol=2e-13,
                        ),
                        (op, x),
                    )
                    for got, want in (
                        (actual["log_results"][i], float(logp)),
                        (actual["log_complements"][i], float(logq)),
                    ):
                        self.assertTrue(
                            math.isclose(got, want, abs_tol=0, rel_tol=2e-13),
                            (op, x, got, want),
                        )

    def test_inverse_lower_and_upper_tails(self):
        probabilities = [1e-300, 1e-100, 1e-12, 0.01, 0.5, 0.95, 0.99, 1 - 1e-12]
        for op in ("ppf", "isf"):
            actual = evaluate(op, probabilities)
            self.assertIsNone(actual["log_results"])
            self.assertIsNone(actual["log_complements"])
            with mp.workdps(350):
                for p, got in zip(probabilities, actual["results"]):
                    numerator, denominator = p.as_integer_ratio()
                    prob = mp.mpf(numerator) / denominator
                    want = mp.sqrt(2) * mp.erfinv(2 * prob - 1)
                    if op == "isf":
                        want = -want
                    self.assertTrue(
                        math.isclose(got, float(want), abs_tol=2e-13, rel_tol=2e-13),
                        (op, p, got),
                    )

    def test_rounded_probability_endpoints_retain_finite_log_tail(self):
        low = evaluate("cdf", [-40])
        high = evaluate("cdf", [40])
        self.assertEqual(low["results"], [0.0])
        self.assertEqual(low["rounded_zero_indices"], [0])
        self.assertEqual(high["results"], [1.0])
        self.assertEqual(high["rounded_one_indices"], [0])
        self.assertLess(low["log_results"][0], -800)
        self.assertEqual(low["log_results"], high["log_complements"])
        self.assertEqual(evaluate("sf", [40])["results"], low["results"])

    def test_smallest_positive_probability_quantile_is_finite(self):
        p = math.nextafter(0.0, 1.0)
        self.assertTrue(math.isfinite(evaluate("ppf", [p])["results"][0]))
        self.assertEqual(
            evaluate("ppf", [p])["results"][0], -evaluate("isf", [p])["results"][0]
        )

    def test_invalid_cells_bounds_and_operation_fail(self):
        for values in (
            [],
            [True],
            [None],
            ["0.1"],
            [[0]],
            [float("nan")],
            [float("inf")],
            [10**1000],
            [1000001],
            [-1000001],
            [0] * 10001,
        ):
            with self.subTest(values_type=type(values).__name__):
                with self.assertRaises(ValueError):
                    evaluate("cdf", values)
        for op in ("ppf", "isf"):
            for values in ([0], [1], [-0.1], [1.1], [True], [float("nan")], [10**1000]):
                with self.assertRaises(ValueError):
                    evaluate(op, values)
        for op in ("CDF", "pdf", "", None, True):
            with self.assertRaises(ValueError):
                evaluate(op, [0])


if __name__ == "__main__":
    unittest.main()
