"""Empty submissions retain the complete selected dataset in the score denominator."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evaluation.runner import evaluate_package
from tasks.datasets import dataset_files

ROOT = Path(__file__).resolve().parents[2]


class DatasetDenominatorTests(unittest.TestCase):
    def test_full_and_mini_missing_predictions_have_500_and_200_denominators(self):
        with tempfile.TemporaryDirectory() as directory:
            for dataset, count in [("full", 500), ("mini", 200)]:
                settings = {
                    "dataset": dataset,
                    "resource_policy": {
                        "version": "task-resources.v1",
                        "max_model_requests": 400,
                        "task_seconds": 7200,
                    },
                    "actor_file_hashes": {
                        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                        for name in dataset_files(dataset)
                        + ["tools/catalog/catalog.json"]
                    },
                }
                predictions = Path(directory) / (dataset + ".json")
                predictions.write_text(
                    json.dumps(
                        {
                            "settings": settings,
                            "fingerprint": hashlib.sha256(
                                json.dumps(settings, sort_keys=True).encode()
                            ).hexdigest(),
                            "predictions": [],
                        }
                    )
                )
                with (
                    self.subTest(dataset=dataset),
                    patch("evaluation.runner.validate_package"),
                ):
                    result = evaluate_package(
                        ROOT,
                        predictions,
                        Path(directory) / (dataset + "_scores.json"),
                        dataset=dataset,
                    )
                self.assertEqual(result["summary"]["dataset"], dataset)
                self.assertEqual(result["summary"]["total_reference_tasks"], count)
                self.assertEqual(result["summary"]["missing_predictions"], count)
                self.assertEqual(result["summary"]["joint_pass_rate"], 0)
                if dataset == "mini":
                    self.assertEqual(
                        [r["id"] for r in result["results"]],
                        [f"FLOW-{i:04d}" for i in range(1, 201)],
                    )
                    self.assertTrue(
                        any(r["id"] != r["source_id"] for r in result["results"])
                    )


if __name__ == "__main__":
    unittest.main()
