"""Shared public format guidance and the distinct KG planner–executor baseline."""

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

P = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(P))
from baselines.common.answers import answer_format, render_answer_format
from baselines.react.runtime import run_react
from baselines.scitoolagent.runtime import run_scitoolagent
from baselines.scitoolagent.retrieval import GraphRetriever
from tools.catalog import ToolCatalog
from tools.executor import execute
from test_project import ScriptedClient

SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "object",
            "properties": {"value": {"type": "number"}},
            "required": ["value"],
        }
    },
    "required": ["results"],
}
CALL = {
    "actions": [
        {"tool": "ParseJSONDocument", "arguments": {"json_text": '{"value":7}'}}
    ]
}
PLAN = {"finish": {"plan": ["ParseJSONDocument"]}}
FINISH = {
    "finish": {
        "results": {"value": {"$observation": "o001", "field": ["document", "value"]}}
    }
}


class PublicFormatTests(unittest.TestCase):
    def test_template_does_not_include_default_const_enum_or_descriptions(self):
        schema = {
            "type": "object",
            "properties": {
                "value": {
                    "type": "number",
                    "default": 81397,
                    "const": 81397,
                    "enum": [81397],
                    "description": "SECRET_EXPECTED_ANSWER",
                }
            },
            "required": ["value"],
        }
        text = json.dumps(answer_format(schema))
        self.assertNotIn("81397", text)
        self.assertNotIn("SECRET_EXPECTED_ANSWER", text)
        self.assertEqual(
            answer_format(schema)["finish_template"]["finish"]["value"],
            "<FILL:number from evidence>",
        )

    def test_tree_preserves_siblings_and_explains_illustrative_arrays(self):
        schema = {
            "type": "object",
            "required": ["results"],
            "properties": {
                "results": {
                    "type": "object",
                    "required": ["left", "right"],
                    "properties": {
                        "left": {
                            "type": "object",
                            "required": ["id"],
                            "properties": {"id": {"type": "string"}},
                        },
                        "right": {"type": "array", "items": {"type": "number"}},
                    },
                }
            },
        }
        guide = answer_format(schema)
        tree = guide["finish_template"]["finish"]
        self.assertEqual(set(tree["results"]), {"left", "right"})
        self.assertIn("actual array length", render_answer_format(guide))

    def test_format_error_resends_readable_tree_without_changing_answer(self):
        client = ScriptedClient(
            [
                {"finish": {"results": {"other": {"value": 7}}}},
                {"finish": {"results": {"value": 7}}},
            ]
        )
        with tempfile.TemporaryDirectory() as d:
            result = run_react(
                "Report a supplied number.",
                catalog=ToolCatalog(),
                client=client,
                invoke=lambda *a, **k: None,
                trace_dir=d,
                answer_schema=SCHEMA,
                max_iterations=2,
            )
        self.assertEqual(result["status"], "completed")
        step = result["steps"][0]
        self.assertEqual(step["error"]["type"], "AnswerFormatError")
        self.assertEqual(result["stats"]["answer_format_errors"], 1)
        self.assertIn("FINAL ANSWER FORMAT", client.requests[1][-2]["content"])
        self.assertIn("/results/other/value", step["error"]["message"])
        self.assertEqual(
            step["decision"]["finish"], {"results": {"other": {"value": 7}}}
        )

    def test_literal_template_is_not_accepted_as_a_string_answer(self):
        client = ScriptedClient(
            [
                {"finish": {"value": "<FILL:string from evidence>"}},
                {"stop": {"reason": "No observation"}},
            ]
        )
        with tempfile.TemporaryDirectory() as d:
            result = run_react(
                "Report a value.",
                catalog=ToolCatalog(),
                client=client,
                invoke=lambda *a, **k: None,
                trace_dir=d,
                answer_schema={
                    "type": "object",
                    "properties": {"value": {"type": "string"}},
                    "required": ["value"],
                },
                max_iterations=2,
            )
        self.assertIsNone(result["final_answer"])
        self.assertEqual(result["stats"]["answer_format_errors"], 1)


class StaticRetriever:
    def retrieve(self, question, deadline):
        return {
            "tools": [
                {
                    "name": "ParseJSONDocument",
                    "description": "Parse JSON",
                    "graph_triples": [],
                }
            ],
            "seed_tools": ["ParseJSONDocument"],
        }


