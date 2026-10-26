"""Offline scientific boundaries, resource reuse and honest failure contracts.

Only synthetic short sequences, ethanol and generated coordinate fixtures.
No models are loaded and no remote successful scientific result is mocked.
"""

import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.implementations.adapters import (
    dna_molecular_weight,
    generate_molecular_conformer,
)
from tools.implementations.biology.sequence_primitives import (
    sequence_composition,
    pairwise_sequence_alignment,
)
from tools.implementations.biology.sequence_utilities_local import (
    digest_protein,
    generate_random_sequence,
)
from tools.implementations.biology.model_cache import cached_resource


def pdb_atom(serial, atom, chain, residue, insertion, x):
    element = atom[0]
    return (
        f"ATOM  {serial:5d} {atom:^4s} GLY {chain}{residue:4d}{insertion:1s}   "
        f"{x:8.3f}{0.0:8.3f}{0.0:8.3f}{1.0:6.2f}{20.0:6.2f}          {element:>2s}\n"
    )


class BiologyConsolidationTests(unittest.TestCase):
    def test_composition_has_explicit_denominator_and_alphabet(self):
        result = sequence_composition("g a\nG", "protein")
        self.assertEqual(result["length"], 3)
        self.assertEqual(result["counts"]["G"], 2)
        self.assertEqual(result["counts"]["W"], 0)
        self.assertAlmostEqual(sum(result["fractions"].values()), 1)
        for value in ("GX", "G-G", "G*", True):
            with self.assertRaises(ValueError):
                sequence_composition(value)

    def test_dna_end_group_chemistry_and_strict_flags(self):
        linear = json.loads(dna_molecular_weight("ACGT"))["molecular_weight"]
        circular = json.loads(dna_molecular_weight("ACGT", circular=True))[
            "molecular_weight"
        ]
        double_linear = json.loads(dna_molecular_weight("ACGT", double_stranded=True))[
            "molecular_weight"
        ]
        double_circular = json.loads(dna_molecular_weight("ACGT", True, True))[
            "molecular_weight"
        ]
        self.assertAlmostEqual(linear - circular, 18.0153, places=4)
        self.assertAlmostEqual(double_linear - double_circular, 36.0306, places=4)
        self.assertAlmostEqual(
            double_linear, 2 * linear, places=7
        )  # Self-complementary fixture.
        for arguments in (("ACGN",), ("ACGT", 1), (True,)):
            with self.assertRaises(ValueError):
                dna_molecular_weight(*arguments)

    def test_alignment_modes_preserve_distinct_objectives(self):
        global_result = pairwise_sequence_alignment("GGAC", "AC")
        local_result = pairwise_sequence_alignment("GGAC", "AC", mode="local")
        self.assertGreater(local_result["score"], global_result["score"])
        self.assertEqual(local_result["aligned_column_count"], 2)
        self.assertEqual(local_result["identity_fraction"], 1)
        self.assertEqual(global_result["aligned_column_count"], 4)
        with self.assertRaises(ValueError):
            pairwise_sequence_alignment("ACX", "AC")

    def test_digest_coordinates_missed_cleavages_and_mass_basis(self):
        sequence = "AKRA"
        digest = json.loads(digest_protein(sequence))
        for row in digest["peptides"]:
            self.assertEqual(row["sequence"], sequence[row["start"] : row["end"]])
        missed = json.loads(digest_protein(sequence, missed_cleavages=1))
        self.assertGreater(len(missed["peptides"]), len(digest["peptides"]))
        masses = json.loads(
            digest_protein("GG", enzyme="no cleavage", include_masses=True)
        )
        monoisotopic = masses["peptides"][0]["neutral_monoisotopic_mass_dalton"]
        self.assertAlmostEqual(monoisotopic, 132.05349, places=4)
        from Bio.SeqUtils import molecular_weight

        self.assertNotAlmostEqual(
            monoisotopic, molecular_weight("GG", seq_type="protein"), places=2
        )
        for kwargs in (
            {"enzyme": "trypsin/p"},
            {"missed_cleavages": True},
            {"include_masses": 1},
        ):
            with self.assertRaises(ValueError):
                digest_protein("AKP", **kwargs)

    def test_random_sampling_integer_boundary_preserves_existing_seed(self):
        first = json.loads(generate_random_sequence(length=8, seed=42))
        self.assertEqual(first, json.loads(generate_random_sequence(length=8, seed=42)))
        for kwargs in ({"length": True}, {"length": 3, "seed": False}):
            with self.assertRaises(ValueError):
                generate_random_sequence(**kwargs)

    def test_remote_validation_does_not_make_requests(self):
        from tools.implementations.biology import novopro_primitives as remote

        with patch.object(
            remote,
            "_request",
            side_effect=AssertionError("No remote calls in this test"),
        ) as request:
            cases = [
                (remote.hydrophilicity_profile, ("GX",), {}),
                (remote.optimize_codons, ("ACGU",), {"input_type": "RNA"}),
                (remote.oligonucleotide_melting_temperature, ("ACGU",), {}),
                (remote.find_sequence_repeats, ("ACGT",), {"minimum_length": True}),
            ]
            for function, args, kwargs in cases:
                with self.assertRaises(ValueError):
                    function(*args, **kwargs)
            self.assertEqual(request.call_count, 0)

    def test_unsupported_mutation_and_dummy_cell_fail_explicitly(self):
        from tools.implementations.biology.mutabind2_local import mutabind2
        from tools.implementations.biology.protein_tools import fix_pdb_file

        with self.assertRaises(NotImplementedError):
            mutabind2("0000", mutation="A1G")
        with self.assertRaises(NotImplementedError):
            fix_pdb_file("unused.pdb", "unused_out.pdb")

    def test_neemo_failure_status_is_not_finished_scientific_output(self):
        from tools.implementations.biology.neemo_current import _finished

        self.assertFalse(_finished("Status: Failed The request was invalid"))
        self.assertFalse(_finished("Status: Running The job is queued"))

    def test_legacy_provider_failure_is_not_a_scientific_payload(self):
        from tools.implementations.biology.novopro import _novopro_result

        for response in ('[0, "Failed"]', '{"status": "failed"}', "not a payload"):
            with self.assertRaises(RuntimeError):
                _novopro_result(response, "negative transport fixture")

    def test_peptide_graph_composes_with_the_existing_formula_and_weight_kernels(self):
        from tools.implementations.biology.peptide_molecule import peptide_to_smiles
        from rdkit import Chem
        from rdkit.Chem import Descriptors, rdMolDescriptors
        from Bio.SeqUtils import molecular_weight

        result = peptide_to_smiles("g g")
        molecule = Chem.MolFromSmiles(result["smiles"])
        self.assertEqual(result["sequence_length"], 2)
        self.assertEqual(rdMolDescriptors.CalcMolFormula(molecule), "C4H8N2O3")
        # Both are average molar mass, but atomic and residue tables are not digitwise equal.
        self.assertGreater(
            abs(
                Descriptors.MolWt(molecule) - molecular_weight("GG", seq_type="protein")
            ),
            0.0001,
        )
        alanine = Chem.MolFromSmiles(peptide_to_smiles("A")["smiles"])
        self.assertEqual(
            [code for _, code in Chem.FindMolChiralCenters(alanine)], ["S"]
        )
        cysteines = Chem.MolFromSmiles(peptide_to_smiles("CC")["smiles"])
        self.assertFalse(
            any(
                b.GetBeginAtom().GetSymbol() == b.GetEndAtom().GetSymbol() == "S"
                for b in cysteines.GetBonds()
            )
        )
        for text in ("GX", "G*", "G-G", ">header\nGG", "GG-NH2"):
            with self.assertRaises(ValueError):
                peptide_to_smiles(text)

    def test_retired_peptide_property_wrappers_do_not_return_duplicate_reports(self):
        from tools.implementations.adapters import peptide_weight, peptide_formula
        from tools.implementations.biology.novopro_current import peptide_properties

        for function in (peptide_weight, peptide_formula, peptide_properties):
            with self.assertRaises(NotImplementedError):
                function("GG")

    def test_pi_and_gravy_are_separate_quantities_with_explicit_methods(self):
        from tools.implementations.biology.protein_descriptors import (
            protein_isoelectric_point,
            protein_gravy,
        )
        from Bio.SeqUtils.IsoelectricPoint import IsoelectricPoint

        # Glycylglycine has only free terminal charge groups: pI=(7.5+3.55)/2.
        pI = protein_isoelectric_point("GG", method="biopython")
        self.assertAlmostEqual(pI["pI"], 5.525, places=4)
        self.assertNotIn("gravy", pI)
        acidic = protein_isoelectric_point("DDD", method="biopython")
        self.assertLess(acidic["pI"], 4.05)
        self.assertLess(abs(IsoelectricPoint("DDD").charge_at_pH(acidic["pI"])), 0.001)
        gravy = protein_gravy("AV")
        self.assertAlmostEqual(gravy["gravy"], 3.0)
        self.assertNotIn("pI", gravy)
        with self.assertRaises(NotImplementedError):
            protein_isoelectric_point("GG", method="unverified")

    def test_mass_weighted_center_and_explicit_distance_indices(self):
        from tools.implementations.biology.extensions import (
            calculate_center_of_mass,
            calculate_atom_distance,
        )

        with (
            tempfile.TemporaryDirectory() as folder,
            patch.dict(os.environ, {"SCITOOLFLOW_ARTIFACTS_DIR": folder}),
        ):
            path = Path(folder) / "synthetic.pdb"
            path.write_text(
                pdb_atom(1, "C", "A", 1, " ", 0)
                + pdb_atom(2, "O", "A", 1, " ", 3)
                + "END\n"
            )
            center = json.loads(calculate_center_of_mass(str(path)))
            self.assertGreater(center["center_of_mass"][0], 1.5)
            distance = json.loads(calculate_atom_distance(str(path), 1, 0))
            self.assertEqual(distance["distance_angstrom"], 3)
            self.assertEqual(distance["atom_indices_zero_based"], [1, 0])
            self.assertEqual(center["source_sha256"], distance["source_sha256"])
            with self.assertRaises(ValueError):
                calculate_atom_distance(str(path), True, 0)

    def test_csv_artifacts_are_unique_and_reject_inconsistent_columns(self):
        from tools.implementations.biology.protein_tools import save_to_csv_file

        with (
            tempfile.TemporaryDirectory() as folder,
            patch.dict(os.environ, {"SCITOOLFLOW_ARTIFACTS_DIR": folder}),
        ):
            first = json.loads(save_to_csv_file('[{"b": 2, "a": 1}]'))
            second = json.loads(save_to_csv_file('[{"b": 3, "a": 4}]'))
            self.assertNotEqual(first["csv_path"], second["csv_path"])
            self.assertEqual(Path(first["csv_path"]).read_text().splitlines()[0], "b,a")
            for data in ('[{"a":1},{"b":2}]', '{"a":[1,2],"b":[3]}', '[{"a":{"x":1}}]'):
                with self.assertRaises(ValueError):
                    save_to_csv_file(data)

    def test_coordinate_inspection_and_contacts_share_exact_fixture_identity(self):
        from tools.implementations.biology.research_workflows import inspect_pdb_quality
        from tools.implementations.biology.mutabind2_local import pdb_interface_contacts

        with (
            tempfile.TemporaryDirectory() as folder,
            patch.dict(os.environ, {"SCITOOLFLOW_ARTIFACTS_DIR": folder}),
        ):
            path = Path(folder) / "synthetic.pdb"
            text = pdb_atom(1, "CA", "A", 1, " ", 0) + pdb_atom(2, "CA", "A", 1, "A", 1)
            text += pdb_atom(3, "CA", "B", 1, " ", 3) + "END\n"
            path.write_text(text)
            quality = inspect_pdb_quality(str(path))
            contacts = json.loads(pdb_interface_contacts(str(path), minimum_contacts=1))
            expected = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(quality["source_sha256"], expected)
            self.assertEqual(contacts["source_sha256"], expected)
            self.assertEqual(
                quality["models"][0]["chains"][0]["residue_ids"], ["1", "1A"]
            )
            self.assertEqual(
                contacts["interfaces"][0]["interface_residue_counts"]["A"], 2
            )
            self.assertFalse(contacts["binding_affinity_or_mutation_prediction"])
            self.assertFalse(contacts["buried_surface"]["computed"])

    def test_real_ethanol_conformer_coordinates_and_artifact(self):
        with (
            tempfile.TemporaryDirectory() as folder,
            patch.dict(os.environ, {"SCITOOLFLOW_ARTIFACTS_DIR": folder}),
        ):
            result = json.loads(generate_molecular_conformer("CCO", "both"))
            self.assertEqual(result["atom_count"], 9)
            self.assertEqual(len(result["coordinates"]), result["atom_count"])
            self.assertEqual(len(result["atoms"]), result["atom_count"])
            self.assertTrue(Path(result["pdb_path"]).is_relative_to(Path(folder)))
            self.assertEqual(
                sum(
                    line.startswith("HETATM")
                    for line in Path(result["pdb_path"]).read_text().splitlines()
                ),
                9,
            )
            self.assertEqual(result["random_seed"], 42)

    def test_resource_factory_reused_and_file_version_invalidates(self):
        with tempfile.TemporaryDirectory() as folder:
            checkpoint = Path(folder)
            weight = checkpoint / "model.bin"
            weight.write_bytes(b"first")
            calls = []

            def factory():
                calls.append(1)
                return (
                    object()
                )  # Resource lifetime only; no fake model output/inference.

            first = cached_resource("test_biology_factory", checkpoint, factory)
            second = cached_resource("test_biology_factory", checkpoint, factory)
            self.assertIs(first, second)
            self.assertEqual(
                len(calls), 1
            )  # Baseline direct factory twice would load twice.
            weight.write_bytes(b"changed checkpoint")
            third = cached_resource("test_biology_factory", checkpoint, factory)
            self.assertIsNot(first, third)
            self.assertEqual(len(calls), 2)


