"""A one-column regressor and scalar polynomial must preserve the same pairs."""

import unittest
from evaluation.authoring.affine_routes import repair_paired_polynomial_routes
from evaluation.workflow import predicate


class AffinePolynomialPairTests(unittest.TestCase):
    def node(self, matrix):
        return {
            "alternatives": [
                {
                    "tools": ["PolynomialLeastSquaresFit"],
                    "input_rules": [
                        {
                            "left": {
                                "operation": "paired_rows",
                                "args": [
                                    {
                                        "source": "call_arguments",
                                        "path": "/training_features",
                                    },
                                    {"source": "call_arguments", "path": "/y"},
                                ],
                            },
                            "op": "multiset_equal",
                            "right": {
                                "operation": "paired_rows",
                                "args": [{"value": matrix}, {"value": [8, 5, 2]}],
                            },
                        }
                    ],
                }
            ]
        }

    def test_repair_flattens_only_the_single_predictor_and_keeps_pairing(self):
        node = self.node([[3], [2], [1]])
        self.assertTrue(repair_paired_polynomial_routes([node]))
        rule = node["alternatives"][0]["input_rules"][0]
        self.assertTrue(
            predicate(rule, {"call_arguments": {"x": [1, 3, 2], "y": [2, 8, 5]}})
        )
        self.assertFalse(
            predicate(rule, {"call_arguments": {"x": [1, 3, 2], "y": [8, 2, 5]}})
        )
        self.assertFalse(repair_paired_polynomial_routes([node]))

    def test_multifeature_regression_is_not_silently_recast_as_polynomial(self):
        with self.assertRaises(AssertionError):
            repair_paired_polynomial_routes([self.node([[1, 2], [2, 3], [3, 4]])])


if __name__ == "__main__":
    unittest.main()
