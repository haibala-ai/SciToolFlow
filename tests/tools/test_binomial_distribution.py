"""Independent exact rational binomial mass and stable-tail boundary checks."""

from fractions import Fraction as F
import math
import unittest
import mpmath as mp
from tools.implementations.machine_learning.binomial_distribution import (
    binomial_probability_table,
)


class BinomialProbabilityTests(unittest.TestCase):
    def test_exact_rational_small_support_and_tail_orientation(self):
        for n in [0, 1, 2, 8, 16, 40]:
            for p in [F(0), F(1), F(1, 2), F(3, 4), F(1, 10)]:
                o = binomial_probability_table(n, float(p))
                pmf = [
                    F(math.comb(n, k)) * p**k * (1 - p) ** (n - k) for k in range(n + 1)
                ]
                self.assertEqual(o["k"], list(range(n + 1)))
                for k, v in enumerate(pmf):
                    self.assertAlmostEqual(o["pmf"][k], float(v), places=13)
                    self.assertAlmostEqual(
                        o["cdf"][k], float(sum(pmf[: k + 1])), places=13
                    )
                    self.assertAlmostEqual(
                        o["sf"][k], float(sum(pmf[k + 1 :])), places=13
                    )
                    self.assertEqual(o["log_pmf"][k] is None, v == 0)
                self.assertAlmostEqual(o["mass_sum"], 1, places=13)

    def test_direct_small_tail_is_not_subtracted_from_rounded_cdf(self):
        o = binomial_probability_table(200, 0.5)
        self.assertEqual(o["cdf"][199], 1)
        self.assertGreater(o["sf"][199], 0)
        self.assertAlmostEqual(o["sf"][199] / float(F(1, 2) ** 200), 1, places=13)
        self.assertEqual(o["sf"][200], 0)

    def test_rounded_zero_is_not_exact_zero_and_log_mass_is_finite(self):
        o = binomial_probability_table(200, 1e-300)
        self.assertIn(200, o["rounded_zero_mass_k"])
        self.assertNotIn(200, o["exact_zero_mass_k"])
        with mp.workdps(100):
            p = mp.mpf(float(1e-300))
            expected = 200 * mp.log(p)
            self.assertLess(abs(o["log_pmf"][200] - float(expected)), 1e-8)
        self.assertTrue(math.isfinite(o["log_pmf"][200]))

    def test_explicit_input_domains_reject_coercion_and_nonfinite(self):
        for n, p in [
            (True, 0.5),
            (8.5, 0.5),
            (-1, 0.5),
            (201, 0.5),
            (8, True),
            (8, "0.5"),
            (8, None),
            (8, float("nan")),
            (8, float("inf")),
            (8, -0.1),
            (8, 1.1),
            (10**1000, 0.5),
            (8, 10**1000),
        ]:
            with self.subTest(n=str(n)[:30], p=str(p)[:30]):
                with self.assertRaises(ValueError):
                    binomial_probability_table(n, p)

    def test_no_random_sampling_or_state_mutation(self):
        self.assertEqual(
            binomial_probability_table(8.0, 0.5), binomial_probability_table(8, 0.5)
        )
        self.assertEqual(
            binomial_probability_table(8, 0.75), binomial_probability_table(8, 0.75)
        )


if __name__ == "__main__":
    unittest.main()
