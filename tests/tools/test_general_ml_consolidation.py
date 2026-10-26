"""Scientific and transport boundaries for the consolidated General/ML APIs."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np

from tools.implementations.general.data_tools import join_record_tables, filter_records
from tools.implementations.general.record_inspection import (
    extract_numeric_columns,
    inspect_scientific_file,
)
from tools.implementations.machine_learning.family_statistics import (
    adjust_p_values,
    hypergeometric_enrichment,
)
from tools.implementations.machine_learning.matched_coordinate_distances import (
    rigid_superposition,
)
from tools.implementations.general.file_records import query_scientific_records_file
from tools.runtime.config import UPLOAD_CONTEXT
from tools.implementations.machine_learning.classification import (
    train_and_predict_classifier,
)
from tools.implementations.general.data_tools import (
    parse_csv_records,
    parse_json_document,
)
from tools.implementations.general.data_tools import format_markdown_table


class ConsolidatedGeneralMLTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.artifacts = self.root / "task/artifacts"
        self.artifacts.mkdir(parents=True)
        self.source = self.root / "source.json"
        self.env = patch.dict(
            os.environ, {"SCITOOLFLOW_ARTIFACTS_DIR": str(self.artifacts)}
        )
        self.env.start()
        self.addCleanup(self.env.stop)
        self.token = UPLOAD_CONTEXT.set({"all_paths": [str(self.source)]})
        self.addCleanup(UPLOAD_CONTEXT.reset, self.token)

    def test_single_and_multiple_numeric_columns_share_explicit_shape(self):
        rows = [{"a": 2, "b": 3}, {"a": 5, "b": 7}]
        self.assertEqual(
            extract_numeric_columns(rows, ["b", "a"])["features"], [[3, 2], [7, 5]]
        )
        self.assertEqual(
            extract_numeric_columns(rows, ["a"], "vector")["values"], [2, 5]
        )
        with self.assertRaises(ValueError):
            extract_numeric_columns(rows, ["a", "b"], "vector")
        for bad in [True, None, "2"]:
            with self.subTest(value=bad), self.assertRaises(ValueError):
                extract_numeric_columns([{"a": bad}], ["a"])

    def test_join_boolean_number_identity_and_stable_traversal(self):
        left = [{"k": True, "x": "boolean"}, {"k": 1, "x": "number"}]
        right = [{"k": 1.0, "y": "numeric"}, {"k": True, "y": "logical"}]
        got = join_record_tables(left, right, ["k"])["records"]
        self.assertEqual(
            got,
            [
                {"k": True, "x": "boolean", "y": "logical"},
                {"k": 1, "x": "number", "y": "numeric"},
            ],
        )
        self.assertEqual(
            join_record_tables(left, right, ["k"], "right")["records"][0]["x"], "number"
        )
        with self.assertRaises(ValueError):
            join_record_tables([{"k": 1}, {"k": 1.0}], [{"k": 1}], ["k"])

    def test_join_preserves_sparse_source_missing_and_unmatched_null(self):
        got = join_record_tables(
            [{"k": "a", "x": 3}, {"k": "b"}], [{"k": "a", "y": 2}], ["k"], "left"
        )["records"]
        self.assertNotIn("x", got[1])
        self.assertIsNone(got[1]["y"])
        self.assertEqual(got[0], {"k": "a", "x": 3, "y": 2})

    def test_filter_uses_typed_json_equality(self):
        rows = [{"x": True}, {"x": 1}, {"x": 1.0}, {"x": "1"}]
        self.assertEqual(filter_records(rows, "x", "eq", 1)["matched_count"], 2)
        self.assertEqual(filter_records(rows, "x", "in", [True])["matched_count"], 1)
        with self.assertRaises(ValueError):
            filter_records([{"x": True}], "x", "lt", 2)

    def test_adjustment_file_and_inline_same_family(self):
        self.source.write_text(
            json.dumps(
                [
                    {"gene_id": "a", "p_value": 0.01},
                    {"gene_id": "b", "p_value": 0.04},
                    {"gene_id": "c", "p_value": 0.03},
                ]
            )
        )
        for method in ["bh", "by", "bonferroni"]:
            inline = adjust_p_values([0.01, 0.04, 0.03], method)
            artifact = adjust_p_values(method=method, results_file=str(self.source))
            rows = json.loads(Path(artifact["results_file"]).read_text())["data"]
            np.testing.assert_array_equal(
                [row["adjusted_p_value"] for row in rows], inline["adjusted_p_values"]
            )
        for kwargs in [
            {},
            {"p_values": [0.1], "results_file": str(self.source)},
            {"p_values": [0.1], "eligibility_field": "testable"},
        ]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                adjust_p_values(**kwargs)

    def test_enrichment_empty_selection_full_family_and_direct_probability(self):
        answer = hypergeometric_enrichment(
            ["a", "b", "c", "d"], ["a", "b"], {"t": ["a", "b"], "empty": []}
        )
        self.assertAlmostEqual(answer["results"][0]["p_value"], 1 / 6)
        self.assertEqual(answer["results"][1]["p_value"], 1.0)
        empty = hypergeometric_enrichment(["a"], [], {"none": []})
        self.assertEqual(empty["p_values"], [1.0])
        self.assertIsNone(empty["results"][0]["fold_enrichment"])
        with self.assertRaises(ValueError):
            hypergeometric_enrichment(
                ["a"], ["a"], {"t": ["outside"]}, unknown_member_policy="error"
            )

    def test_rigid_fit_transforms_residuals_and_batch_svd(self):
        x = np.array(
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 2.0, 0.0], [0.0, 0.0, 3.0]]
        )
        q = np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
        shapes = [x, x @ q + [2.0, 3.0, 5.0], x * 2]
        with patch("numpy.linalg.svd", wraps=np.linalg.svd) as svd:
            got = rigid_superposition(
                [v.tolist() for v in shapes], ["a", "b", "c"], True, True
            )
        self.assertEqual(svd.call_count, 2)
        first = got["pair_fits"][0]
        np.testing.assert_allclose(
            shapes[1] @ np.array(first["rotation"]) + first["translation"],
            x,
            atol=1e-12,
        )
        np.testing.assert_allclose(first["aligned_mobile_coordinates"], x, atol=1e-12)
        self.assertAlmostEqual(first["determinant"], 1.0)
        self.assertLess(first["rmsd"], 1e-12)
        self.assertGreater(got["rmsd_matrix"][0][2], 0.5)

    def test_file_inspector_has_no_records_and_query_keeps_typed_ids(self):
        self.source.write_text('[{"id":1,"x":null},{"id":"1","x":2}]')
        metadata = inspect_scientific_file(str(self.source))
        self.assertEqual(metadata["fields"]["x"]["null_count"], 1)
        self.assertNotIn("records", metadata)
        query = query_scientific_records_file(
            str(self.source), "id", [{"field": "id", "op": "eq", "value": 1}]
        )
        self.assertEqual(query["preview_records"], [{"id": 1, "x": None}])

    def test_classifiers_explicit_data_and_reproducibility(self):
        train = [[0.0, 0.0], [0.0, 0.1], [0.1, 0.0], [1.0, 1.0], [0.9, 1.0], [1.0, 0.9]]
        labels = ["a"] * 3 + ["b"] * 3
        for algorithm in ["random_forest", "adaboost", "mlp"]:
            a = train_and_predict_classifier(
                train, labels, [[0.0, 0.0], [1.0, 1.0]], algorithm, 5, 100
            )
            b = train_and_predict_classifier(
                train, labels, [[0.0, 0.0], [1.0, 1.0]], algorithm, 5, 100
            )
            self.assertEqual(a, b)
            self.assertEqual(a["predictions"], ["a", "b"])
            np.testing.assert_allclose(np.sum(a["probabilities"], axis=1), 1.0)
            self.assertNotIn("accuracy", a)
        with self.assertRaises(ValueError):
            train_and_predict_classifier(train, [True] * 6, [[1.0, 1.0]])

    def test_parser_explicit_file_transport_and_exclusivity(self):
        self.source.write_text('[{"id":"x"}]')
        self.assertEqual(
            parse_json_document(json_file=str(self.source))["document"], [{"id": "x"}]
        )
        self.source.write_text("a,b\n1,2\n")
        got = parse_csv_records(csv_file=str(self.source))
        self.assertEqual(got["records"], [{"a": "1", "b": "2"}])
        self.assertIn("source_sha256", got)
        for function, kwargs in [
            (parse_json_document, {"json_text": "{}", "json_file": str(self.source)}),
            (parse_csv_records, {"csv_text": "a\n1", "csv_file": str(self.source)}),
        ]:
            with self.assertRaises(ValueError):
                function(**kwargs)

    def test_sparse_markdown_output_is_bounded_before_dense_expansion(self):
        sparse = [{str(i): i} for i in range(201)]
        with self.assertRaises(ValueError):
            format_markdown_table(sparse)
        got = format_markdown_table([{"a": "x|y"}, {"a": None}], None)
        self.assertIn("x\\|y", got["markdown"])


if __name__ == "__main__":
    unittest.main()
