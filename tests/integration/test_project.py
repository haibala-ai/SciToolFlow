"""Names-first protocol, discovery neutrality, thinking and clean step trajectories."""

from tests.support.clients import ScriptedClient

import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

P = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(P))
from baselines.react.runtime import run_react, build_prompt
from tools.catalog import ToolCatalog
from tools import execute


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.catalog = ToolCatalog()

    def test_discovery_hides_internal_execution_binding(self):
        result = self.catalog.describe("PearsonCorrelation")["tools"][
            "PearsonCorrelation"
        ]
        self.assertNotIn("execution", result)
        self.assertNotIn("source", result)
        self.assertIn("input_schema", result)

    def test_public_task_command_never_reads_private_evaluation_files(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from unittest.mock import patch
        from cli import main

        original = Path.read_text

        def guarded(path, *args, **kwargs):
            if P / "evaluation" in path.parents:
                raise AssertionError("Public task lookup read private references")
            return original(path, *args, **kwargs)

        output = StringIO()
        with (
            patch.object(Path, "read_text", guarded),
            patch.object(sys, "argv", ["scitoolflow", "task", "SMAS-0103"]),
            redirect_stdout(output),
        ):
            main()
        row = json.loads(output.getvalue())
        self.assertEqual(row["id"], "SMAS-0103")
        self.assertIn("question", row)
        self.assertNotIn("expected_answer", row)
        self.assertNotIn("tool_path", row)

    def test_initial_prompt_is_names_only(self):
        prompt = build_prompt(self.catalog, {"steps": 40})
        self.assertIn('"Chemical":', prompt)
        self.assertIn("DescribeTools", prompt)
        self.assertNotIn("PearsonCorrelation(x", prompt)
        self.assertNotIn(
            self.catalog.tools["PearsonCorrelation"]["description"], prompt
        )
        self.assertNotIn("input_schema", prompt)

    def test_describe_batch_schema_and_unknown(self):
        result = self.catalog.describe(
            ["PearsonCorrelation", "ParseJSONDocument", "MissingTool"]
        )
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["unknown"][0]["name"], "MissingTool")
        for tool in result["tools"].values():
            self.assertTrue(
                all(
                    tool.get(k)
                    for k in [
                        "description",
                        "call_signature",
                        "input_schema",
                        "output_schema",
                        "returns",
                    ]
                )
            )
            self.assertTrue(
                all(p["description"] and p["type"] for p in tool["parameters"])
            )
        self.assertEqual(
            execute(
                "DescribeTools", {"tools": ["PearsonCorrelation"]}, catalog=self.catalog
            )["status"],
            "success",
        )

    def test_source_optional_parameter_is_public(self):
        parameters = self.catalog.tools["InspectPDBQuality"]["parameters"]
        chain = next(p for p in parameters if p["name"] == "mse_to_m")
        self.assertFalse(chain["required"])
        self.assertIs(chain["default"], False)


