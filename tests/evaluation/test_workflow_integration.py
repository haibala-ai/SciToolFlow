"""Version dispatch, local evidence authentication and native-reference gates."""

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evaluation.runner import evaluate_package
from evaluation.integrity.traces import canonical_sha256, verify_release_envelope
from evaluation.integrity.reference import validate_workflow_reference, REVIEW_CHECKS
from tests.support.workflows import fixture, run


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


class WorkflowIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.reference, self.prediction = fixture(), run()
        self.reference.update(
            question="Select all best candidates from the known dataset.",
        )
        self.task = {k: self.reference[k] for k in ("id", "inputs", "question")}
        self.task["answer_schema"] = {"type": "object"}
        self.reference.update(
            answer_contract=self.task["answer_schema"],
            expected_answer=self.prediction["final_answer"],
        )
        self.prediction.update(
            id=self.task["id"], status="completed", failure_reason=None
        )
        self.catalog = {
            name: {
                "domain": "Math",
                "kind": "discovery" if name == "DescribeTools" else "scientific",
                "execution": {},
                "parameters": [],
                "description": name,
                "input_schema": {"type": "object"},
            }
            for name in [
                "ReadTable",
                "ReadJSON",
                "AuditUnits",
                "ScoreCandidates",
                "EvaluateCandidates",
                "InspectSchema",
                "Novel",
                "DescribeTools",
            ]
        }
        write(self.root / "tools/catalog/catalog.json", {"tools": self.catalog})
        self.save_reference()
        self.trace = {
            "schema_version": "scitoolflow.trajectory.v1",
            "backend": "native_subagent",
            "task_id": self.task["id"],
            "status": "completed",
            "failure_reason": None,
            "final_answer": copy.deepcopy(self.prediction["final_answer"]),
            "steps": [
                {"type": "tools", "calls": copy.deepcopy(self.prediction["calls"])}
            ],
        }
        self.resource_policy = {
            "version": "task-resources.v1",
            "max_model_requests": 400,
            "task_seconds": 7200,
        }
        self.trace["steps"][0]["model"] = {}
        self.trace["limits"] = {
            "resource_policy": "task-resources.v1",
            "model_requests": 400,
            "task_seconds": 7200,
        }
        self.trace["resource_usage"] = {
            "policy_version": "task-resources.v1",
            "max_model_requests": 400,
            "task_seconds": 7200,
            "model_requests": 1,
            "elapsed_seconds": 1,
            "requests": [
                {"request": 1, "phase": "react", "status": "returned", "usage": None}
            ],
        }
        self.save_trace()
        self.save_predictions()

    def save_reference(self):
        for name, record in [
            ("evaluation/data/references.jsonl", self.reference),
            ("tasks/full/questions.jsonl", self.task),
        ]:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(record) + "\n")
        write(
            self.root / "MANIFEST.json",
            {"references": "evaluation/data/references.jsonl"},
        )

    def save_trace(self):
        path = self.root / "results/run/trajectory.json"
        self.prediction.update(
            trace_path=str(path), trace_sha256=write(path, self.trace)
        )

    def save_predictions(self, dataset="full"):
        from tasks.datasets import dataset_files

        settings = {
            "dataset": dataset,
            "resource_policy": self.resource_policy,
            "actor_file_hashes": {
                name: hashlib.sha256((self.root / name).read_bytes()).hexdigest()
                for name in dataset_files(dataset) + ["tools/catalog/catalog.json"]
            },
        }
        self.envelope = {
            "settings": settings,
            "fingerprint": hashlib.sha256(
                json.dumps(settings, sort_keys=True).encode()
            ).hexdigest(),
            "predictions": [self.prediction],
        }
        write(self.root / "results/run/predictions.json", self.envelope)

    def evaluate(self, **kwargs):
        kwargs.setdefault("dataset", "full")
        with patch("evaluation.runner.validate_package"):
            return evaluate_package(
                self.root,
                self.root / "results/run/predictions.json",
                self.root / "scores.json",
                **kwargs,
            )

    def test_real_trace_without_exact_reference_path(self):
        self.prediction["calls"][0]["duration_seconds"] = 1234
        self.save_predictions()
        result = self.evaluate()
        self.assertEqual(result["summary"]["joint_pass_rate"], 1)
        self.assertTrue(result["results"][0]["evidence_integrity"]["verified"])
        self.assertEqual(
            json.loads((self.root / "scores_review_requests.json").read_text())[
                "tasks"
            ],
            [],
        )

    def test_supplied_fake_output_cannot_pass(self):
        self.prediction["calls"][0]["output"] = {"x": 99}
        self.save_predictions()
        result = self.evaluate()
        self.assertFalse(result["results"][0]["joint_pass"])
        self.assertEqual(result["summary"]["evidence_integrity_failures"], 1)

    def test_missing_trace_worker_exception_is_row_failure(self):
        self.prediction = {
            "id": self.task["id"],
            "completed": False,
            "status": "failed",
            "calls": [],
            "final_answer": None,
            "failure_reason": "worker failed",
        }
        self.save_predictions()
        result = self.evaluate()
        self.assertEqual(result["summary"]["joint_pass_rate"], 0)
        self.assertEqual(
            result["results"][0]["evidence_integrity"]["original_runtime_failure"],
            "worker failed",
        )

    def test_hash_and_identity_mutations_fail_closed(self):
        for field, value in [
            ("task_id", "other"),
            ("final_answer", {"selected": ["wrong"]}),
            ("status", "failed"),
        ]:
            with self.subTest(field=field):
                old = self.trace[field]
                self.trace[field] = value
                self.save_trace()
                self.save_predictions()
                self.assertFalse(self.evaluate()["results"][0]["joint_pass"])
                self.trace[field] = old
        self.save_trace()
        self.prediction["trace_sha256"] = "0" * 64
        self.save_predictions()
        self.assertFalse(self.evaluate()["results"][0]["joint_pass"])

    def test_duplicate_missing_ids_and_unregistered_tools_fail_closed(self):
        original = copy.deepcopy(self.trace["steps"][0]["calls"])
        for change in [
            lambda c: c.update(observation_id="o1"),
            lambda c: c.pop("observation_id"),
            lambda c: c.update(tool="Fake"),
        ]:
            with self.subTest(change=change):
                self.trace["steps"][0]["calls"] = copy.deepcopy(original)
                change(self.trace["steps"][0]["calls"][1])
                self.prediction["calls"] = copy.deepcopy(
                    self.trace["steps"][0]["calls"]
                )
                self.save_trace()
                self.save_predictions()
                self.assertFalse(self.evaluate()["results"][0]["joint_pass"])

    def test_source_release_and_settings_fingerprint_checked(self):
        self.envelope["fingerprint"] = "bad"
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            verify_release_envelope(self.envelope, self.root)
        self.save_predictions()
        (self.root / "tasks/full/questions.jsonl").write_text("changed")
        with self.assertRaisesRegex(ValueError, "source/release changed"):
            verify_release_envelope(self.envelope, self.root)
        with self.assertRaises(ValueError):
            verify_release_envelope([], self.root)

    def test_budget_exhaustion_cannot_joint_pass(self):
        self.resource_policy["scientific_calls"] = 1
        self.trace["limits"]["scientific_calls"] = 1
        self.save_trace()
        self.save_predictions()
        result = self.evaluate()
        self.assertTrue(result["results"][0]["resource_limit_exceeded"])
        self.assertFalse(result["results"][0]["joint_pass"])

    def test_unlisted_route_remains_independent_pending(self):
        self.trace["steps"][0]["calls"][2]["tool"] = "Novel"
        self.prediction["calls"] = copy.deepcopy(self.trace["steps"][0]["calls"])
        self.save_trace()
        self.save_predictions()
        result = self.evaluate()
        self.assertEqual(result["summary"]["pending_reviews"], 1)
        request = json.loads((self.root / "scores_review_requests.json").read_text())[
            "tasks"
        ][0]
        self.assertTrue(request["requires_independent_review"])
        self.assertFalse(result["results"][0]["joint_pass"])
        write(
            self.root / "reviews.json",
            {"reviews": [{"id": self.task["id"], "planning_pass": True}]},
        )
        with self.assertRaisesRegex(ValueError, "shared policy"):
            self.evaluate(reviews=self.root / "reviews.json")

    def test_mixed_and_unsupported_schemas_are_rejected(self):
        path = self.root / "evaluation/data/references.jsonl"
        path.write_text(
            json.dumps(self.reference) + "\n" + json.dumps({"id": "old"}) + "\n"
        )
        with self.assertRaisesRegex(ValueError, "Only workflow.v1"):
            self.evaluate()
        path.write_text(json.dumps({"id": self.task["id"]}) + "\n")
        with self.assertRaisesRegex(ValueError, "Only workflow.v1"):
            self.evaluate()

    def test_reference_requires_real_native_trace_and_second_review(self):
        registry = {"tools": self.catalog}
        self.reference["reference_trace"] = "results/run/trajectory.json"
        self.reference["native_provenance"] = {
            "actor_backend": "native_subagent",
            "model_api_used": False,
            "actor_id": "isolated-native-actor",
            "task_sha256": canonical_sha256(self.task),
            "trace_sha256": self.prediction["trace_sha256"],
            "task_identity": {
                k: canonical_sha256(self.task)
                for k in [
                    "current_public_task_sha256",
                    "generation_task_sha256",
                    "review_task_sha256",
                ]
            },
        }
        manifest = {
            "actor_backend": "native_subagent",
            "model_api_used": False,
            "task_id": self.task["id"],
            "public_task_sha256": canonical_sha256(self.task),
            "source_sha256": {},
            "input_asset_sha256": {},
        }
        self.reference["native_provenance"].update(
            generation_manifest=manifest,
            generation_manifest_sha256=canonical_sha256(manifest),
        )
        review = {
            "task_id": self.task["id"],
            "task_sha256": canonical_sha256(self.task),
            "trace_sha256": self.prediction["trace_sha256"],
            "status": "approved",
            "reviewer": "independent-root",
            "rationale": "Checked candidate population, genuine data dependency and ranking ties.",
            "checks": dict.fromkeys(REVIEW_CHECKS, True),
            "evaluation_sha256": canonical_sha256(self.reference["evaluation"]),
        }
        digest = canonical_sha256(review)
        self.reference["review"] = {
            "status": "approved",
            "reviewer": review["reviewer"],
            "reviewed_trace_sha256": review["trace_sha256"],
            "record": review,
            "record_sha256": digest,
        }
        self.assertEqual(
            validate_workflow_reference(
                self.root, self.task, self.reference, self.catalog, registry
            ),
            3,
        )
        self.reference["review"]["reviewer"] = "isolated-native-actor"
        with self.assertRaisesRegex(ValueError, "second review"):
            validate_workflow_reference(
                self.root, self.task, self.reference, self.catalog, registry
            )
        self.reference["review"]["reviewer"] = review["reviewer"]
        self.reference["evaluation"]["outcomes"][0]["weight"] = 2
        with self.assertRaisesRegex(ValueError, "second review"):
            validate_workflow_reference(
                self.root, self.task, self.reference, self.catalog, registry
            )
        self.reference["evaluation"]["outcomes"][0].pop("weight")
        self.reference["native_provenance"]["task_sha256"] = "wrong"
        with self.assertRaisesRegex(ValueError, "provenance"):
            validate_workflow_reference(
                self.root, self.task, self.reference, self.catalog, registry
            )


if __name__ == "__main__":
    unittest.main()
