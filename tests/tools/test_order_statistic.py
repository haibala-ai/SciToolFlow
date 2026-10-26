"""Boundary, tied-rank and independent NumPy partition controls."""

import copy
import unittest
import numpy as np
from tools.implementations.machine_learning.order_statistic import (
    select_order_statistic,
)


class OrderStatisticTests(unittest.TestCase):
    def test_ties_endpoints_and_no_mutation(self):
        values = [8, -2, 3, 3, 3, 10]
        unchanged = copy.deepcopy(values)
        for rank, expected in [(1, -2), (2, 3), (4.0, 3), (6, 10)]:
            result = select_order_statistic(values, rank)
            self.assertEqual(result["selected_value"], expected)
            self.assertLessEqual(result["less_count"] + 1, rank)
            self.assertGreaterEqual(result["less_count"] + result["equal_count"], rank)
            self.assertEqual(
                sum(result[k] for k in ["less_count", "equal_count", "greater_count"]),
                len(values),
            )
        self.assertEqual(values, unchanged)
        self.assertEqual(select_order_statistic([2.0], 1)["selected_value"], 2.0)

    def test_independent_partition_all_ranks(self):
        rng = np.random.default_rng(49)
        for values in [
            rng.normal(size=81).tolist(),
            rng.integers(-3, 4, size=91).tolist(),
        ]:
            for rank in range(1, len(values) + 1):
                result = select_order_statistic(values, rank)
                self.assertEqual(
                    result["selected_value"], np.partition(values, rank - 1)[rank - 1]
                )

    def test_invalid_data_not_dropped(self):
        invalid = [
            ([], 1),
            ([1, 2], 0),
            ([1, 2], 3),
            ([1, 2], True),
            ([1, 2], 1.2),
            ([1, 2], "1"),
            ([1, 2], float("inf")),
            ([True, 2], 1),
            ([None, 2], 1),
            (["1", 2], 1),
            ([[1], 2], 1),
            ([float("nan"), 2], 1),
            ([float("inf"), 2], 1),
            ([10**1000], 1),
            ([1] * 10001, 1),
        ]
        for values, rank in invalid:
            with self.subTest(values=str(values)[:40], rank=rank):
                with self.assertRaises(ValueError):
                    select_order_statistic(values, rank)


if __name__ == "__main__":
    unittest.main()
