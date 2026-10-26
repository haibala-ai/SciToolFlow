"""Mixed-format uploads must remain available without changing legacy selection."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.runtime.config import Config, UPLOAD_CONTEXT
from tools.runtime.dispatch import REGISTRY, invoke_here
from tools.implementations.general.research_data import read_scientific_records


class MixedAttachmentTests(unittest.TestCase):
    def setUp(self):
        self.registry_patch = patch.dict(REGISTRY["tools"], {"stub": {}})
        self.registry_patch.start()
        self.addCleanup(self.registry_patch.stop)

    def test_same_format_in_different_directories_has_no_global_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = []
            for name in ("first", "second"):
                parent = root / name
                parent.mkdir()
                path = parent / (name + ".json")
                path.write_text(json.dumps([{"id": name}]))
                files.append(path)
            for attachments in (files, list(reversed(files))):
                with (
                    self.subTest(order=[p.name for p in attachments]),
                    patch(
                        "tools.runtime.dispatch.resolve_function",
                        return_value=read_scientific_records,
                    ),
                ):
                    result = invoke_here(
                        "stub",
                        json.dumps({"snapshot_file": "first.json", "id_field": "id"}),
                        [str(p) for p in attachments],
                    )
                self.assertEqual(result["records"], [{"id": "first"}])
            self.assertEqual(UPLOAD_CONTEXT.get(), {})

    def test_duplicate_uploaded_basenames_require_an_explicit_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for name in ("first", "second"):
                parent = Path(directory) / name
                parent.mkdir()
                path = parent / "records.json"
                path.write_text(json.dumps([{"id": name}]))
                paths.append(path)
            with patch(
                "tools.runtime.dispatch.resolve_function",
                return_value=read_scientific_records,
            ):
                with self.assertRaises(ValueError):
                    invoke_here(
                        "stub",
                        json.dumps({"snapshot_file": "records.json", "id_field": "id"}),
                        [str(p) for p in paths],
                    )
                result = invoke_here(
                    "stub",
                    json.dumps({"snapshot_file": str(paths[0]), "id_field": "id"}),
                    [str(p) for p in paths],
                )
                self.assertEqual(result["records"], [{"id": "first"}])
            self.assertEqual(UPLOAD_CONTEXT.get(), {})

    def test_mixed_formats_both_orders_preserve_json_access(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            json_dir, structure_dir = root / "records", root / "structures"
            json_dir.mkdir()
            structure_dir.mkdir()
            data = json_dir / "records.json"
            data.write_text(json.dumps([{"id": "A", "value": 2}]))
            structure = structure_dir / "example.cif"
            structure.write_text("data_example\n")

            def reader(snapshot_file):
                context = Config()
                records = read_scientific_records(snapshot_file, id_field="id")
                return (
                    records,
                    context.UPLOAD_FILES_PATHS,
                    context.ALL_UPLOAD_FILES_PATHS,
                )

            for attachments in [[data, structure], [structure, data]]:
                with (
                    self.subTest(order=[p.suffix for p in attachments]),
                    patch(
                        "tools.runtime.dispatch.resolve_function", return_value=reader
                    ),
                ):
                    result, legacy, complete = invoke_here(
                        "stub",
                        json.dumps({"snapshot_file": data.name}),
                        [str(p) for p in attachments],
                    )
                self.assertEqual(result["records"], [{"id": "A", "value": 2}])
                self.assertEqual(legacy, [str(attachments[-1])])
                self.assertEqual(set(complete), {str(data), str(structure)})
            self.assertEqual(UPLOAD_CONTEXT.get(), {})

    def test_unattached_private_path_still_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "private.json"
            path.write_text('[{"id":"A"}]')
            with self.assertRaises(PermissionError):
                read_scientific_records(str(path), id_field="id")

    def test_wrong_default_identity_feedback_exposes_schema_not_record_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "standards.json"
            path.write_text('[{"record_id":"sample-value-not-feedback","x":3}]')
            token = UPLOAD_CONTEXT.set({"all_paths": [str(path)]})
            try:
                with self.assertRaises(ValueError) as caught:
                    read_scientific_records(str(path))
                message = str(caught.exception)
                self.assertIn("record_id", message)
                self.assertIn("Set id_field", message)
                self.assertNotIn("sample-value-not-feedback", message)
            finally:
                UPLOAD_CONTEXT.reset(token)


if __name__ == "__main__":
    unittest.main()
