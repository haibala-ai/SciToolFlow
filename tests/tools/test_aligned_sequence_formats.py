"""Exercise the registered aligned-similarity format contract and boundaries."""

import json
import unittest

from tools.implementations.adapters import aligned_sequence_similarity


class AlignedSequenceFormats(unittest.TestCase):
    def test_fasta_headers_are_not_legacy_separators(self):
        result = json.loads(
            aligned_sequence_similarity(">source:A\nACD-\n>source:B\nAC--\n")
        )
        self.assertEqual(result["pairs"][0]["compared_columns"], 3)
        self.assertAlmostEqual(result["pairs"][0]["identity_percent"], 200 / 3)
        self.assertEqual(result["residue_groups"], [])

    def test_legacy_explicit_similarity_groups(self):
        result = json.loads(aligned_sequence_similarity("AIL.AVL:IV"))
        self.assertAlmostEqual(result["pairs"][0]["identity_percent"], 200 / 3)
        self.assertEqual(result["pairs"][0]["similarity_percent"], 100)

    def test_gcg_msf_alignment(self):
        text = """PileUp

   MSF: 4  Type: P  Check: 0  ..

 Name: one Len: 4 Check: 0 Weight: 1.00
 Name: two Len: 4 Check: 0 Weight: 1.00

//

one ACD.
two AC..
"""
        result = json.loads(aligned_sequence_similarity(text))
        self.assertEqual(result["pairs"][0]["compared_columns"], 3)
        self.assertAlmostEqual(result["pairs"][0]["identity_percent"], 200 / 3)

    def test_unequal_alignment_and_all_gap_pair_rejected(self):
        for text in [">a\nACD\n>b\nAC\n", ">a\n---\n>b\n---\n"]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                aligned_sequence_similarity(text)

    def test_invalid_legacy_format_explains_supported_inputs(self):
        with self.assertRaisesRegex(ValueError, "aligned FASTA, GCG/MSF"):
            aligned_sequence_similarity("ACD.ACD")


if __name__ == "__main__":
    unittest.main()
