import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.maintenance.prepare_resources import prepare


class ResourceInstallTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.bundle = self.root / "bundle"
        self.bundle.mkdir()
        self.destination = self.root / "installed"
        self.records = {}
        for relative, component in [
            ("source/main.py", "source"),
            ("model/value.json", "model"),
        ]:
            data = (component + "\n").encode()
            path = self.bundle / relative
            path.parent.mkdir(parents=True)
            path.write_bytes(data)
            self.records[relative] = {
                "component": component,
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        (self.bundle / "manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": "scitoolflow.resources.v1",
                    "components": [{"id": "source"}, {"id": "model"}],
                    "files": self.records,
                }
            )
        )

    def test_offline_install_is_idempotent_and_checkable(self):
        result = prepare(self.bundle, self.destination)
        self.assertTrue(result["ready"])
        self.assertEqual(result["installed"], 2)
        self.assertEqual(result["network_requests"], 0)
        again = prepare(self.bundle, self.destination)
        self.assertEqual(again["installed"], 0)
        self.assertEqual(again["verified_existing"], 2)
        self.assertTrue(prepare(self.bundle, self.destination, check=True)["ready"])

    def test_changed_user_file_is_never_replaced_or_partially_installed(self):
        path = self.destination / "source/main.py"
        path.parent.mkdir(parents=True)
        path.write_text("user changes")
        result = prepare(self.bundle, self.destination)
        self.assertFalse(result["ready"])
        self.assertEqual(result["conflicts"], ["source/main.py"])
        self.assertEqual(path.read_text(), "user changes")
        self.assertFalse((self.destination / "model/value.json").exists())

    def test_source_corruption_rejects_entire_copy(self):
        (self.bundle / "model/value.json").write_text("bad")
        with self.assertRaisesRegex(ValueError, "SHA256"):
            prepare(self.bundle, self.destination)
        self.assertFalse(self.destination.exists())

    def test_destination_symlink_cannot_write_outside_install_root(self):
        outside = self.root / "outside"
        outside.mkdir()
        self.destination.mkdir()
        (self.destination / "source").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            prepare(self.bundle, self.destination)
        self.assertEqual(list(outside.iterdir()), [])

    def test_selected_check_does_not_create_files(self):
        result = prepare(self.bundle, self.destination, selected=["source"], check=True)
        self.assertEqual(result["missing"], 1)
        self.assertFalse(self.destination.exists())
        with self.assertRaisesRegex(ValueError, "Unknown"):
            prepare(self.bundle, self.destination, selected=["nonexistent"])

    def make_chunked_model(self):
        data = b"checkpoint bytes, not a serialized model"
        parts = []
        for index, chunk in enumerate((data[:9], data[9:])):
            relative = f"chunks/model.part{index}"
            path = self.bundle / relative
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(chunk)
            parts.append(
                {
                    "path": relative,
                    "bytes": len(chunk),
                    "sha256": hashlib.sha256(chunk).hexdigest(),
                }
            )
        manifest_path = self.bundle / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["schema_version"] = "scitoolflow.resources.v2"
        manifest["files"]["model/weights.ckpt"] = {
            "component": "model",
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "parts": parts,
        }
        manifest_path.write_text(json.dumps(manifest))
        return data, parts, manifest

    def test_chunks_restore_exact_bytes_without_model_loading(self):
        data, _, _ = self.make_chunked_model()
        self.assertTrue(prepare(self.bundle, self.destination)["ready"])
        self.assertEqual((self.destination / "model/weights.ckpt").read_bytes(), data)
        self.assertTrue(prepare(self.bundle, self.destination, check=True)["ready"])
        self.assertFalse((self.destination / "chunks").exists())

    def test_missing_or_corrupt_chunk_prevents_any_installation(self):
        _, parts, _ = self.make_chunked_model()
        path = self.bundle / parts[1]["path"]
        path.write_bytes(b"X" * parts[1]["bytes"])
        with self.assertRaisesRegex(ValueError, "SHA256"):
            prepare(self.bundle, self.destination)
        self.assertFalse(self.destination.exists())
        path.unlink()
        with self.assertRaisesRegex(ValueError, "SHA256"):
            prepare(self.bundle, self.destination)
        self.assertFalse(self.destination.exists())

    def test_reordered_chunks_fail_whole_file_checksum(self):
        _, _, manifest = self.make_chunked_model()
        manifest["files"]["model/weights.ckpt"]["parts"].reverse()
        (self.bundle / "manifest.json").write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "Reassembled"):
            prepare(self.bundle, self.destination)
        self.assertFalse(self.destination.exists())

    def test_chunk_path_cannot_escape_bundle(self):
        _, _, manifest = self.make_chunked_model()
        manifest["files"]["model/weights.ckpt"]["parts"][0]["path"] = "../outside"
        (self.bundle / "manifest.json").write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "Invalid resource path"):
            prepare(self.bundle, self.destination)
        self.assertFalse(self.destination.exists())


if __name__ == "__main__":
    unittest.main()