class ObservedDiversityBoundaryTests(unittest.TestCase):
    def test_observed_simpson_quantities_and_zero_categories(self):
        from tools.implementations.biology.research_workflows import diversity_indices

        result = diversity_indices([1, 1, 0])
        self.assertEqual(result["richness"], 2)
        self.assertEqual(result["simpson_concentration"], 0.5)
        self.assertEqual(result["gini_simpson"], 0.5)
        self.assertEqual(result["inverse_simpson"], 2.0)
        self.assertAlmostEqual(result["pielou_evenness"], 1.0)
        self.assertNotEqual(
            result["simpson_concentration"], 0.0
        )  # Distinct finite-sample estimator.

    def test_empty_abundance_and_single_category_keep_defined_boundaries(self):
        from tools.implementations.biology.research_workflows import diversity_indices

        zero = diversity_indices([0, 0])
        for field in [
            "shannon_nats",
            "simpson_concentration",
            "gini_simpson",
            "inverse_simpson",
            "pielou_evenness",
        ]:
            self.assertIsNone(zero[field])
        single = diversity_indices([0, 5])
        self.assertEqual(single["simpson_concentration"], 1.0)
        self.assertEqual(single["inverse_simpson"], 1.0)
        self.assertEqual(single["gini_simpson"], 0.0)
        self.assertIsNone(single["pielou_evenness"])

    def test_extreme_counts_do_not_become_nonfinite_or_silent_zero_probabilities(self):
        from tools.implementations.biology.research_workflows import diversity_indices

        for counts in [[1e308, 1e308], [1e-308, 1e308], [True], [-1], [float("nan")]]:
            with self.subTest(counts=counts), self.assertRaises(ValueError):
                diversity_indices(counts)


if __name__ == "__main__":
    unittest.main()
