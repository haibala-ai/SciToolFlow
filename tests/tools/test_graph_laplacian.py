"""Graph quadratic form and strict scientific geometry boundaries."""

import unittest
import numpy as np
from tools.implementations.machine_learning.graph_laplacian import graph_laplacian


class GraphLaplacianTests(unittest.TestCase):
    def test_weighted_graph_quadratic_form(self):
        a = [[0, 2, 0], [2, 0, 3], [0, 3, 0]]
        r = graph_laplacian(a)
        self.assertEqual(r["degrees"], [2, 5, 3])
        self.assertEqual(r["laplacian"], [[2, -2, 0], [-2, 5, -3], [0, -3, 3]])
        x = np.array([2.0, -1.0, 4.0])
        self.assertAlmostEqual(
            x @ np.array(r["laplacian"]) @ x,
            2 * (x[0] - x[1]) ** 2 + 3 * (x[1] - x[2]) ** 2,
        )
        self.assertEqual(a, [[0, 2, 0], [2, 0, 3], [0, 3, 0]])

    def test_isolates_and_zero_graph_not_silently_deleted(self):
        r = graph_laplacian([[0, 2, 0], [2, 0, 0], [0, 0, 0]])
        self.assertEqual(r["node_count"], 3)
        self.assertEqual(r["degrees"][2], 0)
        self.assertEqual(graph_laplacian([[0]])["laplacian"], [[0.0]])

    def test_invalid_geometry_and_overflow(self):
        for value in [
            [],
            [[0, 1]],
            [[0, 1], [2, 0]],
            [[1]],
            [[0, -1], [-1, 0]],
            [[False]],
            [[0, float("nan")], [float("nan"), 0]],
            [[0, float("inf")], [float("inf"), 0]],
            [[0, "1"], ["1", 0]],
            [[0, 1e308, 1e308], [1e308, 0, 0], [1e308, 0, 0]],
            [[0, 10**1000], [10**1000, 0]],
            [[0] * 101 for _ in range(101)],
        ]:
            with self.subTest(value=str(value)[:40]), self.assertRaises(ValueError):
                graph_laplacian(value)

    def test_exact_symmetry_checked_before_float_rounding(self):
        with self.assertRaises(ValueError):
            graph_laplacian([[0, 2**54], [2**54 + 1, 0]])


if __name__ == "__main__":
    unittest.main()
