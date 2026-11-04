"""Dataset namespaces bind renumbered tasks, CLI selection and resume identity."""

from contextlib import redirect_stdout
from io import StringIO
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import cli
from baselines.react.runner import actor_file_hashes, resume_rows
from tasks.datasets import load_dataset

ROOT = Path(__file__).resolve().parents[2]


class DatasetInterfaceTests(unittest.TestCase):
    def test_mini_is_contiguous_and_mapping_preserves_every_scientific_field(self):
        full, mini = load_dataset("full", ROOT), load_dataset("mini", ROOT)
        originals = {row["id"]: row for row in full.questions}
        self.assertEqual(len(full.questions), 500)
        self.assertEqual(len(mini.questions), 200)
        self.assertEqual(
            [r["id"] for r in mini.questions], [f"FLOW-{i:04d}" for i in range(1, 201)]
        )
        self.assertEqual(len(set(mini.source_ids.values())), 200)
        for task in mini.questions:
            source = mini.source_id(task["id"])
            self.assertEqual({**task, "id": source}, originals[source])
        self.assertTrue(any(tid != source for tid, source in mini.source_ids.items()))
        self.assertEqual(mini.select("FLOW-0003")[0], mini.questions[2])
        with self.assertRaises(ValueError):
            mini.select("FLOW-0481")
        with self.assertRaises(ValueError):
            mini.select("FLOW-0001,FLOW-0001")
        with self.assertRaises(ValueError):
            load_dataset("unknown", ROOT)

    def test_task_command_disambiguates_overlapping_ids(self):
        outputs = {}
        for dataset in ("full", "mini"):
            stream = StringIO()
            with (
                patch.object(
                    sys, "argv", ["cli.py", "task", "FLOW-0004", "--dataset", dataset]
                ),
                redirect_stdout(stream),
            ):
                cli.main()
            outputs[dataset] = json.loads(stream.getvalue())
        self.assertEqual(outputs["full"]["id"], outputs["mini"]["id"])
        self.assertNotEqual(outputs["full"]["question"], outputs["mini"]["question"])

    def test_run_and_score_use_the_same_dataset_switch(self):
        with tempfile.TemporaryDirectory() as directory:
            for dataset in ("full", "mini"):
                with (
                    self.subTest(dataset=dataset),
                    patch.object(
                        sys,
                        "argv",
                        ["cli.py", "run", "--dataset", dataset, "--backend", "api"],
                    ),
                    patch("baselines.react.runner.run_batch") as runner,
                ):
                    cli.main()
                    self.assertEqual(runner.call_args.args[0].dataset, dataset)
                    self.assertEqual(runner.call_args.args[0].tasks, "all")
                with (
                    patch.object(
                        sys,
                        "argv",
                        [
                            "cli.py",
                            "score",
                            "--dataset",
                            dataset,
                            "--predictions",
                            directory + "/predictions.json",
                            "--output",
                            directory + "/scores.json",
                        ],
                    ),
                    patch(
                        "evaluation.runner.evaluate_package",
                        return_value={"summary": {}},
                    ) as scorer,
                    redirect_stdout(StringIO()),
                ):
                    cli.main()
                    self.assertEqual(scorer.call_args.kwargs["dataset"], dataset)
                    self.assertIsNone(scorer.call_args.kwargs["task_ids"])

    def test_runtime_reads_public_data_without_selection_notes_or_gold(self):
        original = Path.read_text

        def guarded(path, *args, **kwargs):
            if "evaluation" in path.parts or path.name == "selection.json":
                raise AssertionError("Actor loaded author-only metadata")
            return original(path, *args, **kwargs)

        with patch.object(Path, "read_text", guarded):
            self.assertEqual(len(load_dataset("mini", ROOT).questions), 200)

    def test_mapping_or_question_tampering_is_rejected_even_after_local_rehash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tasks/mini").mkdir(parents=True)
            (root / "tasks/questions.jsonl").write_bytes(
                (ROOT / "tasks/questions.jsonl").read_bytes()
            )
            for name in ("questions.jsonl", "ids.tsv", "metadata.json"):
                (root / "tasks/mini" / name).write_bytes(
                    (ROOT / "tasks/mini" / name).read_bytes()
                )
            path = root / "tasks/mini/ids.tsv"
            source = path.read_text()
            lines = source.splitlines()
            lines[2] = lines[2].split("\t")[0] + "\t" + lines[1].split("\t")[1]
            path.write_text("\n".join(lines) + "\n")
            metadata_path = root / "tasks/mini/metadata.json"
            metadata = json.loads(metadata_path.read_text())
            metadata["sha256"]["ids.tsv"] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            metadata_path.write_text(json.dumps(metadata))
            with self.assertRaisesRegex(ValueError, "bijective"):
                load_dataset("mini", root)
            path.write_text(source)
            metadata["sha256"]["ids.tsv"] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            questions_path = root / "tasks/mini/questions.jsonl"
            rows = [
                json.loads(line) for line in questions_path.read_text().splitlines()
            ]
            rows[2]["question"] = "tampered task"
            questions_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            metadata["sha256"]["questions.jsonl"] = hashlib.sha256(
                questions_path.read_bytes()
            ).hexdigest()
            metadata_path.write_text(json.dumps(metadata))
            with self.assertRaisesRegex(ValueError, "beyond ID"):
                load_dataset("mini", root)

    def test_mini_mapping_participates_in_checkpoint_identity(self):
        full = actor_file_hashes(ROOT, "full")
        mini = actor_file_hashes(ROOT, "mini")
        for name in (
            "tasks/mini/questions.jsonl",
            "tasks/mini/ids.tsv",
            "tasks/mini/metadata.json",
        ):
            self.assertIn(name, mini)
            self.assertNotIn(name, full)
        self.assertFalse(any(name.startswith("evaluation/") for name in mini))
        key = lambda dataset, hashes: hashlib.sha256(
            json.dumps(
                {"dataset": dataset, "actor_file_hashes": hashes}, sort_keys=True
            ).encode()
        ).hexdigest()
        with self.assertRaises(ValueError):
            resume_rows(
                {"fingerprint": key("full", full), "predictions": []}, key("mini", mini)
            )


if __name__ == "__main__":
    unittest.main()
