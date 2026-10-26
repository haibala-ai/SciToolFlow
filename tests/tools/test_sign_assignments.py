"""Enumeration coverage,orthogonality and exact index/coordinate boundaries."""

import itertools
import unittest
from tools.implementations.machine_learning.sign_assignments import (
    enumerate_sign_assignments,
)


class SignAssignmentTests(unittest.TestCase):
    def test_small_full_support_matches_independent_cartesian_product(self):
        for n in range(1, 9):
            out = enumerate_sign_assignments(n, max_rows=10000)
            expected = [list(reversed(v)) for v in itertools.product([-1, 1], repeat=n)]
            self.assertEqual(out["signs"], expected)
            self.assertTrue(out["complete_from_zero"])
            self.assertIsNone(out["next_start_index"])

    def test_complete_design_sign_columns_and_interactions_are_balanced(self):
        for n in range(1, 7):
            rows = enumerate_sign_assignments(n)["signs"]
            for mask in range(1, 1 << n):
                total = 0
                for row in rows:
                    v = 1
                    for j, x in enumerate(row):
                        if mask & (1 << j):
                            v *= x
                    total += v
                self.assertEqual(total, 0)

    def test_chunks_cover_large_support_without_overlap_or_missing_states(self):
        states = []
        start = 0
        while start is not None:
            out = enumerate_sign_assignments(10, start, max_rows=137)
            self.assertLessEqual(len(out["signs"]) * 10, 10000)
            states.extend(out["assignment_indices"])
            start = out["next_start_index"]
        self.assertEqual(states, list(range(1024)))

    def test_high_dimension_cap_endpoints_and_integer_normalization(self):
        out = enumerate_sign_assignments(16, 65535, 10000)
        self.assertEqual(out["signs"], [[1] * 16])
        self.assertEqual(out["assignment_ids"], ["1" * 16])
        self.assertFalse(out["complete_from_zero"])
        self.assertIsNone(out["next_start_index"])
        self.assertEqual(enumerate_sign_assignments(16, 65536)["signs"], [])
        self.assertEqual(
            enumerate_sign_assignments(8.0, 0.0, 256.0),
            enumerate_sign_assignments(8, 0, 256),
        )
        self.assertEqual(
            enumerate_sign_assignments(16, 0, 10000)["returned_assignments"], 625
        )

    def test_invalid_domains_reject_coercion(self):
        for args in [
            (True, 0, 256),
            (0, 0, 256),
            (17, 0, 256),
            (8.5, 0, 256),
            (8, -1, 256),
            (8, 257, 256),
            (8, False, 256),
            (8, 0, 0),
            (8, 0, 10001),
            (8, 0, 1.5),
            (8, 0, "256"),
            (float("nan"), 0, 256),
        ]:
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    enumerate_sign_assignments(*args)


if __name__ == "__main__":
    unittest.main()
