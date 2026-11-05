"""Regressions for observed protocol barriers and independent scoring boundaries."""

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

P = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(P))
from baselines.common.answers import protocol_decision_schema
from baselines.react.runtime import run_react
from evaluation.runner import evaluate_package
from tools.catalog import ToolCatalog
from jsonschema import Draft202012Validator
from tests.support.clients import ScriptedClient
from tests.support.loop import SchemaClient, A, FINISH, SCHEMA, action


class ProtocolGuardTests(unittest.TestCase):
    def run_steps(self, client, invoke, **opts):
        with tempfile.TemporaryDirectory() as directory:
            return run_react(
                "Read JSON.",
                catalog=ToolCatalog(),
                client=client,
                invoke=invoke,
                trace_dir=directory,
                answer_schema=SCHEMA,
                **opts,
            )

    def test_guard_from_first_turn_uses_public_names_not_answer_fields(self):
        c = SchemaClient([FINISH])
        result = self.run_steps(c, lambda *a, **k: None)
        guard = c.options[0]["response_schema"]
        v = Draft202012Validator(guard)
        self.assertFalse(list(v.iter_errors(A)))
        self.assertTrue(
            list(
                v.iter_errors({"actions": [{"tool": "ImaginaryTool", "arguments": {}}]})
            )
        )
        self.assertFalse(list(v.iter_errors({"finish": {"different_public_shape": 3}})))
        self.assertEqual(result["stats"]["protocol_schema_guard_requests"], 1)
        self.assertEqual(result["stats"]["answer_schema_guard_requests"], 0)

    def test_exhausted_call_budget_leaves_other_operations(self):
        schema = protocol_decision_schema([], max_actions=0)
        v = Draft202012Validator(schema)
        self.assertTrue(list(v.iter_errors(A)))
        for op in [
            FINISH,
            {"think": "Check evidence."},
            {"inspect": {"observation_id": "o001"}},
            {"stop": {"reason": "No evidence"}},
        ]:
            self.assertFalse(list(v.iter_errors(op)))

    def test_visible_input_contracts_constrain_arguments_but_allow_real_citations(self):
        c = ToolCatalog()
        first = Draft202012Validator(protocol_decision_schema(["ParseJSONDocument"]))
        wrong = {"actions": [{"tool": "ParseJSONDocument", "arguments": {"wrong": 1}}]}
        self.assertFalse(list(first.iter_errors(wrong)))
        known = Draft202012Validator(
            protocol_decision_schema(
                ["ParseJSONDocument"],
                known_inputs={
                    "ParseJSONDocument": c.tools["ParseJSONDocument"]["input_schema"]
                },
                allow_think=False,
            )
        )
        self.assertTrue(list(known.iter_errors(wrong)))
        self.assertFalse(list(known.iter_errors(A)))
        citation = {
            "actions": [
                {
                    "tool": "ParseJSONDocument",
                    "arguments": {"json_text": {"$observation": "o001"}},
                }
            ]
        }
        self.assertFalse(list(known.iter_errors(citation)))
        self.assertTrue(list(known.iter_errors({"think": "No budget left"})))

    def test_nonconsecutive_failed_calls_are_not_cumulatively_rejected(self):
        calls = []

        def invoke(n, a, **k):
            calls.append(a)
            return {
                "status": "error",
                "error_type": "TemporaryFailure",
                "error": "Retryable",
                "output": None,
            }

        c = ScriptedClient([A, A, {"actions": [action(8)]}, A, FINISH])
        result = self.run_steps(c, invoke)
        self.assertEqual(len(calls), 4)
        self.assertEqual(result["stats"]["rejected_actions"], 0)
        self.assertEqual(result["stats"]["protocol_errors"], 0)
        self.assertEqual(result["stats"]["max_consecutive_identical_tool_steps"], 2)

    def test_ten_failed_identical_steps_use_the_same_consecutive_guard(self):
        calls = []

        def invoke(n, a, **k):
            calls.append(a)
            return {"status": "error", "error": "Unavailable", "output": None}

        result = self.run_steps(ScriptedClient([A] * 10 + [FINISH]), invoke)
        self.assertEqual(len(calls), 10)
        self.assertEqual(result["failure_reason"], "RepeatedToolLoop")
        self.assertEqual(result["stats"]["protocol_errors"], 0)

    def test_argument_feedback_supplies_schema_and_failure_diagnostics_survive(self):
        c = ScriptedClient(
            [
                {
                    "actions": [
                        {"tool": "ParseJSONDocument", "arguments": {"wrong": "x"}}
                    ]
                },
                A,
                FINISH,
            ]
        )
        result = self.run_steps(
            c,
            lambda *a, **k: {
                "status": "error",
                "error": "Unavailable",
                "output": None,
                "worker_stderr": "HTTP 503: service unavailable",
            },
        )
        rejected = result["steps"][0]["action_errors"][0]
        self.assertIn("json_text", rejected["expected_input_schema"]["properties"])
        self.assertIn(
            "HTTP 503", result["calls"][0]["dispatcher_diagnostics"]["worker_stderr"]
        )


class ScoringBoundaryTests(unittest.TestCase):

    def test_old_predictions_cannot_be_scored_against_revised_public_tasks(self):
        from evaluation.integrity.traces import verify_release_envelope
        import hashlib

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "tasks/full").mkdir(parents=True)
            (root / "tasks/full/questions.jsonl").write_text("new-public-task\n")
            settings = {
                "actor_file_hashes": {
                    "tasks/full/questions.jsonl": "old-hash",
                    "tools/catalog/catalog.json": "catalog-hash",
                }
            }
            envelope = {
                "settings": settings,
                "fingerprint": hashlib.sha256(
                    json.dumps(settings, sort_keys=True).encode()
                ).hexdigest(),
                "predictions": [],
            }
            with self.assertRaisesRegex(ValueError, "Actor source/release changed"):
                verify_release_envelope(envelope, root)


if __name__ == "__main__":
    unittest.main()
