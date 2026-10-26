"""Focused single-quantity index boundaries; short synthetic canonical examples only."""

import unittest
from unittest.mock import patch

from tools.implementations.biology.sequence_indices import (
    protein_aliphatic_index,
    protein_instability_index,
    protein_n_terminal_half_life,
)


class FinalDescriptorTests(unittest.TestCase):
    def test_aliphatic_coefficients_and_above100_are_preserved(self):
        self.assertAlmostEqual(
            protein_aliphatic_index("AVIL")["aliphatic_index"], 292.5
        )
        self.assertEqual(protein_aliphatic_index("I")["aliphatic_index"], 390)
        self.assertEqual(protein_aliphatic_index("GG")["aliphatic_index"], 0)
        self.assertEqual(
            protein_aliphatic_index("AVIL"), protein_aliphatic_index("LIVA")
        )

    def test_instability_adjacent_dipeptide_weights_and_order(self):
        self.assertAlmostEqual(protein_instability_index("AA")["instability_index"], 5)
        self.assertAlmostEqual(
            protein_instability_index("AC")["instability_index"], 224.7
        )
        self.assertAlmostEqual(protein_instability_index("CA")["instability_index"], 5)
        with self.assertRaises(ValueError):
            protein_instability_index("A")

    def test_half_life_preserves_system_units_bound_and_unknown(self):
        mammal = protein_n_terminal_half_life("AG", "mammalian_reticulocyte_in_vitro")
        self.assertEqual(
            mammal["half_life"],
            {"value": 4.4, "units": "hour", "relation": "table_point"},
        )
        yeast = protein_n_terminal_half_life("AG", "yeast_in_vivo")
        self.assertEqual(
            yeast["half_life"],
            {"value": 20, "units": "hour", "relation": "greater_than"},
        )
        arginine = protein_n_terminal_half_life("RG", "E_coli_in_vivo")
        self.assertEqual(
            arginine["half_life"],
            {"value": 2, "units": "minute", "relation": "table_point"},
        )
        proline = protein_n_terminal_half_life("PG", "E_coli_in_vivo")
        self.assertEqual(
            proline["half_life"], {"value": None, "units": None, "relation": "unknown"}
        )

    def test_encoded_n_terminus_is_not_silently_processed(self):
        first = protein_n_terminal_half_life("MA", "mammalian_reticulocyte_in_vitro")
        self.assertEqual(first["n_terminal_residue"], "M")
        self.assertEqual(first["half_life"]["value"], 30)
        self.assertEqual(
            first["half_life"],
            protein_n_terminal_half_life("MKK", "mammalian_reticulocyte_in_vitro")[
                "half_life"
            ],
        )

    def test_canonical_normalization_and_unsupported_inputs(self):
        self.assertEqual(protein_aliphatic_index("a v"), protein_aliphatic_index("AV"))
        for fn in (protein_aliphatic_index, protein_instability_index):
            for value in ("AX", "A*", "A-A", True, ""):
                with self.assertRaises(ValueError):
                    fn(value)
        with self.assertRaises(ValueError):
            protein_n_terminal_half_life("MA", "human_generic")

    def test_each_tool_returns_its_single_quantity_without_old_bundle(self):
        samples = [
            protein_aliphatic_index("AV"),
            protein_instability_index("AV"),
            protein_n_terminal_half_life("AV", "yeast_in_vivo"),
        ]
        forbidden = {
            "pI",
            "molecular_weight",
            "counts",
            "gravy",
            "extinction_coefficient",
            "smiles",
        }
        for value in samples:
            self.assertFalse(forbidden & set(value))

    def test_broad_report_is_explicitly_retired(self):
        from tools.implementations.biology.common import compute_protein_parameters

        with self.assertRaisesRegex(NotImplementedError, "single-tool replacement"):
            compute_protein_parameters("AV")

    def test_extinction_report_omits_unrelated_pi(self):
        from tools.implementations.biology.common import compute_extinction_coefficient

        report = compute_extinction_coefficient("WC")
        self.assertIn("Reduced epsilon (M^-1 cm^-1):** 5500", report)
        self.assertIn("A280 at 1 g/L, 1 cm (reduced)", report)
        self.assertNotIn("Isoelectric", report)

    def test_oligonucleotide_invalid_input_fails_before_request(self):
        from tools.implementations.biology import novopro_primitives as module

        with patch.object(module, "_result") as request:
            for fn in (
                module.oligonucleotide_melting_temperature,
                module.oligonucleotide_absorbance_properties,
            ):
                for value in ("ACGU", "ACGN", "", "AC.GT"):
                    with self.assertRaises(ValueError):
                        fn(value)
            request.assert_not_called()

    def test_oligonucleotide_failure_and_malformed_output_remain_errors(self):
        from tools.implementations.biology import novopro_primitives as module

        for fn in (
            module.oligonucleotide_melting_temperature,
            module.oligonucleotide_absorbance_properties,
        ):
            with patch.object(
                module, "_result", side_effect=RuntimeError("unavailable")
            ):
                with self.assertRaisesRegex(RuntimeError, "unavailable"):
                    fn("ACGT")
            with patch.object(module, "_result", return_value=[]):
                with self.assertRaisesRegex(RuntimeError, "schema"):
                    fn("ACGT")

    def test_composite_oligonucleotide_report_is_retired(self):
        from tools.implementations.biology.novopro_primitives import (
            oligonucleotide_properties,
        )

        with self.assertRaisesRegex(NotImplementedError, "unknown end-group"):
            oligonucleotide_properties("ACGT")


if __name__ == "__main__":
    unittest.main()