class RuntimeTests(unittest.TestCase):
    def test_required_field_feedback_identifies_wrong_nesting_without_moving_values(
        self,
    ):
        from baselines.react.feedback import schema_issues, required_answer_fields
        from jsonschema import Draft202012Validator

        schema = {
            "type": "object",
            "properties": {
                "results": {
                    "type": "object",
                    "properties": {"value": {"type": "number", "default": 42}},
                    "required": ["value"],
                }
            },
            "required": ["results"],
        }
        answer = {"results": {"other": {"value": 7}}}
        before = copy.deepcopy(answer)
        issues = schema_issues(Draft202012Validator(schema), answer)
        self.assertEqual(issues[0]["path"], "/results/value")
        self.assertEqual(
            issues[0]["same_name_at_other_paths"], ["/results/other/value"]
        )
        self.assertEqual(answer, before)
        fields = required_answer_fields(schema)
        self.assertEqual(fields[-1], {"path": "/results/value", "type": "number"})
        self.assertNotIn("42", json.dumps(fields))

    def test_empty_tool_name_does_not_discard_a_valid_sibling(self):
        result, saved, _ = self.run_script(
            [
                {
                    "actions": [
                        {"tool": "", "arguments": {}},
                        {"tool": "ParseJSONDocument", "arguments": {"json_text": "{}"}},
                    ]
                },
                {"finish": {"value": 7}},
            ]
        )
        self.assertEqual(result["stats"]["scientific_calls"], 1)
        self.assertEqual(saved["steps"][0]["calls"][0]["action_index"], 1)

    def test_request_timeout_at_deadline_is_a_task_deadline(self):
        current = [0]
        client = ScriptedClient([])

        def expired(*args, **kwargs):
            current[0] = 2
            raise TimeoutError("request expired")

        client.request = expired
        with tempfile.TemporaryDirectory() as directory:
            result = run_react(
                "Read JSON",
                catalog=ToolCatalog(),
                client=client,
                invoke=lambda *a, **k: None,
                trace_dir=directory,
                clock=lambda: current[0],
                task_timeout=1,
            )
        self.assertEqual(result["failure_reason"], "TaskDeadline")

    def test_invalid_scope_fails_before_model_construction(self):
        import os
        from unittest.mock import patch
        from baselines.react.runner import run_batch

        with (
            patch.dict(os.environ, {"SCITOOL_TOOL_SCOPE": "invalid-scope"}),
            patch("baselines.react.runner.GenerationClient") as model,
        ):
            with self.assertRaisesRegex(ValueError, "Unknown execution scope"):
                run_batch(None)
            model.assert_not_called()

    def test_direct_valid_call_needs_no_discovery(self):
        result, saved, _ = self.run_script(
            [
                {
                    "actions": [
                        {
                            "tool": "ParseJSONDocument",
                            "arguments": {"json_text": '{"value":7}'},
                        }
                    ]
                },
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
        self.assertEqual(result["final_answer"], {"value": 7})
        self.assertEqual(result["stats"]["discovery_calls"], 0)
        self.assertEqual(result["stats"]["protocol_errors"], 0)

    def test_bad_argument_does_not_discard_valid_sibling(self):
        result, saved, client = self.run_script(
            [
                {
                    "actions": [
                        {
                            "tool": "ParseJSONDocument",
                            "arguments": {"wrong_name": "{}"},
                        },
                        {
                            "tool": "ParseJSONDocument",
                            "arguments": {"json_text": '{"value":7}'},
                        },
                    ]
                },
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
        self.assertEqual(result["final_answer"], {"value": 7})
        self.assertEqual(result["stats"]["scientific_calls"], 1)
        self.assertEqual(result["stats"]["rejected_actions"], 1)
        first = saved["steps"][0]
        self.assertEqual(first["calls"][0]["action_index"], 1)
        feedback = first["action_errors"][0]
        self.assertFalse(feedback["executed"])
        self.assertIn("wrong_name", feedback["message"])
        self.assertEqual(
            feedback["expected_input_schema"],
            ToolCatalog().tools["ParseJSONDocument"]["input_schema"],
        )
        self.assertIn("json_text", feedback["expected_input_schema"]["properties"])
        self.assertIn("json_file", feedback["expected_input_schema"]["properties"])
        self.assertEqual(feedback["suggested_action"]["tool"], "DescribeTools")
        self.assertNotIn("input_schema", feedback)
        self.assertIn("action_errors", client.requests[1][-2]["content"])

    def test_invalid_action_can_be_corrected_without_discovery(self):
        result, saved, _ = self.run_script(
            [
                {"actions": [{"tool": "ParseJSONDocument", "arguments": {}}]},
                {
                    "actions": [
                        {"tool": "ParseJSONDocument", "arguments": {"json_text": "{}"}}
                    ]
                },
                {"finish": {"value": 7}},
            ]
        )
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["stats"]["rejected_actions"], 1)
        self.assertEqual(result["stats"]["discovery_calls"], 0)

    def test_budget_exhaustion_allows_a_finish_in_next_decision(self):
        result, saved, _ = self.run_script(
            [
                {
                    "actions": [
                        {"tool": "ParseJSONDocument", "arguments": {"json_text": "{}"}}
                    ]
                },
                {
                    "actions": [
                        {"tool": "ParseJSONDocument", "arguments": {"json_text": "{}"}}
                    ]
                },
                {"finish": {"value": 7}},
            ],
            max_calls=1,
        )
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["stats"]["scientific_calls"], 1)
        self.assertIn("nothing executed", saved["steps"][1]["error"]["message"])

    def test_finish_feedback_identifies_nested_path(self):
        result, saved, _ = self.run_script(
            [
                {"finish": {"results": {"value": "bad"}}},
                {"finish": {"results": {"value": 7}}},
            ],
            answer_schema={
                "type": "object",
                "properties": {
                    "results": {
                        "type": "object",
                        "properties": {"value": {"type": "number"}},
                    }
                },
            },
        )
        self.assertEqual(result["status"], "completed")
        self.assertIn("/results/value", saved["steps"][0]["error"]["message"])

    def test_stop_is_an_explicit_unsuccessful_attempt(self):
        result, saved, _ = self.run_script(
            [{"stop": {"reason": "Required source unavailable"}}]
        )
        self.assertEqual(result["status"], "failed")
        self.assertIsNone(result["final_answer"])
        self.assertTrue(result["failure_reason"].startswith("AgentStopped:"))
        self.assertEqual(saved["steps"][0]["type"], "stop")

    def test_optional_note_beside_action_is_not_a_thinking_turn(self):
        result, saved, _ = self.run_script(
            [
                {
                    "think": "Read the document",
                    "actions": [
                        {"tool": "ParseJSONDocument", "arguments": {"json_text": "{}"}}
                    ],
                },
                {"finish": {"value": 7}},
            ]
        )
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["stats"]["think_steps"], 0)
        self.assertTrue(saved["steps"][0]["normalizations"])

    def test_live_budget_counts_queries_thinking_and_final_decision(self):
        result, saved, client = self.run_script(
            [
                {"think": "Read next"},
                {"finish": {"value": 7}},
            ]
        )
        first = json.loads(client.requests[0][-1]["content"])["remaining_budget"]
        last = json.loads(client.requests[1][-1]["content"])["remaining_budget"]
        self.assertEqual(first["decisions_including_current"], 2)
        self.assertEqual(last["decisions_including_current"], 1)
        self.assertTrue(last["final_decision"])
        self.assertIsNone(first["think_steps"])
        self.assertEqual(first["model_requests"] - last["model_requests"], 1)

    def test_interruption_saves_trace_and_propagates(self):
        from unittest.mock import Mock

        client = ScriptedClient([])
        client.request = Mock(side_effect=KeyboardInterrupt)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(KeyboardInterrupt):
                run_react(
                    "Read JSON",
                    catalog=ToolCatalog(),
                    client=client,
                    invoke=lambda *a, **k: None,
                    trace_dir=directory,
                )
            trace = json.loads(
                next(Path(directory).glob("*/trajectory.json")).read_text()
            )
            self.assertEqual(trace["status"], "interrupted")
            self.assertEqual(trace["failure_reason"], "Interrupted")

    def test_resume_fingerprint_covers_worker_and_shared_helpers(self):
        from baselines.react.runner import actor_file_hashes

        hashes = actor_file_hashes(P)
        for name in [
            "tools/runtime/worker.py",
            "tools/runtime/dispatch.py",
            "tools/implementations/shared/common.py",
            "src/models/client.py",
            "tasks/assets.py",
            "tasks/schema.py",
            "src/utils/io.py",
            "src/utils/paths.py",
            "cli.py",
        ]:
            self.assertIn(name, hashes)
        self.assertFalse(any(name.startswith("evaluation/") for name in hashes))

    def run_script(self, replies, **kwargs):
        client = ScriptedClient(replies)
        catalog = ToolCatalog()

        def invoke(name, args, **options):
            if name == "DescribeTools":
                return execute(name, args, catalog=catalog)
            return {
                "status": "success",
                "output": {"document": json.loads(args["json_text"])},
            }

        with tempfile.TemporaryDirectory() as directory:
            result = run_react(
                "Read the supplied JSON value.",
                catalog=catalog,
                client=client,
                invoke=invoke,
                trace_dir=directory,
                case_id="CONTROL",
                max_iterations=len(replies),
                **kwargs,
            )
            saved = json.loads(Path(result["trace_path"]).read_text())
        return result, saved, client

    def test_discover_think_act_finish_has_one_step_per_decision(self):
        replies = [
            {
                "actions": [
                    {
                        "tool": "DescribeTools",
                        "arguments": {"tools": ["ParseJSONDocument"]},
                    }
                ]
            },
            {"think": "The documented parser can read the provided document."},
            {
                "actions": [
                    {
                        "tool": "ParseJSONDocument",
                        "arguments": {"json_text": '{"value":7}'},
                    }
                ]
            },
            {
                "finish": {
                    "value": {"$observation": "o001", "field": ["document", "value"]}
                }
            },
        ]
        result, saved, client = self.run_script(replies)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["final_answer"], {"value": 7})
        self.assertEqual(
            [s["type"] for s in saved["steps"]], ["tools", "think", "tools", "finish"]
        )
        self.assertEqual(result["stats"]["scientific_calls"], 1)
        self.assertEqual(result["stats"]["discovery_calls"], 1)
        self.assertEqual(result["stats"]["think_steps"], 1)
        self.assertEqual(len(client.requests), 4)
        self.assertNotIn("event", saved)
        self.assertTrue(
            any(
                "call_signature" in message["content"] for message in client.requests[1]
            )
        )

    def test_consecutive_thinking_is_bounded(self):
        result, saved, _ = self.run_script(
            [{"think": "Check what remains."}] * 4,
            max_consecutive_thinks=1,
            max_protocol_errors=2,
        )
        self.assertEqual(result["failure_reason"], "RepeatedProtocolError")
        self.assertEqual(result["stats"]["think_steps"], 1)

    def test_unknown_tool_feedback_names_offender(self):
        result, saved, _ = self.run_script(
            [{"actions": [{"tool": "InventedScientificTool", "arguments": {}}]}],
            max_protocol_errors=1,
        )
        self.assertIn(
            "InventedScientificTool", saved["steps"][0]["action_errors"][0]["message"]
        )
        self.assertEqual(result["stats"]["scientific_calls"], 0)

    def test_discipline_prefix_feedback_queries_actual_catalogue_names(self):
        result, saved, _ = self.run_script(
            [{"actions": [{"tool": "General:ParseJSONDocument", "arguments": {}}]}],
            max_protocol_errors=1,
        )
        error = saved["steps"][0]["action_errors"][0]
        self.assertIn("not tool-name prefixes", error["naming_hint"])
        suggested = error["suggested_action"]
        self.assertEqual(suggested["tool"], "DescribeTools")
        self.assertIn("ParseJSONDocument", suggested["arguments"]["tools"])
        self.assertEqual(result["stats"]["scientific_calls"], 0)

    def test_incomplete_json_is_not_repaired_into_a_call(self):
        from baselines.common.protocol import parse_reply

        with self.assertRaises(ValueError):
            parse_reply('{"actions":[')

    def test_local_client_bootstraps_bundled_runtime(self):
        import types
        from unittest.mock import patch
        from src.models.client import GenerationClient

        fake = types.SimpleNamespace(
            RUNTIME=types.SimpleNamespace(request=lambda *a, **k: {"text": "{}"})
        )
        with (
            patch.dict(sys.modules, {"src.models.local": fake}),
            patch("src.utils.paths.bootstrap_runtime") as bootstrap,
        ):
            self.assertEqual(GenerationClient("local").request([])["text"], "{}")
            bootstrap.assert_called_once()


if __name__ == "__main__":
    unittest.main()
