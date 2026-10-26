"""Identity-bound observed record lookup survives ordering and projection."""

import unittest
from evaluation.workflow import operand, MissingEvidence


def lookup(records, identity="mp-A", path="/tensor/values", key="material_id"):
    return operand(
        {
            "operation": "record_value",
            "args": [
                {"value": records},
                {"value": key},
                {"value": identity},
                {"value": path},
            ],
        },
        {},
    )


class RecordValueTest(unittest.TestCase):
    def setUp(self):
        self.a = {
            "material_id": "mp-A",
            "tensor": {"values": [1, 2, 3]},
            "optional": None,
        }
        self.b = {"material_id": "mp-B", "tensor": {"values": [4, 5, 6]}}

    def test_filtered_reordered_records_produce_identical_observed_value(self):
        self.assertEqual(lookup([self.a, self.b]), [1, 2, 3])
        self.assertEqual(lookup([self.b, self.a]), [1, 2, 3])
        self.assertEqual(lookup([self.a]), [1, 2, 3])
        self.assertEqual(
            lookup([{"material_id": "mp-A", "tensor": {"values": [1, 2, 3]}}]),
            [1, 2, 3],
        )
        self.assertEqual(lookup([self.a], path=""), self.a)

    def test_missing_duplicate_identity_and_missing_field_fail(self):
        for records in [[self.b], [self.a, self.a], [{"tensor": {"values": [1]}}]]:
            with self.assertRaises(MissingEvidence):
                lookup(records)
        with self.assertRaises(MissingEvidence):
            lookup([self.a], path="/absent")
        self.assertIsNone(lookup([self.a], path="/optional"))
        # Missing identity is not the same as an explicit null identity.
        self.assertEqual(
            lookup([{"id": None, "value": 0}], identity=None, path="/value", key="id"),
            0,
        )
        with self.assertRaises(MissingEvidence):
            lookup([{"value": 0}], identity=None, path="/value", key="id")

    def test_strict_pointer_bounds_and_scalar_identity_validation(self):
        for path in ["tensor/values", "/~2", "/~", 3]:
            with self.assertRaises(MissingEvidence):
                lookup([self.a], path=path)
        for records in [[], [self.a] * 1001, [self.a, 3]]:
            with self.assertRaises(MissingEvidence):
                lookup(records)
        for identity in [[], {}, float("nan"), float("inf")]:
            with self.assertRaises(MissingEvidence):
                lookup([self.a], identity=identity)
        with self.assertRaises(MissingEvidence):
            lookup([self.a], key="")

    def test_exact_case_type_and_escaped_pointer(self):
        for wrong in ["MP-A", "mp-A-extra", True, 0]:
            with self.assertRaises(MissingEvidence):
                lookup([self.a], identity=wrong)
        with self.assertRaises(MissingEvidence):
            lookup([{"id": True, "value": 5}], identity=1, path="/value", key="id")
        self.assertEqual(
            lookup(
                [{"id": 0, "a/b": {"~v": [7]}}],
                identity=0,
                path="/a~1b/~0v/0",
                key="id",
            ),
            7,
        )


if __name__ == "__main__":
    unittest.main()
