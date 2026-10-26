"""Consecutive-step termination and public-schema correction regressions."""

from tests.support.loop import action, A, FINISH, SCHEMA, SchemaClient

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

P = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(P))
from baselines.common.answers import correction_decision_schema
from baselines.common.repetition import ConsecutiveToolSteps
from baselines.react.runtime import run_react
from baselines.scitoolagent.runtime import run_scitoolagent
from src.models.client import GenerationClient
from tools.catalog import ToolCatalog
from jsonschema import Draft202012Validator
from tests.support.clients import ScriptedClient
from tests.support.planner import StaticRetriever


class ConsecutiveLoopTests(unittest.TestCase):
    def run_decisions(self, decisions, **options):
        dispatched = []
        client = ScriptedClient(decisions)

        def invoke(name, args, **kwargs):
            dispatched.append((name, args))
            return {
                "status": "success",
                "output": {
                    "source_text": json.dumps({"value": 7}),
                    "document": {"value": 7},
                },
            }

        with tempfile.TemporaryDirectory() as directory:
            result = run_react(
                "Read JSON.",
                catalog=ToolCatalog(),
                client=client,
                invoke=invoke,
                trace_dir=directory,
                answer_schema=SCHEMA,
                protocol_schema_guard=False,
                max_iterations=40,
                **options,
            )
        return result, dispatched, client

    def test_ten_identical_steps_stop_without_an_eleventh_model_request(self):
        result, dispatched, client = self.run_decisions([A] * 10 + [FINISH])
        self.assertEqual(result["failure_reason"], "RepeatedToolLoop")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(len(client.requests), 10)
        self.assertEqual(len(dispatched), 10)
        self.assertEqual(result["stats"]["scientific_calls"], 10)
        self.assertEqual(result["steps"][-1]["loop_termination"]["count"], 10)
        self.assertEqual(result["steps"][-1]["error"]["type"], "RepeatedToolLoop")
        self.assertIsNone(result["final_answer"])

    def test_nonconsecutive_reuse_does_not_accumulate(self):
        for interruption in [
            {"think": "Check the existing result."},
            {"inspect": {"observation_id": "o001", "field": ["document"]}},
            {"actions": [action(8)]},
            {"actions": [action(), action(8)]},
            {
                "actions": [
                    {
                        "tool": "DescribeTools",
                        "arguments": {"tools": ["ParseJSONDocument"]},
                    }
                ]
            },
            {"unknown_operation": "invalid"},
        ]:
            with self.subTest(interruption=interruption):
                result, _, _ = self.run_decisions(
                    [A] * 9 + [interruption] + [A] * 9 + [FINISH]
                )
                self.assertEqual(result["status"], "completed")
                self.assertEqual(
                    result["stats"]["max_consecutive_identical_tool_steps"], 9
                )

    def test_multiple_identical_calls_in_a_batch_are_one_decision_step(self):
        result, dispatched, client = self.run_decisions(
            [{"actions": [action(), action()]}] * 10 + [FINISH]
        )
        self.assertEqual(result["failure_reason"], "RepeatedToolLoop")
        self.assertEqual(len(dispatched), 20)
        self.assertEqual(len(client.requests), 10)

    def test_resolved_observation_arguments_count_as_identical(self):
        cited = {
            "actions": [
                {
                    "tool": "ParseJSONDocument",
                    "arguments": {
                        "json_text": {"$observation": "o001", "field": ["source_text"]}
                    },
                }
            ]
        }
        result, _, _ = self.run_decisions([A] + [cited] * 9 + [FINISH])
        self.assertEqual(result["failure_reason"], "RepeatedToolLoop")

    def test_argument_key_order_is_ignored_but_values_are_not(self):
        tracker = ConsecutiveToolSteps()

        def step(args):
            return {"type": "tools", "calls": [{"tool": "Example", "arguments": args}]}

        self.assertEqual(tracker.observe(step({"a": 1, "b": 2}), 1), 1)
        self.assertEqual(tracker.observe(step({"b": 2, "a": 1}), 2), 2)
        self.assertEqual(tracker.observe(step({"b": 3, "a": 1}), 3), 1)

    def test_scitoolagent_cannot_replan_around_the_terminal_limit(self):
        client = ScriptedClient(
            [{"finish": {"plan": ["ParseJSONDocument"] * 10}}] + [A] * 10
        )
        with tempfile.TemporaryDirectory() as directory:
            result = run_scitoolagent(
                "Read JSON.",
                catalog=ToolCatalog(),
                client=client,
                invoke=lambda *a, **k: {
                    "status": "success",
                    "output": {
                        "tools": {"ParseJSONDocument": {}},
                        "document": {"value": 7},
                    },
                },
                retriever=StaticRetriever(),
                trace_dir=directory,
                answer_schema=SCHEMA,
                protocol_schema_guard=False,
            )
        self.assertEqual(result["failure_reason"], "RepeatedToolLoop")
        self.assertEqual(result["stats"]["scientific_calls"], 10)
        self.assertEqual(len(client.requests), 11)
        self.assertEqual(len(result["retrievals"]), 1)


