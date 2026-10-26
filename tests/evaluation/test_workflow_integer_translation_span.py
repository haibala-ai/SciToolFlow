"""Alternative closed-walk generators preserve span, not lattice index."""

import unittest

from evaluation.workflow import MissingEvidence, operand


def span(value):
    return operand(
        {"operation": "integer_translation_span", "args": [{"value": value}]}, {}
    )


class TranslationSpanTests(unittest.TestCase):
    def test_generator_order_sign_redundancy_and_nonprimitive_steps(self):
        expected = span([[1, 0, 0], [0, 1, 0]])
        self.assertEqual(
            span([[-1, -1, 0], [0, -1, 0], [2, 2, 0], [0, 0, 0]]), expected
        )
        self.assertEqual(span([[2, 0, 0], [0, 4, 0]]), expected)

    def test_correct_rank_with_wrong_plane_is_different(self):
        self.assertNotEqual(span([[1, 0, 0], [0, 1, 0]]), span([[1, 0, 0], [0, 0, 1]]))

    def test_incomplete_and_zero_subspaces_are_distinct(self):
        self.assertNotEqual(span([[1, 1, 0]]), span([[1, 0, 0], [0, 1, 0]]))
        self.assertEqual(span([[0, 0, 0]]), [])

    def test_exact_rational_plane(self):
        self.assertEqual(
            span([[2, 0, 1], [0, 3, 1]]), [["1", "0", "1/2"], ["0", "1", "1/3"]]
        )

    def test_invalid_or_almost_integer_coordinates_are_rejected(self):
        for bad in [
            [],
            [[True, 0, 0]],
            [[1, 0, 1e-12]],
            [[1, 0]],
            [[float("inf"), 0, 0]],
            [[1000001, 0, 0]],
            [[1, 0, 0]] * 1001,
            "translations",
        ]:
            with self.subTest(value=str(bad)[:40]), self.assertRaises(MissingEvidence):
                span(bad)


if __name__ == "__main__":
    unittest.main()
