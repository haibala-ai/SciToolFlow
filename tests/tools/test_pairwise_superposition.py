"""Proper-rigid shape distances: invariants, reflection, identity and numeric limits."""

import unittest
import numpy as np
from tools.implementations.machine_learning.matched_coordinate_distances import (
    pairwise_superposition_rmsd as f,
)


class PairwiseSuperpositionTests(unittest.TestCase):
    def setUp(self):
        self.x = np.array([[0.0, 0, 0], [1, 0, 0], [0, 2, 0], [0, 0, 3]])

    def test_rigid_invariance_symmetry_and_scope(self):
        q = np.array([[0.0, -1, 0], [1, 0, 0], [0, 0, 1]])
        result = f(
            [
                self.x.tolist(),
                (self.x @ q + [4, -2, 3]).tolist(),
                (2 * self.x).tolist(),
            ],
            ["original", "rigid", "scale"],
        )
        self.assertLess(result["rmsd_matrix"][0][1], 1e-12)
        self.assertGreater(result["rmsd_matrix"][0][2], 0.5)
        self.assertEqual(result["rmsd_matrix"][2][0], result["rmsd_matrix"][0][2])
        self.assertEqual(result["pair_count"], 3)

    def test_mirror_and_independent_point_permutation_are_not_removed(self):
        mirror = self.x * np.array([-1, 1, 1])
        p = self.x[[1, 0, 2, 3]]
        self.assertGreater(
            f([self.x.tolist(), mirror.tolist()], ["x", "mirror"])["rmsd_matrix"][0][1],
            0.5,
        )
        self.assertGreater(
            f([self.x.tolist(), p.tolist()], ["x", "wrong-pairs"])["rmsd_matrix"][0][1],
            0.1,
        )

    def test_consistent_point_and_set_reorder_preserves_distances(self):
        sets = [
            self.x.tolist(),
            (2 * self.x).tolist(),
            (self.x * np.array([1, 1, 2])).tolist(),
        ]
        before = f(sets, ["a", "b", "c"])
        after = f(
            [np.array(sets[i])[[3, 1, 2, 0]].tolist() for i in [2, 0, 1]],
            ["c", "a", "b"],
        )
        np.testing.assert_allclose(
            after["rmsd_matrix"],
            np.array(before["rmsd_matrix"])[[2, 0, 1]][:, [2, 0, 1]],
            atol=1e-12,
        )

    def test_extreme_finite_scale_and_subnormal_underflow(self):
        for scale in [1e-150, 1e150]:
            result = f(
                [(self.x * scale).tolist(), (2 * self.x * scale).tolist()], ["a", "b"]
            )
            reference = f([self.x.tolist(), (2 * self.x).tolist()], ["a", "b"])
            self.assertAlmostEqual(
                result["rmsd_matrix"][0][1] / scale,
                reference["rmsd_matrix"][0][1],
                places=12,
            )
        for scale in [5e-324, 1e-320]:
            with self.subTest(scale=scale), self.assertRaises(ValueError):
                f(
                    [(self.x * scale).tolist(), (2 * self.x * scale).tolist()],
                    ["a", "b"],
                )

    def test_degenerate_and_nearly_degenerate_shapes_fail(self):
        for shape in [
            [[1, 1, 1]] * 4,
            [[0, 0, 0], [1, 0, 0], [2, 0, 0]],
            [[0, 0, 0], [1, 0, 0], [2, 1e-15, 0]],
        ]:
            with self.subTest(shape=shape), self.assertRaises(ValueError):
                f([shape, shape], ["a", "b"])

    def test_strict_types_shapes_and_ids(self):
        x = self.x.tolist()
        for sets, ids in [
            ([x], ["a"]),
            ([x, x], ["a", "a"]),
            ([x, x], ["a", 1]),
            ([x, x[:3]], ["a", "b"]),
            ([x, [[1, 2]] * 4], ["a", "b"]),
        ]:
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                f(sets, ids)
        for bad in [True, None, "1", float("inf"), float("nan"), 10**1000]:
            wrong = [row[:] for row in x]
            wrong[0][0] = bad
            with self.subTest(bad=repr(bad)), self.assertRaises(ValueError):
                f([x, wrong], ["a", "b"])

    def test_corresponding_planar_triangles_valid_no_input_mutation(self):
        x = [[0, 0, 0], [1, 0, 0], [0, 2, 0]]
        y = [[0, 0, 0], [2, 0, 0], [0, 4, 0]]
        self.assertGreater(f([x, y], ["a", "b"])["rmsd_matrix"][0][1], 0)
        self.assertEqual(x, [[0, 0, 0], [1, 0, 0], [0, 2, 0]])


if __name__ == "__main__":
    unittest.main()
