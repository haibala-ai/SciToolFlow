"""A new public question cannot inherit an old reference solely by task ID."""

import json
import hashlib
from pathlib import Path
import tempfile
import unittest

from evaluation.integrity.traces import canonical_sha256
from scripts.references.audit_workflow_design import current_reference_rows, rows


class ReferenceVersionTests(unittest.TestCase):
    def fixture_with_assets(self, directory):
        root = Path(directory)
        task = {
            "id": "FLOW-0001",
            "question": "same question",
            "files": ["asset://same.json"],
        }
        spec = {"nodes": ["reviewed rules"]}
        old_digest = hashlib.sha256(b"old actual asset").hexdigest()
        manifest = root / "generation.json"
        manifest.write_text(
            json.dumps(
                {"input_asset_sha256": {"/original/runtime/same.json": old_digest}}
            )
        )
        reference = {
            "id": task["id"],
            "evaluation": spec,
            "native_provenance": {
                "task_sha256": canonical_sha256(task),
                "generation_manifest": json.loads(manifest.read_text()),
                "task_identity": {"current_public_task_sha256": canonical_sha256(task)},
                "generation_manifest_sha256": canonical_sha256(
                    json.loads(manifest.read_text())
                ),
            },
        }
        path = root / "reference.jsonl"
        path.write_text(json.dumps(reference) + "\n")
        hidden = {
            task["id"]: {
                "evaluation": spec,
                "public_asset_sha256": {"same.json": old_digest},
            }
        }
        return root, task, hidden, path, manifest

    def test_same_question_and_filename_cannot_inherit_changed_asset_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root, task, hidden, path, manifest = self.fixture_with_assets(directory)
            old = (path.read_bytes(), manifest.read_bytes())
            selected, _ = current_reference_rows(
                [path], {task["id"]: task}, hidden, root
            )
            self.assertIn(task["id"], selected)
            hidden[task["id"]]["public_asset_sha256"]["same.json"] = hashlib.sha256(
                b"changed byte content"
            ).hexdigest()
            selected, versions = current_reference_rows(
                [path], {task["id"]: task}, hidden, root
            )
            self.assertEqual(selected, {})
            self.assertTrue(versions[0]["matches_current_public_identity"])
            self.assertTrue(versions[0]["matches_current_evaluation_identity"])
            self.assertFalse(versions[0]["matches_current_input_asset_identity"])
            self.assertEqual((path.read_bytes(), manifest.read_bytes()), old)

    def test_same_task_and_assets_cannot_inherit_changed_reviewed_rules(self):
        with tempfile.TemporaryDirectory() as directory:
            root, task, hidden, path, _ = self.fixture_with_assets(directory)
            hidden[task["id"]]["evaluation"] = {"nodes": ["different scientific rules"]}
            selected, versions = current_reference_rows(
                [path], {task["id"]: task}, hidden, root
            )
            self.assertEqual(selected, {})
            self.assertFalse(versions[0]["matches_current_evaluation_identity"])
            self.assertTrue(versions[0]["matches_current_input_asset_identity"])

    def test_absent_tampered_or_ambiguous_execution_inventory_is_not_current(self):
        with tempfile.TemporaryDirectory() as directory:
            root, task, hidden, path, manifest = self.fixture_with_assets(directory)
            reference = json.loads(path.read_text())
            reference["native_provenance"]["generation_manifest"] = {
                "input_asset_sha256": {}
            }
            path.write_text(json.dumps(reference) + "\n")
            selected, versions = current_reference_rows(
                [path], {task["id"]: task}, hidden, root
            )
            self.assertEqual(selected, {})
            self.assertIn("manifest hash", versions[0]["current_identity_error"])
            reference = json.loads(path.read_text())
            reference["native_provenance"].pop("generation_manifest")
            path.write_text(json.dumps(reference) + "\n")
            selected, _ = current_reference_rows(
                [path], {task["id"]: task}, hidden, root
            )
            self.assertEqual(selected, {})
            reference["native_provenance"]["generation_manifest"] = "../outside.json"
            path.write_text(json.dumps(reference) + "\n")
            selected, versions = current_reference_rows(
                [path], {task["id"]: task}, hidden, root
            )
            self.assertEqual(selected, {})
            self.assertIn("manifest hash", versions[0]["current_identity_error"])

    def test_every_declared_asset_must_have_unique_complete_current_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            root, task, hidden, path, _ = self.fixture_with_assets(directory)
            task["files"].append("asset://another.json")
            reference = json.loads(path.read_text())
            reference["native_provenance"]["task_identity"][
                "current_public_task_sha256"
            ] = canonical_sha256(task)
            path.write_text(json.dumps(reference) + "\n")
            selected, versions = current_reference_rows(
                [path], {task["id"]: task}, hidden, root
            )
            self.assertEqual(selected, {})
            self.assertIn("inventory differ", versions[0]["current_identity_error"])

    def test_exact_current_identity_only_and_all_history_visible(self):
        with tempfile.TemporaryDirectory() as directory:
            old = {"id": "FLOW-0001", "question": "old"}
            new = {"id": "FLOW-0001", "question": "revised"}
            paths = []
            for label, task in [("old", old), ("new", new)]:
                path = Path(directory) / (label + ".jsonl")
                path.write_text(
                    json.dumps(
                        {
                            "id": task["id"],
                            "native_provenance": {
                                "task_identity": {
                                    "current_public_task_sha256": canonical_sha256(task)
                                }
                            },
                            "expected_answer": label,
                        }
                    )
                    + "\n"
                )
                paths.append(path)
            selected, versions = current_reference_rows(paths, {new["id"]: new})
            self.assertEqual(selected[new["id"]]["expected_answer"], "new")
            self.assertEqual(
                [v["matches_current_public_identity"] for v in versions], [False, True]
            )
            self.assertEqual(len(versions), 2)
            selected, versions = current_reference_rows(
                paths, {"FLOW-0001": {"id": "FLOW-0001", "question": "another version"}}
            )
            self.assertEqual(selected, {})
            self.assertTrue(
                all(not v["matches_current_public_identity"] for v in versions)
            )
            with self.assertRaises(ValueError):
                current_reference_rows([paths[1], paths[1]], {new["id"]: new})
            with self.assertRaises(ValueError):
                rows(paths)  # Public/hidden duplicate protection was not relaxed.

    def test_missing_native_identity_cannot_claim_current_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reference.jsonl"
            path.write_text(json.dumps({"id": "FLOW-0001"}) + "\n")
            selected, versions = current_reference_rows(
                [path], {"FLOW-0001": {"id": "FLOW-0001"}}
            )
            self.assertEqual(selected, {})
            self.assertEqual(
                versions[0]["status"], "historical_identity_only_not_current_coverage"
            )
