"""Fused linear rows retain all source pairs, multiplicities and actual outputs."""

import copy
import unittest
from evaluation.workflow import MissingEvidence, operand, predicate


def projection(
    matrix, vector, outputs, coefficients=(1, 2), reference=(0.2, 0.8), **kw
):
    return operand(
        dict(
            operation="linear_projection_values",
            args=[
                dict(value=v)
                for v in [matrix, vector, outputs, list(coefficients), list(reference)]
            ],
            **kw,
        ),
        {},
    )


class LinearProjectionValueTests(unittest.TestCase):
    def test_selected_complete_functional_and_all_duplicate_outputs(self):
        self.assertEqual(
            projection([[9, 9], [1, 2], [1, 2]], [0.2, 0.8], [9, 1.8, 1.8]), [1.8, 1.8]
        )
        self.assertEqual(projection([[1, 2], [1, 2]], [0.2, 0.8], [1.8, 99]), [1.8, 99])

    def test_joint_component_permutation_preserves_weight_pairs(self):
        self.assertEqual(projection([[2, 1]], [0.8, 0.2], [1.8]), [1.8])
        with self.assertRaises(MissingEvidence):
            projection([[2, 1]], [0.2, 0.8], [1.8])

    def test_required_functional_after_more_than32_fused_rows(self):
        self.assertEqual(
            projection([[9, 9]] * 64 + [[1, 2]], [0.2, 0.8], [9] * 64 + [1.8]), [1.8]
        )
        with self.assertRaises(MissingEvidence):
            projection([[9, 9]] * 64, [0.2, 0.8], [9] * 64)

    def test_tolerance_only_applies_to_complete_paired_components(self):
        self.assertEqual(
            projection([[1 + 5e-13, 2]], [0.2, 0.8], [1.8], atol=1e-11), [1.8]
        )
        with self.assertRaises(MissingEvidence):
            projection([[1 + 5e-9, 2]], [0.2, 0.8], [1.8], atol=1e-11)
        with self.assertRaises(MissingEvidence):
            projection([[1 + 5e-13, 2]], [0.2, 0.8], [1.8])

    def test_declared_component_identity_preserves_order_even_for_equal_weights(self):
        self.assertEqual(
            projection(
                [[1, 2]],
                [0.5, 0.5],
                [1.5],
                reference=[0.5, 0.5],
                preserve_component_order=True,
            ),
            [1.5],
        )
        with self.assertRaises(MissingEvidence):
            projection(
                [[2, 1]],
                [0.5, 0.5],
                [1.5],
                reference=[0.5, 0.5],
                preserve_component_order=True,
            )
        with self.assertRaises(MissingEvidence):
            projection([[1, 2]], [0.2, 0.8], [1.8], preserve_component_order=1)

    def test_bad_shape_type_nonfinite_and_work_bounds_fail(self):
        invalid = [
            ([], [], []),
            ([[1, 2]], [0.2], [1]),
            ([[1]], [0.2, 0.8], [1]),
            ([[1, 2]], [0.2, 0.8], []),
            ([[True, 2]], [0.2, 0.8], [1]),
            ([[1, 2]], [0.2, float("nan")], [1]),
            ([[1, 2]], [0.2, 0.8], [False]),
            ([[1] * 129], [1] * 129, [1]),
            ([[1] * 100] * 101, [1] * 100, [1] * 101),
        ]
        for matrix, vector, outputs in invalid:
            with self.subTest(shape=str(matrix)[:40]):
                with self.assertRaises(MissingEvidence):
                    projection(matrix, vector, outputs)
        for tolerance in [-1, False, float("inf")]:
            with self.assertRaises(MissingEvidence):
                projection([[1, 2]], [0.2, 0.8], [1.8], atol=tolerance)

    def test_coupled_components_keep_multiplicity(self):
        with self.assertRaises(MissingEvidence):
            projection(
                [[1, 1, 2]],
                [0.2, 0.2, 0.8],
                [1],
                coefficients=[1, 2, 2],
                reference=[0.2, 0.8, 0.8],
            )

    def test_observed_inputs_are_immutable_and_wrong_duplicate_is_visible(self):
        context = dict(
            call_arguments=dict(left=[[1, 2], [1, 2]], right=[0.2, 0.8]),
            call_output=dict(product=[1.8, 99]),
        )
        before = copy.deepcopy(context)
        e = dict(
            operation="linear_projection_values",
            args=[
                dict(source="call_arguments", path="/left"),
                dict(source="call_arguments", path="/right"),
                dict(source="call_output", path="/product"),
                dict(value=[1, 2]),
                dict(value=[0.2, 0.8]),
            ],
        )
        self.assertFalse(
            predicate(
                dict(left=dict(operation="max", args=[e]), op="eq", value=1.8), context
            )
        )
        self.assertEqual(context, before)


if __name__ == "__main__":
    unittest.main()
