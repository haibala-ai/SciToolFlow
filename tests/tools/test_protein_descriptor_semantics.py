"""Correct descriptor labels and group order; no sequence repair or design."""

import unittest

from tools.implementations.biology.extensions import (
    calculate_hydrophobicity_and_polarity,
    predict_secondary_structure,
)


class DescriptorSemanticsTests(unittest.TestCase):
    def test_turn_is_not_misreported_as_sheet(self):
        result = predict_secondary_structure("ACDEFGHIKLMNPQRSTVWY")
        self.assertIn("Helix-prone Residue Fraction**: `25.00%`", result)
        self.assertIn("Turn-prone Residue Fraction**: `25.00%`", result)
        self.assertIn("Sheet-prone Residue Fraction**: `35.00%`", result)
        self.assertIn("not predicted or observed", result)

    def test_isoelectric_point_is_not_called_polarity(self):
        result = calculate_hydrophobicity_and_polarity("ACDEFGHIKLMNPQRSTVWY")
        self.assertIn("Estimated Isoelectric Point (pI)", result)
        self.assertIn("pI is not molecular polarity", result)

    def test_noncanonical_symbols_are_rejected_instead_of_filtered(self):
        for function in [
            calculate_hydrophobicity_and_polarity,
            predict_secondary_structure,
        ]:
            with self.subTest(function=function.__name__):
                self.assertTrue(function("ACDX").startswith("Error"))
                self.assertTrue(function("").startswith("Error"))
                self.assertEqual(function("ACD"), function("a c\nd"))


if __name__ == "__main__":
    unittest.main()
