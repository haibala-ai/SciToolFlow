"""Partition names may change; specimen pairing and noise semantics may not."""

import unittest
from evaluation.workflow import operand, MissingEvidence


def profile(labels, noise=False):
    return operand(
        {
            "operation": "partition_profile",
            "args": [{"value": labels}, {"value": noise}],
        },
        {},
    )


class PartitionProfileTests(unittest.TestCase):
    def test_global_bijection_preserves_partition_but_row_shuffle_does_not(self):
        self.assertEqual(
            profile([0, 0, 1, 2, 1]), profile(["oak", "oak", "pine", "elm", "pine"])
        )
        self.assertNotEqual(profile([0, 0, 1, 2, 1]), profile([0, 1, 0, 2, 1]))
        self.assertNotEqual(profile([0, 0, 1, 2, 1]), profile([0, 0, 1, 1, 1]))
        self.assertNotEqual(profile([0, 0, 1, 2, 1]), profile([0, 0, 1, 2]))

    def test_noise_has_context_specific_semantics(self):
        self.assertEqual(profile([-1, 0, 0, 1]), profile([4, 2, 2, 7]))
        self.assertNotEqual(profile([-1, 0, 0, 1], True), profile([4, 2, 2, 7], True))
        self.assertEqual(
            profile([-1, 0, 0, 1], True), profile([-1, "a", "a", "b"], True)
        )
        self.assertNotEqual(
            profile([-1, 0, 0, 1], True), profile(["-1", 0, 0, 1], True)
        )

    def test_label_type_and_multiplicity_are_preserved(self):
        self.assertEqual(profile([0, "0", 0, "0"])["memberships"], [0, 1, 0, 1])
        self.assertEqual(profile([2, 2, 2])["memberships"], [0, 0, 0])
        self.assertEqual(len(profile([0] * 10000)["memberships"]), 10000)

    def test_reject_missing_or_invalid_labels_and_policy(self):
        for labels, policy in [
            ([], False),
            ([1] * 10001, False),
            ([True], False),
            ([None], False),
            ([1.0], False),
            ([[]], False),
            ([{}], False),
            (["x" * 2000001], False),
            ([1], 0),
        ]:
            with (
                self.subTest(labels=str(labels)[:30]),
                self.assertRaises(MissingEvidence),
            ):
                profile(labels, policy)


if __name__ == "__main__":
    unittest.main()
