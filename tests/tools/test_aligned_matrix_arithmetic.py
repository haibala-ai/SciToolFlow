"""Scientific handoff and boundary checks for exact-shape matrix arithmetic."""

import unittest
from tools.implementations.general.numeric_operations import (
    elementwise_numeric_operations as calc,
)


class AlignedMatrixArithmeticTests(unittest.TestCase):
    def test_pearson_residual_identity(self):
        # Complete observed table, with its true independence expectation.
        table = [[20, 10], [5, 15]]
        expected = [[15, 15], [10, 10]]
        residual = calc("subtract", table, expected)["values"]
        root = calc("sqrt", expected)["values"]
        standardized = calc("divide", residual, root)["values"]
        pearson = sum(v * v for row in standardized for v in row)
        independent = sum(
            (table[i][j] - expected[i][j]) ** 2 / expected[i][j]
            for i in range(2)
            for j in range(2)
        )
        self.assertAlmostEqual(pearson, independent)
        self.assertEqual(
            calc("multiply", [[1, 2]], [[2, 3]])["operand_mode"], "aligned_matrix"
        )

    def test_no_axis_or_shape_broadcast(self):
        for other in [
            [1, 2],
            [[1, 2]],
            [[1], [2]],
            [[1, 2], [3]],
            [[[1], [2]], [[3], [4]]],
        ]:
            with self.subTest(other=other), self.assertRaises(ValueError):
                calc("add", [[1, 2], [3, 4]], other)

    def test_bad_cells_and_arithmetic_domain(self):
        for other in [
            [[True, 1]],
            [[None, 1]],
            [["1", 1]],
            [[float("nan"), 1]],
            [[float("inf"), 1]],
            [[10**1000, 1]],
        ]:
            with self.subTest(other=repr(other)), self.assertRaises(ValueError):
                calc("add", [[1, 2]], other)
        for operation, values, other in [
            ("divide", [[1, 2]], [[1, 0]]),
            ("multiply", [[1e-200]], [[1e-200]]),
            ("divide", [[1e-300]], [[1e300]]),
            ("add", [[1e308]], [[1e308]]),
        ]:
            with (
                self.subTest(operation=operation, values=values),
                self.assertRaises(ValueError),
            ):
                calc(operation, values, other)

    def test_input_identity_and_existing_success_modes(self):
        left, right = [[1, 2], [3, 4]], [[4, 3], [2, 1]]
        self.assertEqual(calc("add", left, right)["values"], [[5.0, 5.0], [5.0, 5.0]])
        self.assertEqual(left, [[1, 2], [3, 4]])
        self.assertEqual(right, [[4, 3], [2, 1]])
        self.assertEqual(
            calc("divide", [[2, 4]], 2)["operand_mode"], "scalar_broadcast"
        )
        self.assertEqual(
            calc("divide", [2, 4], [1, 2])["operand_mode"], "aligned_vector"
        )
        self.assertEqual(calc("sqrt", [[4, 9]])["values"], [[2.0, 3.0]])


if __name__ == "__main__":
    unittest.main()
