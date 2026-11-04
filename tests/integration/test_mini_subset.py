"""Mini selection preserves scientific task identity and balanced eligibility."""

import copy
from collections import Counter
import json
from pathlib import Path
import unittest

from scripts.benchmark.mini import subset_files, validate_selection

ROOT = Path(__file__).resolve().parents[2]


class MiniSubsetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.questions = [
            json.loads(line)
            for line in (ROOT / "tasks/questions.jsonl").read_bytes().splitlines()
        ]
        cls.index = json.loads((ROOT / "tasks/index.json").read_bytes())
        cls.selection = json.loads((ROOT / "tasks/mini/selection.json").read_bytes())

    @staticmethod
    def reindex(selection):
        selection["tasks"].sort(key=lambda r: r["source_id"])
        for i, entry in enumerate(selection["tasks"], 1):
            entry["id"] = f"FLOW-{i:04d}"

    def test_delivered_subset_changes_only_ids_and_preserves_balanced_domains(self):
        selected, files = subset_files(ROOT)
        self.assertEqual(
            Counter(r["domain"] for r in selected),
            {"Chemical": 50, "Material": 50, "Biology": 50, "MachineLearning": 50},
        )
        for name, content in files.items():
            self.assertEqual((ROOT / "tasks/mini" / name).read_bytes(), content)
        by_id = {r["id"]: r for r in self.questions}
        mapping = {entry["id"]: entry["source_id"] for entry in self.selection["tasks"]}
        self.assertTrue(
            all(
                {**row, "id": mapping[row["id"]]} == by_id[mapping[row["id"]]]
                for row in selected
            )
        )
        self.assertEqual(
            [r["id"] for r in selected], [f"FLOW-{i:04d}" for i in range(1, 201)]
        )
        self.assertEqual(len(selected), 200)
        self.assertTrue(all("expected_answer" not in row for row in selected))

    def test_high_difficulty_is_rejected_even_if_annotation_claims_standard(self):
        selection = copy.deepcopy(self.selection)
        domain = selection["tasks"][0]["domain"]
        high = next(
            r
            for r in self.index["tasks"]
            if r["domain"] == domain and r["category"] == "high_difficulty"
        )
        selection["tasks"][0]["source_id"] = high["id"]
        selection["tasks"][0]["category"] = "standard"
        self.reindex(selection)
        with self.assertRaisesRegex(ValueError, "High-difficulty"):
            validate_selection(selection, self.questions, self.index)

    def test_duplicate_ids_cannot_fill_the_quota(self):
        selection = copy.deepcopy(self.selection)
        selection["tasks"][1] = copy.deepcopy(selection["tasks"][0])
        with self.assertRaisesRegex(ValueError, "200 unique"):
            validate_selection(selection, self.questions, self.index)

    def test_correct_total_with_wrong_discipline_distribution_is_rejected(self):
        selection = copy.deepcopy(self.selection)
        chosen = {r["source_id"] for r in selection["tasks"]}
        replacement = next(
            r
            for r in self.index["tasks"]
            if r["domain"] == "Material"
            and r["category"] != "high_difficulty"
            and r["id"] not in chosen
        )
        entry = selection["tasks"][0]
        self.assertEqual(entry["domain"], "Chemical")
        entry.update({key: replacement[key] for key in ("domain", "category")})
        entry["source_id"] = replacement["id"]
        self.reindex(selection)
        with self.assertRaisesRegex(ValueError, "50 tasks"):
            validate_selection(selection, self.questions, self.index)

    def test_repeated_labels_do_not_count_as_two_workstreams(self):
        selection = copy.deepcopy(self.selection)
        selection["tasks"][0]["parallel_subtasks"] = ["one branch", "one branch"]
        with self.assertRaisesRegex(ValueError, "distinct"):
            validate_selection(selection, self.questions, self.index)

    def test_duplicate_source_rows_are_not_silently_overwritten(self):
        with self.assertRaisesRegex(ValueError, "500 aligned"):
            validate_selection(
                self.selection, self.questions + self.questions[:1], self.index
            )


if __name__ == "__main__":
    unittest.main()
