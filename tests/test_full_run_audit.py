"""Regressions for observed protocol barriers and independent scoring boundaries."""

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

P = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(P))
from baselines.common.answers import protocol_decision_schema
from baselines.react.runtime import run_react
from evaluation.answer import score_answer
from evaluation.scoring import evaluate_v2
from evaluation.runner import evaluate_package
from tools.catalog import ToolCatalog
from jsonschema import Draft202012Validator
from test_project import ScriptedClient
from test_loop_and_format import SchemaClient, A, FINISH, SCHEMA, action
from test_remediation import reference, REGISTRY


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
    def test_incomplete_path_match_is_diagnostic_not_strict_planning_success(self):
        r = reference(1)
        pred = {
            "id": "CONTROL",
            "completed": False,
            "status": "failed",
            "failure_reason": "Stopped",
            "calls": [{"tool": "Example", "arguments": {"x": 1}, "status": "success"}],
            "final_answer": None,
        }
        with tempfile.TemporaryDirectory() as d:
            x = evaluate_v2(
                [r], [pred], Path(d) / "score.json", registry=REGISTRY, trace_root=P
            )
        self.assertFalse(x["results"][0]["planning_strict"])
        self.assertTrue(x["results"][0]["reference_path_match"])
        self.assertEqual(x["summary"]["reference_path_match_rate"], 1)

    def test_unordered_document_keys_still_reject_duplicates_and_extra_values(self):
        r = reference(["experiment", "counts", "note"])
        r["scoring"]["field_rules"][0]["comparison"] = "unordered_string_array"
        self.assertEqual(
            score_answer(r, {"results": {"value": ["note", "counts", "experiment"]}})[
                "status"
            ],
            "passed",
        )
        self.assertEqual(
            score_answer(r, {"results": {"value": ["note", "counts", "counts"]}})[
                "status"
            ],
            "failed",
        )
        ordered = reference([1, 2, 3])
        self.assertEqual(
            score_answer(ordered, {"results": {"value": [3, 2, 1]}})["status"], "failed"
        )

    def test_old_predictions_cannot_be_scored_against_revised_public_tasks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "evaluation").mkdir()
            (root / "tasks").mkdir()
            (root / "evaluation/references.jsonl").write_text("{}\n")
            (root / "tasks/questions.jsonl").write_text("{}\n")
            p = root / "old.json"
            p.write_text(
                json.dumps(
                    {
                        "settings": {
                            "actor_file_hashes": {"tasks/questions.jsonl": "old-hash"}
                        },
                        "predictions": [],
                    }
                )
            )
            with patch("evaluation.runner.validate_package"):
                with self.assertRaisesRegex(ValueError, "Task release changed"):
                    evaluate_package(root, p, root / "score.json")

    def test_compact_pilot_still_checks_all_quantities_and_scientific_caveats(self):
        refs = {
            r["id"]: r
            for l in (P / "evaluation/references.jsonl").read_text().splitlines()
            if (r := json.loads(l))
        }
        for key in ["FLOW-0232", "FLOW-0285", "FLOW-0481"]:
            r = refs[key]
            self.assertEqual(score_answer(r, r["expected_answer"])["status"], "passed")
        r = refs["FLOW-0285"]
        bad = copy.deepcopy(r["expected_answer"])
        bad["results"]["causation_established"] = True
        self.assertEqual(score_answer(r, bad)["status"], "failed")
        bad = copy.deepcopy(r["expected_answer"])
        bad["results"]["order_sensitive_measure"] = "unsupported_measure"
        self.assertEqual(score_answer(r, bad)["status"], "failed")
        r = refs["FLOW-0481"]
        bad = copy.deepcopy(r["expected_answer"])
        bad["results"]["test"]["p_value"] = 0.79
        self.assertEqual(score_answer(r, bad)["status"], "failed")


if __name__ == "__main__":
    unittest.main()
