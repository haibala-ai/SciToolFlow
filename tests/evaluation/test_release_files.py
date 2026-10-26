"""Current release file identities and explicit unit paths reject ambiguous input."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from evaluation.integrity.files import verify_file_identities
from evaluation.integrity.package import validate_unit_annotations


class ReleaseFileTests(unittest.TestCase):
    def test_declared_byte_size_and_hash_are_both_required(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            content = b"scientific input\n"
            (root / "input.txt").write_bytes(content)
            (root / "MANIFEST.json").write_text(
                json.dumps({"file_identities": "identities.json"})
            )
            item = {
                "file": "input.txt",
                "bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }

            def save():
                (root / "identities.json").write_text(
                    json.dumps({"files": {"input": item}})
                )

            save()
            self.assertEqual(verify_file_identities(root), 1)
            for size in [len(content) - 1, True, -1, "17", None]:
                item["bytes"] = size
                save()
                with (
                    self.subTest(size=size),
                    self.assertRaisesRegex(ValueError, "byte size"),
                ):
                    verify_file_identities(root)
            item["bytes"] = len(content)
            item["sha256"] = "0" * 64
            save()
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                verify_file_identities(root)

    def test_declared_file_cannot_escape_the_release(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = parent / "release"
            root.mkdir()
            (parent / "input.txt").write_bytes(b"x")
            (root / "MANIFEST.json").write_text(
                json.dumps({"file_identities": "identities.json"})
            )
            for relative in ["../input.txt", str(parent / "input.txt")]:
                (root / "identities.json").write_text(
                    json.dumps(
                        {
                            "files": {
                                "x": {
                                    "file": relative,
                                    "bytes": 1,
                                    "sha256": hashlib.sha256(b"x").hexdigest(),
                                }
                            }
                        }
                    )
                )
                with (
                    self.subTest(path=relative),
                    self.assertRaisesRegex(ValueError, "escapes"),
                ):
                    verify_file_identities(root)


class UnitPathTests(unittest.TestCase):
    def test_task_wide_description_does_not_invent_a_field_path(self):
        validate_unit_annotations(
            {"unit_annotations": [{"description": "Energies in eV per cell."}]},
            {"energy": 1.0},
        )
        for annotation in [
            {"description": ""},
            {"description": "  "},
            {"description": 1},
            {"description": "Energy", "unit": "eV"},
            {"description": "Energy", "path": "/missing"},
            {},
        ]:
            with self.subTest(annotation=annotation), self.assertRaises(ValueError):
                validate_unit_annotations(
                    {"unit_annotations": [annotation]}, {"energy": 1.0}
                )

    def test_exact_paths_support_escaped_keys_and_array_indices(self):
        answer = {"a/b": {"~x": [0.0, {"value": 7}]}}
        for path in ["/a~1b/~0x/1/value", ["a/b", "~x", 1, "value"], "", []]:
            with self.subTest(path=path):
                validate_unit_annotations(
                    {"unit_annotations": [{"path": path}]}, answer
                )

    def test_missing_or_ambiguous_paths_are_not_guessed(self):
        answer = {"a": [1, 2]}
        paths = [
            "a/0",
            "/missing",
            "/a/-1",
            "/a/01",
            "/a/2",
            "/a/~2",
            ["a", -1],
            ["a", True],
            ["a", "0"],
            None,
            0,
        ]
        for path in paths:
            with (
                self.subTest(path=path),
                self.assertRaisesRegex(ValueError, "Unresolvable"),
            ):
                validate_unit_annotations(
                    {"unit_annotations": [{"path": path}]}, answer
                )
        for malformed in [None, "a"]:
            with (
                self.subTest(annotation=malformed),
                self.assertRaisesRegex(ValueError, "Unresolvable"),
            ):
                validate_unit_annotations({"unit_annotations": [malformed]}, answer)
