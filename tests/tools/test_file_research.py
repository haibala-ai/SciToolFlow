"""Whole-population file analysis and explicit membership-family regressions."""

import json
import hashlib
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.implementations.general.file_records import query_scientific_records_file
from tools.implementations.machine_learning.file_enrichment import (
    hypergeometric_enrichment_file,
)
from tools.implementations.machine_learning.file_statistics import adjust_p_values_file
from tools.runtime.config import UPLOAD_CONTEXT


class FileResearchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.artifacts = self.root / "task/artifacts"
        self.artifacts.mkdir(parents=True)
        self.paths = []
        context_token = UPLOAD_CONTEXT.set({"all_paths": self.paths})
        self.addCleanup(UPLOAD_CONTEXT.reset, context_token)
        environment = patch.dict(
            os.environ, {"SCITOOLFLOW_ARTIFACTS_DIR": str(self.artifacts)}
        )
        environment.start()
        self.addCleanup(environment.stop)

    def source(self, name, document):
        path = self.root / name
        path.write_text(json.dumps(document, allow_nan=False))
        self.paths.append(str(path))
        return str(path)

    @staticmethod
    def records(result):
        return json.loads(Path(result["results_file"]).read_text())["data"]

    def test_full_background_survives_projection_and_enrichment(self):
        # This is a mathematical population fixture, not experimental data.
        source = self.source(
            "population.json",
            {
                "data": [
                    {"gene_id": f"g{i}", "eligible": i < 12357} for i in range(14599)
                ]
            },
        )
        background = query_scientific_records_file(
            source,
            "gene_id",
            predicates=[{"field": "eligible", "op": "eq", "value": True}],
            fields=[],
            preview_limit=1,
        )
        selected = self.source("selected.json", [{"gene_id": "g1"}, {"gene_id": "g2"}])
        memberships = self.source(
            "membership.json",
            {
                "term_ids": ["present", "empty"],
                "data": [{"gene_id": "g1", "term_id": "present"}],
            },
        )
        output = hypergeometric_enrichment_file(
            background["results_file"], selected, memberships
        )
        self.assertEqual(background["matching_record_count"], 12357)
        self.assertEqual(len(self.records(background)), 12357)
        self.assertEqual(output["universe_size"], 12357)
        self.assertEqual(output["family_size"], 2)
        by_id = {row["term_id"]: row for row in self.records(output)}
        self.assertAlmostEqual(by_id["present"]["p_value"], 2 / 12357)
        self.assertEqual(
            (by_id["empty"]["K"], by_id["empty"]["k"], by_id["empty"]["p_value"]),
            (0, 0, 1),
        )

    def test_membership_projection_preserves_declared_zero_member_terms_and_deduplicates(
        self,
    ):
        universe = self.source(
            "universe.json", [{"gene_id": f"g{i}"} for i in range(8)]
        )
        selected = self.source(
            "selection.json", [{"gene_id": f"g{i}"} for i in range(3)]
        )
        memberships = self.source(
            "annotations.json",
            {
                "term_ids": ["A", "B", "empty"],
                "data": [
                    {
                        "id": str(i),
                        "term_id": term,
                        "gene_id": gene,
                        "qualifier": qualifier,
                    }
                    for i, (term, gene, qualifier) in enumerate(
                        [
                            ("A", "g0", "positive"),
                            ("A", "g0", "positive"),
                            ("A", "g1", "positive"),
                            ("A", "g3", "positive"),
                            ("A", "outside", "positive"),
                            ("B", "g2", "NOT"),
                        ]
                    )
                ],
            },
        )
        filtered = query_scientific_records_file(
            memberships,
            "id",
            predicates=[{"field": "qualifier", "op": "eq", "value": "positive"}],
            fields=["term_id", "gene_id"],
        )
        self.assertEqual(
            json.loads(Path(filtered["results_file"]).read_text())["term_ids"],
            ["A", "B", "empty"],
        )
        result = hypergeometric_enrichment_file(
            universe, selected, filtered["results_file"]
        )
        self.assertEqual(result["duplicate_membership_pairs_ignored"], 1)
        self.assertEqual(result["outside_universe_distinct_member_count"], 1)
        by_id = {r["term_id"]: r for r in self.records(result)}
        exact_tail = (math.comb(3, 2) * math.comb(5, 1) + math.comb(3, 3)) / math.comb(
            8, 3
        )
        self.assertAlmostEqual(by_id["A"]["p_value"], exact_tail)
        self.assertEqual([by_id[t]["p_value"] for t in ["B", "empty"]], [1, 1])
        adjusted = adjust_p_values_file(result["results_file"], id_field="term_id")
        self.assertEqual(adjusted["family_size"], 3)
        self.assertEqual(
            [r["term_id"] for r in self.records(adjusted)], ["A", "B", "empty"]
        )
        with self.assertRaises(ValueError):
            hypergeometric_enrichment_file(
                universe,
                selected,
                filtered["results_file"],
                unknown_member_policy="error",
            )

    def test_boolean_and_numeric_equality_are_distinct(self):
        source = self.source(
            "typed.json",
            [
                {"id": "bool", "x": True},
                {"id": "int", "x": 1},
                {"id": "float", "x": 1.0},
            ],
        )
        for value, expected in [(True, ["bool"]), (1, ["int", "float"])]:
            output = query_scientific_records_file(
                source, "id", predicates=[{"field": "x", "op": "eq", "value": value}]
            )
            self.assertEqual([r["id"] for r in self.records(output)], expected)

    def test_explicit_nulls_stable_ties_and_limit_count(self):
        source = self.source(
            "sort.json",
            [
                {"id": "a", "x": 2},
                {"id": "b", "x": None},
                {"id": "c", "x": 2},
                {"id": "d", "x": 1},
            ],
        )
        result = query_scientific_records_file(
            source,
            "id",
            fields=["x"],
            order_by=[{"field": "x", "direction": "descending", "nulls": "first"}],
            limit=3,
        )
        self.assertEqual([r["id"] for r in self.records(result)], ["b", "a", "c"])
        self.assertEqual(
            (result["matching_record_count"], result["output_record_count"]), (4, 3)
        )
        nulls = query_scientific_records_file(
            source, "id", predicates=[{"field": "x", "op": "is_null"}]
        )
        self.assertEqual([r["id"] for r in self.records(nulls)], ["b"])
        empty = query_scientific_records_file(source, "id", limit=0)
        self.assertEqual((empty["matching_record_count"], self.records(empty)), (4, []))

    def test_missing_field_is_not_null_and_earlier_predicate_cannot_hide_it(self):
        source = self.source(
            "missing.json",
            [{"id": "a", "keep": False}, {"id": "b", "keep": True, "x": 1}],
        )
        with self.assertRaises(ValueError):
            query_scientific_records_file(
                source,
                "id",
                predicates=[
                    {"field": "keep", "op": "eq", "value": True},
                    {"field": "x", "op": "is_null"},
                ],
            )
        with self.assertRaises(ValueError):
            query_scientific_records_file(source, "id", fields=["x"])
        missing = query_scientific_records_file(
            source, "id", predicates=[{"field": "x", "op": "missing"}]
        )
        self.assertEqual([r["id"] for r in self.records(missing)], ["a"])

    def test_complete_identity_digest_ignores_projection_and_order_not_selected_set(
        self,
    ):
        source = self.source(
            "ids.json", [{"id": "é", "v": 2}, {"id": "b", "v": 1}, {"id": "a", "v": 1}]
        )
        full = query_scientific_records_file(source, "id", preview_limit=0)
        projection = query_scientific_records_file(
            source, "id", fields=[], order_by=[{"field": "v"}]
        )
        limited = query_scientific_records_file(source, "id", limit=2)
        expected = hashlib.sha256(
            json.dumps(
                ["a", "b", "é"], ensure_ascii=False, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()
        self.assertEqual(full["output_identity_set_sha256"], expected)
        self.assertEqual(projection["output_identity_set_sha256"], expected)
        self.assertNotEqual(limited["output_identity_set_sha256"], expected)

    def test_identity_unknown_and_permission_failures_are_explicit(self):
        universe = self.source("u.json", [{"gene_id": "x"}])
        selected = self.source("s.json", [{"gene_id": "outside"}])
        membership = self.source("m.json", {"term_ids": ["T"], "data": []})
        duplicates = self.source("d.json", [{"gene_id": "x"}, {"gene_id": "x"}])
        with self.assertRaises(ValueError):
            query_scientific_records_file(duplicates, "gene_id")
        with self.assertRaises(ValueError):
            hypergeometric_enrichment_file(universe, selected, membership)
        private = self.root / "not_uploaded.json"
        private.write_text('[{"gene_id":"x"}]')
        with self.assertRaises(PermissionError):
            query_scientific_records_file(str(private), "gene_id")


if __name__ == "__main__":
    unittest.main()
