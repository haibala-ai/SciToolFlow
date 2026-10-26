"""Matrix representation equivalence must preserve full feature pairings."""

import itertools
import unittest

from evaluation.workflow import MissingEvidence, operand


def profile(value):
    return operand({"operation": "matrix_axis_profile", "args": [{"value": value}]}, {})


class MatrixAxisProfileTests(unittest.TestCase):
    def test_all_small_joint_axis_permutations_are_identical(self):
        matrix = [[0, 1, 4], [2, 3, 8], [1, 5, 9]]
        expected = profile(matrix)
        for rows in itertools.permutations(range(3)):
            for cols in itertools.permutations(range(3)):
                self.assertEqual(
                    profile([[matrix[i][j] for j in cols] for i in rows]), expected
                )

    def test_margins_do_not_replace_complete_shared_features(self):
        matrix = [[0, 1, 4], [2, 3, 8], [1, 5, 9]]
        wrong = [matrix[0][::-1], matrix[1], matrix[2]]
        self.assertNotEqual(profile(matrix), profile(wrong))

    def test_zero_columns_and_duplicate_features_keep_multiplicity(self):
        matrix = [[0, 0, 1], [0, 0, 2]]
        self.assertEqual(profile(matrix), [[0, 0], [0, 0], [1, 2]])
        self.assertNotEqual(profile(matrix), profile([[0, 1], [0, 2]]))

    def test_ambiguous_rows_do_not_claim_unique_identity(self):
        with self.assertRaises(MissingEvidence):
            profile([[1, 2], [2, 1]])

    def test_bad_numeric_values_shape_and_work_bounds_reject(self):
        for value in [
            [],
            [[True]],
            [[float("nan")]],
            [[float("inf")]],
            [[1], [2, 3]],
            [[0] * 1001],
            [[0] * 100] * 129,
        ]:
            with self.subTest(shape=str(value)[:30]):
                with self.assertRaises(MissingEvidence):
                    profile(value)


if __name__ == "__main__":
    unittest.main()