class AnswerSchemaGuardTests(unittest.TestCase):
    def test_shape_does_not_export_literals_or_scientific_bounds(self):
        schema = {
            "type": "object",
            "properties": {
                "value": {
                    "type": "number",
                    "const": 81397,
                    "enum": [81397],
                    "default": 81397,
                    "minimum": 81397,
                    "description": "SECRET_VALUE",
                    "examples": [81397],
                }
            },
            "required": ["value"],
        }
        guard = correction_decision_schema(schema)
        text = json.dumps(guard)
        self.assertNotIn("81397", text)
        self.assertNotIn("SECRET_VALUE", text)
        validator = Draft202012Validator(guard)
        for decision in [
            FINISH,
            A,
            {"think": "Assess evidence."},
            {"inspect": {"observation_id": "o001"}},
            {"stop": {"reason": "Evidence missing."}},
            {"finish": {"value": {"$observation": "o001", "field": ["value"]}}},
        ]:
            self.assertTrue(validator.is_valid(decision), decision)
        self.assertFalse(validator.is_valid({"finish": {"other": {"value": 7}}}))

    def test_guard_activates_after_error_and_preserves_tools_and_citations(self):
        client = SchemaClient(
            [
                {"finish": {"other": {"value": 7}}},
                A,
                {
                    "finish": {
                        "value": {
                            "$observation": "o001",
                            "field": ["document", "value"],
                        }
                    }
                },
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            result = run_react(
                "Read JSON.",
                catalog=ToolCatalog(),
                client=client,
                invoke=lambda *a, **k: {
                    "status": "success",
                    "output": {"document": {"value": 7}},
                },
                trace_dir=directory,
                answer_schema=SCHEMA,
                protocol_schema_guard=False,
            )
        self.assertEqual(result["final_answer"], {"value": 7})
        self.assertNotIn("response_schema", client.options[0])
        self.assertIn("response_schema", client.options[1])
        self.assertEqual(result["stats"]["answer_schema_guard_requests"], 2)
        self.assertEqual(result["stats"]["answer_format_errors"], 1)
        self.assertEqual(result["stats"]["scientific_calls"], 1)
        self.assertIn("response_schema_sha256", result["steps"][1]["model"])

    def test_guard_can_be_disabled(self):
        client = SchemaClient([{"finish": {}}, FINISH])
        with tempfile.TemporaryDirectory() as directory:
            result = run_react(
                "Report input.",
                catalog=ToolCatalog(),
                client=client,
                invoke=lambda *a, **k: None,
                trace_dir=directory,
                answer_schema=SCHEMA,
                protocol_schema_guard=False,
                answer_schema_guard=False,
            )
        self.assertEqual(result["status"], "completed")
        self.assertTrue(
            all("response_schema" not in options for options in client.options)
        )

    def test_vllm_transport_sends_the_requested_schema(self):
        class Response:
            status_code = 200

            def json(self):
                return {
                    "choices": [
                        {
                            "message": {"content": json.dumps(FINISH)},
                            "finish_reason": "stop",
                        }
                    ]
                }

        class Session:
            def post(self, url, **kwargs):
                self.payload = kwargs["json"]
                return Response()

        session = Session()
        client = GenerationClient("vllm", session=session)
        schema = correction_decision_schema(SCHEMA)
        with client.generation_scope():
            client.request(
                [{"role": "user", "content": "Format correction"}],
                response_schema=schema,
            )
        self.assertEqual(session.payload["response_format"]["type"], "json_schema")
        self.assertEqual(
            session.payload["response_format"]["json_schema"]["schema"], schema
        )
        self.assertEqual(session.payload["max_tokens"], 4096)


if __name__ == "__main__":
    unittest.main()
