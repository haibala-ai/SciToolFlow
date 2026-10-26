"""Offline primer-request identity checks; no remote scientific values tested."""

import json
import unittest
from unittest.mock import patch

from tools.implementations.biology.novopro import compute_primer_properties


class PrimerBatchIdentityTests(unittest.TestCase):
    def test_each_input_record_gets_a_unique_id_without_deduplicating_sequences(self):
        requests = []

        def transport_fixture(payload):
            requests.append(payload)
            lines = payload["sq"].splitlines()
            ids = lines[::2]
            sequences = lines[1::2]
            self.assertEqual(ids, [">sequence0", ">sequence1", ">sequence2"])
            self.assertEqual(len(set(ids)), 3)
            self.assertEqual(sequences, ["ACGT", "AAAA", "ACGT"])
            # This is a transport/format fixture, not a provider calculation.
            return json.dumps([1, "OFFLINE TRANSPORT FIXTURE: no scientific values"])

        with patch(
            "tools.implementations.biology.novopro.send_novopro_request",
            side_effect=transport_fixture,
        ):
            result = compute_primer_properties("ACGT.AAAA.ACGT")
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0]["sr"], "primerstat")
        self.assertIn(">sequence1\nAAAA\n>sequence2\nACGT", result)
        self.assertIn("OFFLINE TRANSPORT FIXTURE", result)

    def test_single_record_identity_and_existing_whitespace_policy_are_preserved(self):
        with patch(
            "tools.implementations.biology.novopro.send_novopro_request",
            return_value=json.dumps([1, "OFFLINE TRANSPORT FIXTURE"]),
        ) as transport:
            result = compute_primer_properties(" A C\nGT ")
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(transport.call_args.args[0]["sq"], ">sequence0\nACGT\n")
        self.assertIn(">sequence0\nACGT", result)


if __name__ == "__main__":
    unittest.main()
