"""Reserved source names cannot erase keys or the requested statistic."""

import unittest
from tools.implementations.general.research_workflows import aggregate_record_groups


class AggregateCollisionTests(unittest.TestCase):
    def test_each_reserved_group_name_retains_original_key_and_counts(self):
        for key in [
            "observed_count",
            "missing_count",
            "group_key_values",
            "aggregate_value",
        ]:
            with self.subTest(key=key):
                r = aggregate_record_groups(
                    [{key: 3, "x": 2}, {key: 3, "x": None}, {key: 3, "x": 6}],
                    [key],
                    "x",
                )["records"][0]
                self.assertEqual(r["group_key_values"], {key: 3})
                self.assertEqual(r["aggregate_value"], 4)
                self.assertEqual(r["observed_count"], 2)
                self.assertEqual(r["missing_count"], 1)

    def test_each_reserved_value_name_retains_reduction_distinct_from_counts(self):
        for value in [
            "observed_count",
            "missing_count",
            "group_key_values",
            "aggregate_value",
        ]:
            for op, expected in [("mean", 4), ("sum", 8), ("median", 4)]:
                with self.subTest(value=value, op=op):
                    r = aggregate_record_groups(
                        [
                            {"g": "A", value: 2},
                            {"g": "A", value: 6},
                            {"g": "A", value: None},
                        ],
                        ["g"],
                        value,
                        op,
                    )["records"][0]
                    self.assertEqual(r["group_key_values"], {"g": "A"})
                    self.assertEqual(r["aggregate_value"], expected)
                    self.assertEqual((r["observed_count"], r["missing_count"]), (2, 1))

    def test_both_key_and_value_collision_with_all_null_and_distinct_key_types(self):
        result = aggregate_record_groups(
            [
                {"observed_count": 1, "missing_count": None},
                {"observed_count": "1", "missing_count": None},
            ],
            ["observed_count"],
            "missing_count",
            "sum",
        )
        self.assertEqual(result["group_count"], 2)
        for row, key in zip(result["records"], [1, "1"]):
            self.assertEqual(row["group_key_values"], {"observed_count": key})
            self.assertIsNone(row["aggregate_value"])
            self.assertEqual((row["observed_count"], row["missing_count"]), (0, 1))

    def test_noncollision_shape_is_unchanged(self):
        result = aggregate_record_groups(
            [{"group": "A", "value": 2}, {"group": "A", "value": 6}], ["group"], "value"
        )
        self.assertEqual(
            result["records"],
            [{"group": "A", "value": 4, "observed_count": 2, "missing_count": 0}],
        )


if __name__ == "__main__":
    unittest.main()
