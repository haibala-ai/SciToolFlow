"""Regression tests for independent scoring, public contracts and resumable execution."""

import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

P = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(P))
from evaluation.answer import scalar_compare, score_answer
from evaluation.planning import arguments_match
from evaluation.scoring import evaluate_v2
from scitoolflow.benchmark.schema import answer_schema, validation_errors
from evaluation.reviews import review_callback
from scitoolflow.models.client import GenerationClient
from baselines.react.context import Context
from tools.catalog import ToolCatalog
from baselines.react import runner as batch


def reference(value):
    return {
        "id": "CONTROL",
        "question": "Report the returned value.",
        "tool_path": ["Example"],
        "necessary_observation_ids": ["o001"],
        "expected_answer": {"results": {"value": value}},
        "_resolved_events": {
            "o001": {"tool": "Example", "arguments": {"x": 1}, "status": "success"}
        },
        "scoring": {"field_rules": [{"field": "results.value", "atol": 0, "rtol": 0}]},
    }


REGISTRY = {
    "tools": {"Example": {"parameters": [{"name": "x", "required": True}]}},
    "aliases": {},
}


class ScoringTests(unittest.TestCase):
    def test_identifiers_case_and_units(self):
        for a, b in [("mp-149", "wrong-149"), ("CO", "Co"), ("0.5 eV", "0.5 J")]:
            self.assertNotEqual(scalar_compare(a, b, 0, 0), "match")

    def test_numeric_text_must_be_single_literal(self):
        self.assertNotEqual(
            scalar_compare(42, "Not 42; the answer is 0.", 0, 0), "match"
        )
        self.assertEqual(scalar_compare(42, "42", 0, 0), "match")

    def test_zero_and_additive_tolerance(self):
        r = reference(1.0)
        self.assertEqual(
            score_answer(r, {"results": {"value": 1.0000005}})["status"], "failed"
        )
        r["scoring"]["field_rules"][0].update(atol=1e-6, rtol=1e-6)
        self.assertEqual(
            score_answer(r, {"results": {"value": 1.0000015}})["status"], "passed"
        )

    def test_full_array_tail(self):
        values = list(range(100))
        r = reference(values)
        wrong = values.copy()
        wrong[-1] = -1
        self.assertEqual(
            score_answer(r, {"results": {"value": wrong}})["status"], "failed"
        )

    def test_invalid_rule_is_not_silently_dropped(self):
        r = reference(1)
        r["scoring"]["field_rules"][0]["field"] = "missing.path"
        with self.assertRaises(ValueError):
            score_answer(r, {"results": {"value": 1}})

    def test_optional_parameter_values(self):
        self.assertTrue(
            arguments_match(
                "Example", {"x": 1}, {"x": 1, "mode": "sum"}, {"mode": "sum"}
            )
        )
        self.assertFalse(
            arguments_match(
                "Example", {"x": 1}, {"x": 1, "mode": "negate"}, {"mode": "sum"}
            )
        )
        self.assertFalse(
            arguments_match("Example", {"x": 1}, {"x": 1, "mode": "sum"}, {"mode"})
        )

    def evaluate(self, r, calls=None, answer=None, **options):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        output = Path(self.temp.name) / "score.json"
        pred = {
            "id": r["id"],
            "completed": True,
            "calls": calls
            or [{"tool": "Example", "arguments": {"x": 1}, "status": "success"}],
            "final_answer": answer if answer is not None else r["expected_answer"],
        }
        result = evaluate_v2(
            [r], [pred], output, registry=REGISTRY, trace_root=P, **options
        )
        return result, output, pred

    def test_actual_budget(self):
        calls = [{"tool": "Example", "arguments": {"x": 1}, "status": "success"}] * 33
        result, _, _ = self.evaluate(reference(1), calls)
        self.assertFalse(result["results"][0]["joint_pass"])
        self.assertTrue(result["results"][0]["budget_exceeded"])

    def test_event_label_cannot_hide_budget(self):
        calls = [
            {
                "tool": "Example",
                "arguments": {"x": 1},
                "status": "success",
                "event": "other",
            }
        ] * 33
        result, _, _ = self.evaluate(reference(1), calls)
        self.assertTrue(result["results"][0]["budget_exceeded"])

    def test_contract_failure_with_no_rules(self):
        r = reference(1)
        r["answer_contract"] = answer_schema(r["expected_answer"])
        r["scoring"]["field_rules"] = []
        self.assertEqual(score_answer(r, {})["status"], "failed")

    def test_normalizer_callback(self):
        seen = []

        def normalizer(v):
            seen.append(True)
            return v

        self.evaluate(reference(1), normalize_value=normalizer)
        self.assertGreater(len(seen), 0)

    def test_required_outputs(self):
        refs = [
            json.loads(s)
            for s in (P / "evaluation/references.jsonl").read_text().splitlines()
        ]
        r = next(r for r in refs if r["id"] == "FLOW-0372")
        self.assertEqual(
            score_answer(
                r, {"derived_comparisons": [{"identical": True}, {"identical": True}]}
            )["status"],
            "failed",
        )
        self.assertEqual(score_answer(r, r["expected_answer"])["status"], "passed")

    def test_review_is_hash_bound(self):
        r = reference("The reference explanation.")
        result, path, pred = self.evaluate(
            r, answer={"results": {"value": "An equivalent explanation."}}
        )
        self.assertTrue(result["results"][0]["answer_pending"])
        requests = json.loads(path.with_name("score_review_requests.json").read_text())[
            "tasks"
        ]
        review = {
            k: requests[0][k] for k in ["id", "reference_sha256", "prediction_sha256"]
        }
        review.update(
            answer_pass=True,
            reviewer="independent-test",
            rationale="Synthetic review protocol control.",
            reviewed_at="2026-10-16",
        )
        review_path = path.with_name("review.json")
        review_path.write_text(json.dumps([review]))
        scored = evaluate_v2(
            [r],
            [pred],
            path,
            registry=REGISTRY,
            trace_root=P,
            semantic=review_callback(review_path),
        )
        self.assertTrue(scored["results"][0]["answer_pass"])
        review["prediction_sha256"] = "wrong"
        review_path.write_text(json.dumps([review]))
        with self.assertRaises(ValueError):
            evaluate_v2(
                [r],
                [pred],
                path,
                registry=REGISTRY,
                trace_root=P,
                semantic=review_callback(review_path),
            )

    def test_quarantined_reference_is_explicit(self):
        r = reference(1)
        r.update(
            evaluation_status="quarantined", reference_issue="Missing original evidence"
        )
        result, _, _ = self.evaluate(r)
        self.assertEqual(result["summary"]["quarantined_reference_tasks"], 1)
        self.assertEqual(result["summary"]["eligible_reference_tasks"], 0)
        self.assertIsNone(result["summary"]["joint_pass_rate"])


