"""Offline boundary tests; mocked NeEMO tables are not scientific validation."""

from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from tools.implementations import adapters
from tools.implementations.biology import neemo_current
from tools.runtime.dispatch import normalize_output


class ConnectedConformerTests(unittest.TestCase):
    def test_disconnected_components_are_rejected_before_embedding(self):
        with patch("rdkit.Chem.AllChem.EmbedMolecule") as embed:
            for smiles in ("C.C", "CC(=O)[O-].[Na+]", "[Na+].[Cl-]"):
                with self.subTest(smiles=smiles):
                    with self.assertRaisesRegex(ValueError, "one connected molecule"):
                        adapters.generate_molecular_conformer(smiles, "both")
            embed.assert_not_called()

    def test_connected_molecule_keeps_seed_optimizer_and_atom_inventory(self):
        result = json.loads(adapters.generate_molecular_conformer("CCO"))
        self.assertEqual(result["random_seed"], 42)
        self.assertEqual(result["method"], "ETKDGv3 + MMFF94")
        self.assertEqual(result["coordinate_units"], "angstrom")
        self.assertEqual(result["atom_count"], 9)
        self.assertEqual(len(result["coordinates"]), 9)
        self.assertEqual(len(result["atoms"]), 9)
        self.assertFalse(result["experimental_structure"])


class NeemoPendingBoundaryTests(unittest.TestCase):
    def run_fixture(self, polls, mutation="", changes=None):
        # Every provider-side value below is a format fixture. No request is sent.
        processed = {"sequence": "A", "residues": [{"index": 1}], "hidden_fields": {}}
        local = {
            "source": "local structure preparation (NeEMO job still queued)",
            "accessibility_method": "Shrake-Rupley on the isolated chain",
            "accessibility_units": "angstrom^2; absolute area, not NeEMO relative accessibility percent",
            "residues": [],
        }
        with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
            stack.enter_context(
                patch.object(
                    neemo_current, "artifacts_root", return_value=Path(temporary)
                )
            )
            stack.enter_context(
                patch.object(neemo_current, "_session", return_value=MagicMock())
            )
            stack.enter_context(
                patch.object(
                    neemo_current,
                    "_submit_structure",
                    return_value={"pid": "fixture-structure"},
                )
            )
            stack.enter_context(patch.object(neemo_current, "_poll", side_effect=polls))
            parse = stack.enter_context(
                patch.object(neemo_current, "_parse_processed", return_value=processed)
            )
            local_prepare = stack.enter_context(
                patch.object(neemo_current, "_local_preparation", return_value=local)
            )
            submit_mutation = stack.enter_context(
                patch.object(
                    neemo_current, "_submit_mutation", return_value="fixture-mutation"
                )
            )
            stability = stack.enter_context(
                patch.object(
                    neemo_current, "_parse_stability", return_value=changes or []
                )
            )
            raw = neemo_current.neemo("1ABC", "A", mutation, wait_seconds=0)
            return (
                json.loads(raw),
                normalize_output(raw),
                parse.call_count,
                local_prepare.call_count,
                submit_mutation.call_count,
                stability.call_count,
            )

    def test_queued_structure_is_blocked_with_local_absolute_area_scope(self):
        result, normalized, parse, local, mutation, stability = self.run_fixture(
            [(False, "fixture queued", "running", "running")], "A1G"
        )
        self.assertEqual(result["status"], "queued")
        self.assertEqual(result["structure_job_status"], "queued")
        self.assertEqual(normalized["status"], "blocked")
        self.assertEqual(normalized["error_type"], "UpstreamPending")
        self.assertEqual(result["stability_changes"], [])
        self.assertNotIn("mutation_job", result)
        self.assertEqual((parse, local, mutation, stability), (0, 1, 0, 0))
        for phrase in (
            "local preparation",
            "first PDB model",
            "isolated selected chain",
            "angstrom^2",
            "not NeEMO relative",
        ):
            self.assertIn(phrase, result["scope"])
        self.assertIn("no stability change is estimated locally", result["scope"])

    def test_queued_structure_without_mutation_is_still_queued(self):
        result, normalized, *_ = self.run_fixture([(False, "", "running", "running")])
        self.assertEqual(result["status"], "queued")
        self.assertEqual(normalized["error_type"], "UpstreamPending")
        self.assertIn("structure job remains queued", result["stability_change_status"])

    def test_queued_mutation_does_not_turn_completed_structure_into_success(self):
        result, normalized, parse, local, mutation, stability = self.run_fixture(
            [
                (True, "structure fixture", "done", "finished"),
                (False, "mutation fixture", "running", "running"),
            ],
            "A1G",
        )
        self.assertEqual(result["status"], "queued")
        self.assertEqual(result["structure_job_status"], "finished")
        self.assertEqual(result["mutation_job"]["status"], "queued")
        self.assertEqual(result["stability_changes"], [])
        self.assertEqual(normalized["error_type"], "UpstreamPending")
        self.assertEqual((parse, local, mutation, stability), (1, 0, 1, 0))

    def test_completed_structure_without_mutation_is_completed(self):
        result, normalized, parse, local, mutation, stability = self.run_fixture(
            [(True, "structure fixture", "done", "finished")]
        )
        self.assertEqual(result["status"], "completed")
        self.assertEqual(normalized["status"], "success")
        self.assertEqual((parse, local, mutation, stability), (1, 0, 0, 0))
        self.assertNotIn("local preparation", result["scope"])

    def test_completed_mutation_requires_parsed_rows_and_completed_status(self):
        rows = [{"stability_change_kcal_per_mol": 0.125, "fixture_only": True}]
        result, normalized, parse, local, mutation, stability = self.run_fixture(
            [
                (True, "structure fixture", "done", "finished"),
                (True, "mutation fixture", "done", "finished"),
            ],
            "A1G",
            rows,
        )
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["stability_changes"], rows)
        self.assertEqual(normalized["status"], "success")
        self.assertEqual((parse, local, mutation, stability), (1, 0, 1, 1))

    def test_completed_mutation_without_parseable_rows_is_an_error(self):
        with self.assertRaisesRegex(RuntimeError, "no stability values were parseable"):
            self.run_fixture(
                [(True, "", "done", "finished"), (True, "", "done", "finished")], "A1G"
            )


if __name__ == "__main__":
    unittest.main()
