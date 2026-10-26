"""Scientific boundary checks,not a mirror of production implementation."""

import itertools, math, unittest
import numpy as np
from scipy.stats import pearsonr
from tools.implementations.machine_learning.mantel import mantel_correlation


class MantelTests(unittest.TestCase):
    def setUp(self):
        self.a = [[0, 1, 2], [1, 0, 3], [2, 3, 0]]
        self.b = [[0, 2, 7], [2, 0, 6], [7, 6, 0]]

    def test_scipy_statistic_and_separate_label_enumeration(self):
        expected = float(pearsonr([1, 2, 3], [2, 7, 6]).statistic)
        self.assertAlmostEqual(
            mantel_correlation(self.a, self.b, 0)["correlation"], expected, 14
        )
        observed = mantel_correlation(self.a, self.b, 0)
        self.assertIsNone(observed["p_value"])
        self.assertIsNone(observed["extreme_count"])
        # Independently enumerate all3!object permutations,not3!IID paired entries in n>3.
        exact = []
        for order in itertools.permutations(range(3)):
            v = [self.a[order[i]][order[j]] for i, j in [(0, 1), (0, 2), (1, 2)]]
            exact.append(float(pearsonr(v, [2, 7, 6]).statistic))
        self.assertEqual(sum(abs(x) >= abs(expected) - 1e-14 for x in exact), 4)
        # Seeded MC count uses scipy's independently recomputed Pearson statistic.
        rng = np.random.default_rng(7)
        count = 0
        for _ in range(199):
            order = rng.permutation(3)
            v = [self.a[order[i]][order[j]] for i, j in [(0, 1), (0, 2), (1, 2)]]
            rr = float(pearsonr(v, [2, 7, 6]).statistic)
            count += int(abs(rr) >= abs(expected) - 1e-14)
        got = mantel_correlation(self.a, self.b, 199, 7)
        self.assertEqual(got["extreme_count"], count)
        self.assertEqual(got["p_value"], (count + 1) / 200)

    def test_scale_invariance_self_identity_and_all_three_tails(self):
        for alt in ["two-sided", "greater", "less"]:
            out = mantel_correlation(self.a, self.a, 199, 3, alt)
            self.assertAlmostEqual(out["correlation"], 1)
            self.assertGreater(out["p_value"], 0)
            self.assertLessEqual(out["p_value"], 1)
        huge = [[v * 1e307 for v in row] for row in self.a]
        small = [[v * 1e-250 for v in row] for row in self.b]
        self.assertAlmostEqual(
            mantel_correlation(huge, small, 0)["correlation"],
            mantel_correlation(self.a, self.b, 0)["correlation"],
            14,
        )

    def test_invalid_geometry_and_contract(self):
        cases = [
            {"distance_a": [[0, 1], [1, 0]]},
            {"distance_a": [[0, 1, 2], [1, 0], [2, 3, 0]]},
            {"distance_a": [[0, True, 2], [True, 0, 3], [2, 3, 0]]},
            {"distance_a": [[0, 1, 2], [1.1, 0, 3], [2, 3, 0]]},
            {"distance_a": [[1, 1, 2], [1, 0, 3], [2, 3, 0]]},
            {"distance_a": [[0, -1, 2], [-1, 0, 3], [2, 3, 0]]},
            {"distance_a": [[0, 1, float("inf")], [1, 0, 3], [float("inf"), 3, 0]]},
            {"distance_a": [[0, 1, 1], [1, 0, 1], [1, 1, 0]]},
            {"permutations": True},
            {"permutations": 1.5},
            {"seed": "7"},
            {"seed": -1},
            {"alternative": "GREATER"},
        ]
        for change in cases:
            with self.subTest(change=change), self.assertRaises(ValueError):
                mantel_correlation(
                    **{"distance_a": self.a, "distance_b": self.b, **change}
                )
        a = np.abs(np.arange(100)[:, None] - np.arange(100)[None, :]).tolist()
        with self.assertRaisesRegex(ValueError, "work limit"):
            mantel_correlation(a, a, 9999)


if __name__ == "__main__":
    unittest.main()
