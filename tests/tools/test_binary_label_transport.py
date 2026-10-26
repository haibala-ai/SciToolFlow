"""Cross-tool JSON label semantics and scientifically undefined metric boundaries."""

import math, unittest
from tools.implementations.machine_learning.research_workflows import (
    binary_classification_metrics as metrics,
    threshold_class_probabilities as threshold,
    decision_cost_summary as cost,
    probability_calibration_summary as calibration,
)


class BinaryLabelTransport(unittest.TestCase):
    def test_integral_transport_and_no_input_mutation(self):
        truth = [0.0, 1.0, 1.0, 0.0]
        pred = [0, 1, 0, 1]
        copy = list(truth)
        self.assertEqual(metrics(truth, pred, 1.0), metrics([0, 1, 1, 0], pred, 1))
        self.assertEqual(truth, copy)
        self.assertEqual(
            cost(truth, pred, 1.0, false_positive_cost=2, false_negative_cost=3)[
                "total_cost"
            ],
            5,
        )
        self.assertEqual(
            calibration(truth, [0.1, 0.8, 0.6, 0.4], 1.0),
            calibration([0, 1, 1, 0], [0.1, 0.8, 0.6, 0.4], 1),
        )

    def test_strings_remain_distinct(self):
        r = metrics(["1", 1], ["1", 1], 1.0)
        self.assertEqual((r["true_positive"], r["true_negative"]), (1, 1))
        self.assertEqual(
            threshold([0.5], positive_label="1", negative_label=1.0)["predicted"], ["1"]
        )

    def test_bad_labels_every_entry_point(self):
        for bad in [True, False, 0.5, float("nan"), float("inf"), [], {}, None]:
            for fn in [
                lambda: metrics([bad], [0], 1),
                lambda: metrics([0], [bad], 1),
                lambda: metrics([0], [0], bad),
                lambda: threshold([0.5], positive_label=bad),
                lambda: threshold([0.5], negative_label=bad),
                lambda: cost([bad], [0], 1),
                lambda: calibration([bad], [0.5], 1),
                lambda: calibration([0], [0.5], bad),
            ]:
                with self.subTest(bad=repr(bad)), self.assertRaises(ValueError):
                    fn()

    def test_absent_classes_and_null_denominators(self):
        r = metrics([0.0, 0.0], [0.0, 0.0], 1.0)
        self.assertIsNone(r["recall"])
        self.assertIsNone(r["precision"])
        self.assertEqual(r["specificity"], 1)
        r = metrics([1], [1], 1.0)
        self.assertIsNone(r["specificity"])
        self.assertEqual(calibration([0.0], [0.0], 1.0)["brier_score"], 0)
        for fn in [
            lambda: metrics(["cat", "dog"], ["dog", "cat"], "fish"),
            lambda: calibration(["cat", "dog"], [0.1, 0.9], "fish"),
        ]:
            with self.assertRaises(ValueError):
                fn()

    def test_threshold_boundaries_and_probability_scores(self):
        self.assertEqual(
            threshold([0, 0.499, 0.5, 1], positive_label=1.0, negative_label=0.0)[
                "predicted"
            ],
            [0, 0, 1, 1],
        )
        with self.assertRaises(ValueError):
            threshold([0.5], positive_label=1.0, negative_label=1)
        r = calibration([0.0, 1.0], [0.25, 0.75], 1.0, bins=5)
        self.assertAlmostEqual(r["brier_score"], 0.0625)
        self.assertAlmostEqual(r["log_loss"], -math.log(0.75))
        self.assertTrue(
            any(
                x["count"] == 0
                and x["mean_probability"] is None
                and x["observed_fraction"] is None
                for x in r["bins"]
            )
        )


if __name__ == "__main__":
    unittest.main()