class SciToolAgentTests(unittest.TestCase):
    def invoke(self, name, args, **kwargs):
        self.invocations.append(name)
        if name == "DescribeTools":
            return execute(name, args, catalog=self.catalog)
        return {
            "status": "success",
            "output": {"document": json.loads(args["json_text"])},
        }

    def run_case(self, replies, **kwargs):
        self.invocations = []
        self.catalog = ToolCatalog()
        client = kwargs.pop("client", None) or ScriptedClient(replies)
        retriever = kwargs.pop("retriever", StaticRetriever())
        with tempfile.TemporaryDirectory() as d:
            result = run_scitoolagent(
                "Parse JSON and report the value.",
                catalog=self.catalog,
                client=client,
                invoke=self.invoke,
                trace_dir=d,
                case_id="CONTROL",
                answer_schema=SCHEMA,
                retriever=retriever,
                **kwargs
            )
            files = list(Path(d).rglob("trajectory.json"))
            self.assertEqual(len(files), 1)
            saved = json.loads(files[0].read_text())
        return result, saved, client

    def test_planner_executor_summary_share_one_trace_and_real_costs(self):
        result, saved, client = self.run_case([PLAN, CALL, FINISH])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["final_answer"], {"results": {"value": 7}})
        self.assertEqual(result["stats"]["model_turns"], 3)
        self.assertEqual(result["stats"]["scientific_calls"], 1)
        self.assertEqual(result["stats"]["discovery_calls"], 1)
        self.assertEqual(
            [s["phase"] for s in saved["steps"]], ["planner", "executor", "summarizer"]
        )
        self.assertTrue(saved["preparations"][0]["automatic"])
        self.assertEqual(len(client.requests), 3)
        self.assertNotIn("TOOL NAMES BY DISCIPLINE", client.requests[0][0]["content"])

    def test_global_decision_budget_includes_the_planner(self):
        result, _, _ = self.run_case([PLAN, CALL], max_iterations=2)
        self.assertEqual(result["failure_reason"], "DecisionBudget")
        self.assertEqual(result["stats"]["model_turns"], 2)
        self.assertIsNone(result["final_answer"])

    def test_repeated_plan_items_keep_unique_observation_ids_and_cached_contract(self):
        finish = copy.deepcopy(FINISH)
        finish["finish"]["results"]["value"]["$observation"] = "o002"
        result, _, _ = self.run_case(
            [
                {"finish": {"plan": ["ParseJSONDocument", "ParseJSONDocument"]}},
                CALL,
                CALL,
                finish,
            ]
        )
        self.assertEqual(result["status"], "completed")
        self.assertEqual(
            [c["observation_id"] for c in result["calls"]], ["d001", "o001", "o002"]
        )
        self.assertEqual(result["stats"]["scientific_calls"], 2)
        self.assertEqual(result["stats"]["discovery_calls"], 1)

    def test_executor_cannot_replace_the_planned_tool(self):
        other = {
            "actions": [
                {
                    "tool": "PearsonCorrelation",
                    "arguments": {"x": [1, 2, 3], "y": [1, 3, 5]},
                }
            ]
        }
        result, saved, _ = self.run_case([PLAN, other, CALL, FINISH])
        self.assertEqual(result["status"], "completed")
        self.assertNotIn("PearsonCorrelation", self.invocations)
        self.assertEqual(result["stats"]["rejected_actions"], 1)
        self.assertEqual(result["stats"]["model_turns"], 4)

    def test_role_handoffs_preserve_plan_position_arguments_and_task_contract(self):
        second = copy.deepcopy(CALL)
        second["actions"][0]["arguments"]["json_text"] = '{"value":9}'
        finish = copy.deepcopy(FINISH)
        finish["finish"]["results"]["value"]["$observation"] = "o002"
        result, saved, client = self.run_case(
            [{"finish": {"plan": ["ParseJSONDocument"] * 2}}, CALL, second, finish]
        )
        self.assertEqual(result["final_answer"], {"results": {"value": 9}})
        contexts = [json.loads(request[1]["content"]) for request in client.requests]
        self.assertTrue(all(row["task_answer_schema"] == SCHEMA for row in contexts))
        self.assertEqual(contexts[1]["plan_position"], 1)
        self.assertEqual(contexts[2]["plan_position"], 2)
        self.assertEqual(contexts[2]["ordered_plan"], ["ParseJSONDocument"] * 2)
        previous = contexts[2]["previous_observations"][0]
        self.assertEqual(previous["arguments"], CALL["actions"][0]["arguments"])
        self.assertEqual(previous["output"], {"document": {"value": 7}})
        self.assertEqual(saved["phases"][2]["plan_position"], 2)

    def test_role_protocol_hides_discovery_and_limits_executor_to_planned_tool(self):
        from jsonschema import Draft202012Validator
        from test_loop_and_format import SchemaClient

        client = SchemaClient([PLAN, CALL, FINISH])
        result, _, _ = self.run_case([], client=client)
        self.assertEqual(result["status"], "completed")
        discovery = {
            "actions": [
                {"tool": "DescribeTools", "arguments": {"tools": ["ParseJSONDocument"]}}
            ]
        }
        for options in client.options:
            self.assertTrue(
                list(
                    Draft202012Validator(options["response_schema"]).iter_errors(
                        discovery
                    )
                )
            )
        self.assertTrue(
            list(
                Draft202012Validator(client.options[0]["response_schema"]).iter_errors(
                    CALL
                )
            )
        )
        self.assertFalse(
            list(
                Draft202012Validator(client.options[1]["response_schema"]).iter_errors(
                    CALL
                )
            )
        )
        self.assertTrue(
            list(
                Draft202012Validator(client.options[2]["response_schema"]).iter_errors(
                    CALL
                )
            )
        )

    def test_role_discovery_rejection_is_enforced_without_native_schema_support(self):
        discovery = {
            "actions": [
                {"tool": "DescribeTools", "arguments": {"tools": ["ParseJSONDocument"]}}
            ]
        }
        result, _, _ = self.run_case([discovery, PLAN, CALL, FINISH])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(self.invocations.count("DescribeTools"), 1)
        self.assertEqual(result["stats"]["rejected_actions"], 1)

    def test_planner_budget_is_distinguished_from_exhausted_global_budget(self):
        result, _, _ = self.run_case(
            [{"think": "Assess candidate ordering"}] * 8,
            max_iterations=20,
            max_reasoning_turns=10,
            max_consecutive_thinks=10,
        )
        self.assertEqual(result["failure_reason"], "PlannerDecisionBudget")
        self.assertEqual(result["stats"]["model_turns"], 8)

    def test_executor_preserves_shared_dispatcher_blocked_feedback(self):
        original = self.invoke

        def dispatcher(name, args, **kwargs):
            if name == "DescribeTools":
                return original(name, args, **kwargs)
            return {
                "status": "blocked",
                "output": None,
                "error_type": "MissingResource",
                "error": "Required resource unavailable",
            }

        stop = {"stop": {"reason": "Required resource unavailable"}}
        with patch.object(self, "invoke", dispatcher):
            result, _, _ = self.run_case([PLAN, CALL, stop, stop])
        scientific = [c for c in result["calls"] if c["kind"] == "scientific"]
        self.assertEqual(scientific[0]["status"], "blocked")
        self.assertEqual(scientific[0]["error_type"], "MissingResource")
        self.assertIsNone(result["final_answer"])

    def test_actor_does_not_read_private_evaluation_files(self):
        original = Path.read_text

        def guarded(path, *args, **kwargs):
            if P / "evaluation" in path.parents:
                raise AssertionError("Actor read private reference")
            return original(path, *args, **kwargs)

        with patch.object(Path, "read_text", guarded):
            result, _, _ = self.run_case([PLAN, CALL, FINISH])
        self.assertEqual(result["status"], "completed")

    def test_graph_filter_retains_dataflow_but_removes_shared_io_peers(self):
        ret = GraphRetriever.__new__(GraphRetriever)
        ret.config = {"graph_depth": 3, "graph_edge_limit": 100}
        ret.vectors = {n: [] for n in ["seed", "consumer", "same_output", "same_input"]}
        ret.graph = {
            "seed": [["outputs", "table"], ["inputs", "array"]],
            "table": [
                ["is the input of", "consumer"],
                ["is the output of", "same_output"],
            ],
            "array": [["is the input of", "same_input"]],
        }
        self.assertEqual(ret.neighbors("seed"), {"consumer"})


if __name__ == "__main__":
    unittest.main()
