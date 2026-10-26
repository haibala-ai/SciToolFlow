"""The standard model counts cystine pairs, never individual Cys as cystines."""

import re
import unittest
from unittest.mock import patch
from tools.implementations.biology.common import compute_extinction_coefficient


def field(text, name):
    return float(re.search(re.escape("**" + name + ":** ") + r"([\d.eE+-]+)", text)[1])


class ExtinctionSemanticsTest(unittest.TestCase):
    def test_cysteine_pairs_and_odd_remaining_cysteine(self):
        with patch(
            "tools.implementations.biology.common.send_novopro_request",
            side_effect=AssertionError("No provider dependency"),
        ):
            six = compute_extinction_coefficient("CCCCCC")
            self.assertEqual(field(six, "Reduced epsilon (M^-1 cm^-1)"), 0)
            self.assertEqual(field(six, "Fully paired epsilon (M^-1 cm^-1)"), 375)
            self.assertEqual(field(six, "Cystine pairs assumed"), 3)
            for sequence in ["CCY", "CCCY"]:
                result = compute_extinction_coefficient(sequence)
                self.assertEqual(
                    field(result, "Fully paired epsilon (M^-1 cm^-1)"), 1615
                )
                self.assertAlmostEqual(
                    field(result, "Reduced-chain mass (g/mol)")
                    - field(result, "Fully paired-chain mass (g/mol)"),
                    2.01588,
                    places=7,
                )

    def test_matching_mass_basis_no_aromatic_signal_and_no_fabricated_concentration(
        self,
    ):
        result = compute_extinction_coefficient(" wy cc \n")
        self.assertIn("`WYCC`", result)
        epsilon = 5500 + 1490 + 125
        self.assertEqual(field(result, "Fully paired epsilon (M^-1 cm^-1)"), epsilon)
        self.assertAlmostEqual(
            field(result, "A280 at 1 g/L, 1 cm (fully paired)"),
            epsilon / field(result, "Fully paired-chain mass (g/mol)"),
            places=10,
        )
        zero = compute_extinction_coefficient("GGG")
        self.assertEqual(field(zero, "Fully paired epsilon (M^-1 cm^-1)"), 0)
        self.assertIn(
            "Not determined; measured absorbance and path length are not inputs", zero
        )
        for invalid in [
            None,
            True,
            12,
            "",
            "AX",
            "A*",
            "A-C",
            ">header\nAC",
            "A" * 100001,
        ]:
            with self.subTest(type=type(invalid).__name__):
                self.assertTrue(
                    compute_extinction_coefficient(invalid).startswith(
                        "Error compute extinction coefficient:"
                    )
                )
