"""An API-free actor must not accidentally invoke a second LLM via a tool."""

import unittest
import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import Mock

from scripts.references.native_reference_session import invoke_native_tool
from evaluation.integrity.traces import canonical_sha256
from evaluation.integrity.reference import verify_generation_manifest


class NativeReferenceBoundaryTests(unittest.TestCase):
    def test_generation_manifest_hash_and_task_identity_are_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task = {"id": "FLOW-test", "question": "Public question"}
            path = root / "generation.json"
            manifest = {
                "actor_backend": "native_subagent",
                "model_api_used": False,
                "task_id": task["id"],
                "public_task_sha256": canonical_sha256(task),
                "source_sha256": {"code.py": "a" * 64},
                "input_asset_sha256": {},
            }
            path.write_text(json.dumps(manifest))
            provenance = {
                "generation_manifest": manifest,
                "task_identity": {
                    k: canonical_sha256(task)
                    for k in [
                        "current_public_task_sha256",
                        "generation_task_sha256",
                        "review_task_sha256",
                    ]
                },
                "generation_manifest_sha256": canonical_sha256(manifest),
            }
            verify_generation_manifest(root, task, provenance)
            manifest["model_api_used"] = True
            path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                verify_generation_manifest(root, task, provenance)
            provenance["generation_manifest_sha256"] = canonical_sha256(manifest)
            with self.assertRaisesRegex(ValueError, "manifest/task mismatch"):
                verify_generation_manifest(root, task, provenance)

    def test_language_model_helpers_blocked_before_execution_including_alias(self):
        catalog = Mock()
        catalog.canonical.side_effect = lambda name: {
            "code_alias": "CodeInterpreterTools"
        }.get(name, name)
        execute = Mock()
        for name in ["CodeInterpreterTools", "PaperQA", "code_alias"]:
            result = invoke_native_tool(name, {}, catalog=catalog, execute_tool=execute)
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["error_type"], "ReferenceGenerationHelperDisabled")
        execute.assert_not_called()

    def test_scientific_tools_still_use_the_real_executor_and_task_files(self):
        catalog = Mock()
        catalog.canonical.side_effect = lambda name: name
        execute = Mock(return_value={"status": "success", "output": {"value": 3}})
        result = invoke_native_tool(
            "ReadScientificRecords",
            {"snapshot_file": "input.json"},
            catalog=catalog,
            execute_tool=execute,
            files=["/public/input.json"],
            timeout=90,
        )
        self.assertEqual(result["output"], {"value": 3})
        execute.assert_called_once_with(
            "ReadScientificRecords",
            {"snapshot_file": "input.json"},
            catalog=catalog,
            files=["/public/input.json"],
            timeout=90,
        )


if __name__ == "__main__":
    unittest.main()