class ContractAndRuntimeTests(unittest.TestCase):
    def test_schema_has_no_array_cardinality_or_values(self):
        schema = answer_schema(
            {"values": [4, 5, 6], "entities": {"mp-149": {"gap": 1.3}}}
        )
        serialized = json.dumps(schema)
        self.assertNotIn("mp-149", serialized)
        self.assertNotIn("minItems", serialized)
        self.assertNotIn("maxItems", serialized)
        self.assertTrue(validation_errors({}, schema))
        self.assertFalse(
            validation_errors(
                {"values": [9], "entities": {"mp-10": {"gap": 2}}}, schema
            )
        )

    def test_all_public_contracts_are_executable_and_reject_empty(self):
        rows = [
            json.loads(s)
            for s in (P / "tasks/questions.jsonl").read_text().splitlines()
        ]
        self.assertEqual(len(rows), 500)
        self.assertTrue(
            all(row["answer_schema"].get("type") == "object" for row in rows)
        )
        self.assertTrue(
            all(validation_errors({}, row["answer_schema"]) for row in rows)
        )

    def test_unit_annotations_resolve(self):
        from evaluation.answer import resolve_candidates

        refs = {
            r["id"]: r
            for r in map(
                json.loads, (P / "evaluation/references.jsonl").read_text().splitlines()
            )
        }
        schemas = [
            json.loads(s)
            for s in (P / "tasks/questions.jsonl").read_text().splitlines()
        ]
        for row in schemas:
            for item in row.get("unit_annotations", []):
                self.assertTrue(
                    resolve_candidates(
                        refs[row["id"]]["expected_answer"], [item["path"]]
                    )[0]
                )

    def test_tools_do_not_load_reference_examples(self):
        self.assertEqual(len(ToolCatalog().tools), 547)
        original = Path.read_text

        def guarded(path, *a, **kw):
            if "reference_traces" in path.parts or path.name == "references.jsonl":
                raise AssertionError("Actor read private reference traces")
            return original(path, *a, **kw)

        with patch.object(Path, "read_text", guarded):
            self.assertEqual(len(ToolCatalog().tools), 547)

    def test_vllm_authorization_is_not_sampling_key(self):
        class Response:
            status_code = 200

            def json(self):
                return {
                    "choices": [
                        {
                            "message": {"content": '{"finish":{}}'},
                            "finish_reason": "stop",
                        }
                    ]
                }

        class Session:
            def post(self, *a, **kw):
                self.headers = kw["headers"]
                return Response()

        session = Session()
        with patch.dict(os.environ, {"SCITOOLFLOW_VLLM_KEY": "TEST_PLACEHOLDER"}):
            client = GenerationClient("vllm", session=session)
            with client.react_request_scope():
                client.request([{"role": "user", "content": "probe"}], max_tokens=16)
        self.assertEqual(session.headers["Authorization"], "Bearer TEST_PLACEHOLDER")

    def test_sampling_validation(self):
        with patch.dict(os.environ, {"SCITOOLFLOW_VLLM_TOP_P": "nan"}):
            client = GenerationClient("vllm", session=object())
            with client.react_request_scope(), self.assertRaises(ValueError):
                client.request([], max_tokens=10)

    def test_checkpoint_resume(self):
        previous = {
            "fingerprint": "same",
            "predictions": [{"id": "A"}],
            "progress": [{"id": "A", "status": "completed"}],
        }
        predictions = batch.resume_rows(previous, "same")
        rows = predictions
        self.assertEqual([r["id"] for r in rows], ["A"])
        self.assertEqual(len(predictions), 1)
        with self.assertRaises(ValueError):
            batch.resume_rows(previous, "changed")
        with self.assertRaises(ValueError):
            batch.resume_rows({"predictions": [{"id": "A"}]}, "same")

    def test_exact_token_budget_in_context(self):
        with self.assertRaises(ValueError):
            Context([{"content": "too much"}], 1000, lambda m: 20, 10)
        context = Context([{"content": "initial"}], 1000, lambda m: len(m) * 10, 25)
        context.append("user", "one")
        context.append("user", "two")
        self.assertLessEqual(len(context.build([])), 2)


if __name__ == "__main__":
    unittest.main()
