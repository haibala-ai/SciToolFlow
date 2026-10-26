"""Coordinate coverage must preserve source identity and valid adjacent splits."""

import unittest

from evaluation.workflow import MissingEvidence, operand


def union(pairs, length):
    return operand(
        {"operation": "interval_union", "args": [{"value": pairs}, {"value": length}]},
        {},
    )


class IntervalCoverageTests(unittest.TestCase):
    def test_adjacent_splits_same_coverage_but_same_text_different_coordinates_not_equal(
        self,
    ):
        self.assertEqual(union([[0, 2], [2, 4], [8, 10]], 10), [[0, 4], [8, 10]])
        self.assertEqual(union([[0.0, 2.0], [2.0, 4.0]], 4.0), [[0, 4]])
        self.assertEqual(union([[0, 2000000]], 2000000), [[0, 2000000]])
        self.assertEqual(union([[0, 2], [3, 4]], 4), [[0, 2], [3, 4]])
        # A homopolymer can have identical selected text at shifted positions.
        self.assertNotEqual(union([[0, 3]], 10), union([[1, 4]], 10))

    def test_length_and_intervals_follow_actual_call_and_missing_evidence_fails(self):
        expression = {
            "operation": "interval_union",
            "args": [
                {"source": "actual_call", "path": "/intervals"},
                {
                    "operation": "length",
                    "args": [{"source": "actual_call", "path": "/sequence"}],
                },
            ],
        }
        context = {"actual_call": {"intervals": [[0, 3]], "sequence": "abcd"}}
        self.assertEqual(operand(expression, context), [[0, 3]])
        context["actual_call"]["sequence"] = "ab"
        with self.assertRaises(MissingEvidence):
            operand(expression, context)
        with self.assertRaises(MissingEvidence):
            operand(expression, {})

    def test_invalid_and_unbounded_intervals_fail_without_clipping_or_sorting(self):
        invalid = [
            ([[0, 1]], True),
            ([[False, 1]], 2),
            ([[0.2, 1]], 2),
            ([["0", 1]], 2),
            ([[0, float("inf")]], 2),
            ([[0, float("nan")]], 2),
            ([[0, 3], [2, 4]], 4),
            ([[0, 2], [0, 2]], 2),
            ([[2, 4], [0, 2]], 4),
            ([[0, 5]], 4),
            ([[-1, 2]], 4),
            ([[1, 1]], 4),
            ([], 4),
            ([[0, 1, 2]], 4),
            ([[i, i + 1] for i in range(1001)], 1001),
            ([[0, 1]], 2000001),
            ([[0, 1]], 0),
            ([[0, 1]], float("inf")),
            ([[0, 1]], "2"),
        ]
        for pairs, length in invalid:
            with (
                self.subTest(pairs=pairs[:2], length=length),
                self.assertRaises(MissingEvidence),
            ):
                union(pairs, length)
        for args in [
            [],
            [{"value": [[0, 1]]}],
            [{"value": [[0, 1]]}, {"value": 2}, {"value": 3}],
        ]:
            with self.assertRaises(MissingEvidence):
                operand({"operation": "interval_union", "args": args}, {})
