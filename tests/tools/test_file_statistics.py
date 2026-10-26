"""Complete-family correction and per-task artifact access boundaries."""

import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.implementations.general.research_data import (
    _public_source_path,
    read_scientific_records,
)
from tools.implementations.machine_learning.file_statistics import adjust_p_values_file
from tools.runtime.config import UPLOAD_CONTEXT


class FileStatisticsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.artifacts = self.root / "task_a/artifacts"
        self.artifacts.mkdir(parents=True)
        self.source = self.root / "input.json"
        self.source.write_text(
            json.dumps(
                {
                    "data": [
                        {"gene_id": "a", "p_value": 0.01, "testable": True},
                        {"gene_id": "b", "p_value": 0.04, "testable": True},
                        {"gene_id": "c", "p_value": 0.03, "testable": True},
                        {"gene_id": "d", "p_value": None, "testable": False},
                        {"gene_id": "e", "p_value": 0.001, "testable": False},
                    ],
                    "model": {"input_gene_count": 5},
                }
            )
        )
        self.env = patch.dict(
            os.environ, {"SCITOOLFLOW_ARTIFACTS_DIR": str(self.artifacts)}
        )
        self.env.start()
        self.addCleanup(self.env.stop)
        self.token = UPLOAD_CONTEXT.set({"all_paths": [str(self.source)]})
        self.addCleanup(UPLOAD_CONTEXT.reset, self.token)

    def test_complete_declared_family_preserves_null_excluded_rows_and_metadata(self):
        result = adjust_p_values_file(str(self.source), eligibility_field="testable")
        output = json.loads(Path(result["results_file"]).read_text())
        self.assertEqual(result["family_size"], 3)
        self.assertEqual(result["input_record_count"], 5)
        self.assertEqual(result["null_p_value_count"], 1)
        self.assertEqual(result["excluded_valid_p_value_count"], 1)
        self.assertEqual(output["model"], {"input_gene_count": 5})
        self.assertEqual([r["gene_id"] for r in output["data"]], list("abcde"))
        self.assertEqual(
            [r["adjusted_p_value"] for r in output["data"]],
            [0.03, 0.04, 0.04, None, None],
        )
        self.assertEqual(
            hashlib.sha256(Path(result["results_file"]).read_bytes()).hexdigest(),
            result["results_sha256"],
        )
        read = read_scientific_records(result["results_file"], ["c", "d"], "gene_id")
        self.assertEqual([row["gene_id"] for row in read["records"]], ["c", "d"])
        self.assertIsNone(read["records"][1]["adjusted_p_value"])
        self.assertEqual(read["verified_provenance"]["family_size"], 3)

    def test_default_family_includes_every_nonnull_value(self):
        result = adjust_p_values_file(str(self.source))
        self.assertEqual(result["family_size"], 4)
        output = json.loads(Path(result["results_file"]).read_text())
        self.assertAlmostEqual(output["data"][4]["adjusted_p_value"], 0.004)

    def test_by_and_bonferroni_independent_expected_values(self):
        for method, expected in [
            ("bonferroni", [0.03, 0.12, 0.09]),
            ("by", [0.055, 0.07333333333333333, 0.07333333333333333]),
        ]:
            with self.subTest(method=method):
                result = adjust_p_values_file(
                    str(self.source), method, eligibility_field="testable"
                )
                output = json.loads(Path(result["results_file"]).read_text())
                for row, value in zip(output["data"], expected):
                    self.assertAlmostEqual(row["adjusted_p_value"], value)

    def test_null_family_is_preserved_without_imputation(self):
        self.source.write_text('[{"gene_id":"z","p_value":null}]')
        result = adjust_p_values_file(str(self.source))
        self.assertEqual(result["family_size"], 0)
        self.assertIsNone(
            json.loads(Path(result["results_file"]).read_text())["data"][0][
                "adjusted_p_value"
            ]
        )

    def test_malformed_rows_do_not_create_partial_output(self):
        bad_rows = [
            [{"gene_id": "a", "p_value": 0.1}, {"gene_id": "a", "p_value": 0.2}],
            [{"gene_id": "a"}],
            [{"gene_id": "a", "p_value": True}],
            [{"gene_id": "a", "p_value": 1.1}],
            [{"gene_id": "a", "p_value": 0.1, "adjusted_p_value": 0.1}],
        ]
        for rows in bad_rows:
            with self.subTest(rows=rows):
                self.source.write_text(json.dumps(rows))
                with self.assertRaises(ValueError):
                    adjust_p_values_file(str(self.source))
        self.assertEqual(list(self.artifacts.iterdir()), [])

    def test_bad_eligibility_is_not_silently_interpreted(self):
        for row in [
            {"gene_id": "a", "p_value": 0.1, "testable": 1},
            {"gene_id": "a", "p_value": None, "testable": True},
            {"gene_id": "a", "p_value": 0.1},
        ]:
            self.source.write_text(json.dumps([row]))
            with self.assertRaises(ValueError):
                adjust_p_values_file(str(self.source), eligibility_field="testable")

    def test_full_14599_row_family_does_not_hit_vector_10000_limit(self):
        self.source.write_text(
            json.dumps([{"gene_id": f"g{i}", "p_value": 0.01} for i in range(14599)])
        )
        result = adjust_p_values_file(str(self.source))
        self.assertEqual(result["family_size"], 14599)
        read = read_scientific_records(result["results_file"], ["g14598"], "gene_id")
        self.assertEqual(read["records"][0]["adjusted_p_value"], 0.01)

    def test_no_shared_default_or_relative_root(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SCITOOLFLOW_ARTIFACTS_DIR", None)
            with self.assertRaises(ValueError):
                adjust_p_values_file(str(self.source))
        with patch.dict(
            os.environ, {"SCITOOLFLOW_ARTIFACTS_DIR": "relative/artifacts"}
        ):
            with self.assertRaises(ValueError):
                _public_source_path(str(self.source))

    def test_nonexistent_artifact_root_is_clear_configuration_error(self):
        nonexistent = self.root / "not_created/task_artifacts"
        with patch.dict(os.environ, {"SCITOOLFLOW_ARTIFACTS_DIR": str(nonexistent)}):
            with self.assertRaisesRegex(ValueError, "existing task-local"):
                _public_source_path(str(self.source))
        self.assertFalse(nonexistent.exists())

    def test_broad_filesystem_root_cannot_expand_read_scope(self):
        for root in ["/", "/tmp", str(Path.home())]:
            with (
                self.subTest(root=root),
                patch.dict(os.environ, {"SCITOOLFLOW_ARTIFACTS_DIR": root}),
            ):
                with self.assertRaisesRegex(ValueError, "shared or broad"):
                    _public_source_path(str(self.source))

    def test_cross_task_and_symlink_escape_rejected(self):
        other = self.root / "task_b/artifacts"
        other.mkdir(parents=True)
        secret = other / "result.json"
        secret.write_text('[{"gene_id":"other","p_value":0.1}]')
        for name in [str(secret), "../" * 2 + "task_b/artifacts/result.json"]:
            with self.subTest(name=name), self.assertRaises(PermissionError):
                _public_source_path(name)
        link = self.artifacts / "escape.json"
        link.symlink_to(secret)
        with self.assertRaises(PermissionError):
            _public_source_path(str(link))

    def test_relative_task_artifact_is_readable(self):
        path = self.artifacts / "nested/results.json"
        path.parent.mkdir()
        path.write_text('[{"gene_id":"a","p_value":0.1}]')
        result = read_scientific_records("nested/results.json", id_field="gene_id")
        self.assertEqual(result["records"][0]["gene_id"], "a")


if __name__ == "__main__":
    unittest.main()
