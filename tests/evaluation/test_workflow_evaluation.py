"""Scientific evidence, alternative routes and failure boundaries for workflow.v1."""

from tests.support.workflows import fixture, ROWS, call, run

import copy
import unittest

from evaluation.workflow import (
    score_workflow,
    validate_workflow,
    predicate,
    pointer,
    public_answer_contract,
    evaluate_workflows,
    MissingEvidence,
)


class WorkflowScoringTest(unittest.TestCase):
    def test_valid_alternative_and_independent_reorder(self):
        prediction = run()
        prediction["calls"][0]["tool"] = "ReadJSON"
        prediction["calls"][2]["tool"] = "EvaluateCandidates"
        prediction["calls"][:2] = list(reversed(prediction["calls"][:2]))
        prediction["calls"].insert(
            0, {"tool": "DescribeTools", "arguments": {"names": ["ReadJSON"]}}
        )
        result = score_workflow(fixture(), prediction)
        self.assertTrue(result["joint_pass"])
        self.assertEqual(result["selection_efficiency"], 1)
        self.assertEqual(result["scientific_calls"], 3)

    def test_broken_dataflow_and_wrong_dataset_are_not_evidence(self):
        for mutate in (
            lambda p: p["calls"][2]["arguments"].update(rows=[{"id": "invented"}]),
            lambda p: p["calls"][0]["arguments"].update(dataset="wrong"),
        ):
            prediction = run()
            mutate(prediction)
            result = score_workflow(fixture(), prediction)
            self.assertFalse(result["planning_pass"])
            self.assertFalse(result["answer_pass"])
            self.assertLess(result["orchestration_credit"], 1)

    def test_answer_cannot_substitute_for_missing_observations(self):
        prediction = run()
        prediction["calls"] = []
        result = score_workflow(fixture(), prediction)
        self.assertFalse(result["joint_pass"])
        self.assertEqual(result["scientific_credit"], 0)

    def test_reordering_actual_dependency_fails(self):
        prediction = run()
        prediction["calls"] = prediction["calls"][2:] + prediction["calls"][:2]
        self.assertFalse(score_workflow(fixture(), prediction)["planning_pass"])

    def test_duplicate_calls_lower_efficiency_without_erasing_science(self):
        prediction = run()
        duplicate = copy.deepcopy(prediction["calls"][-1])
        duplicate["observation_id"] = "duplicate"
        prediction["calls"].append(duplicate)
        result = score_workflow(fixture(), prediction)
        self.assertTrue(result["joint_pass"])
        self.assertEqual(result["redundant_calls"], 1)
        self.assertEqual(result["selection_efficiency"], 0.75)

    def test_necessary_recovery_and_bounded_exploration_not_penalized(self):
        prediction = run()
        prediction["calls"].insert(
            0, call("fail", "ReadTable", {"dataset": "known-v0"}, None, "error")
        )
        prediction["calls"].insert(
            1, call("inspect", "InspectSchema", {}, {"kind": "candidate_table"})
        )
        self.assertEqual(
            score_workflow(fixture(), prediction)["selection_efficiency"], 1
        )

    def test_conditionals_are_not_always_required(self):
        ref = fixture()
        ref["evaluation"]["branches"] = [
            {
                "id": "confirm",
                "when": {
                    "left": {"source": "inputs", "path": "/needs_confirmation"},
                    "op": "eq",
                    "value": True,
                },
            }
        ]
        ref["evaluation"]["nodes"].append(
            {
                "id": "confirm",
                "branch": "confirm",
                "depends_on": ["score"],
                "alternatives": [
                    {
                        "tools": ["ConfirmSelection"],
                        "output_rules": [
                            {"path": "/verified", "op": "eq", "value": True}
                        ],
                    }
                ],
            }
        )
        self.assertTrue(score_workflow(ref, run())["joint_pass"])
        ref["inputs"]["needs_confirmation"] = True
        self.assertFalse(score_workflow(ref, run())["planning_pass"])
        prediction = run()
        prediction["calls"].append(
            call("confirm", "ConfirmSelection", {}, {"verified": True})
        )
        self.assertTrue(score_workflow(ref, prediction)["joint_pass"])

    def test_missing_branch_evidence_is_pending_not_ignored(self):
        ref = fixture()
        ref["evaluation"]["branches"] = [
            {
                "id": "confirm",
                "when": {
                    "left": {"source": "inputs", "path": "/unknown_condition"},
                    "op": "eq",
                    "value": True,
                },
            }
        ]
        ref["evaluation"]["nodes"][-1]["branch"] = "confirm"
        result = score_workflow(ref, run())
        self.assertTrue(result["pending_review"])
        self.assertFalse(result["joint_pass"])

    def test_ties_and_format_do_not_expose_one_arbitrary_gold(self):
        prediction = run()
        rows = copy.deepcopy(ROWS)
        rows[0]["score"] = 1.9995
        prediction["calls"][-1]["output"]["ranking"] = rows
        prediction["final_answer"] = '```json\n{"selected": ["b", "a"]}\n```'
        self.assertTrue(score_workflow(fixture(), prediction)["joint_pass"])
        prediction["final_answer"] = {"selected": ["b"]}
        self.assertFalse(score_workflow(fixture(), prediction)["answer_pass"])

    def test_correct_answer_does_not_hide_runtime_failure(self):
        prediction = run()
        prediction["completed"] = False
        prediction["failure_reason"] = "timeout"
        result = score_workflow(fixture(), prediction)
        self.assertTrue(result["answer_pass"])
        self.assertFalse(result["joint_pass"])

    def test_invalid_input_can_require_evidenced_abstention(self):
        ref = {
            "id": "invalid",
            "inputs": {"value": -1},
            "evaluation": {
                "schema_version": "workflow.v1",
                "nodes": [
                    {
                        "id": "validate",
                        "alternatives": [
                            {
                                "tools": ["ValidateDomain"],
                                "statuses": ["error"],
                                "input_rules": [
                                    {
                                        "path": "/value",
                                        "op": "eq",
                                        "right": {"source": "inputs", "path": "/value"},
                                    }
                                ],
                                "output_rules": [
                                    {
                                        "path": "/code",
                                        "op": "eq",
                                        "value": "out_of_domain",
                                    }
                                ],
                            }
                        ],
                    }
                ],
                "outcomes": [
                    {
                        "id": "abstention",
                        "left": {"source": "answer", "path": "/disposition"},
                        "op": "eq",
                        "value": "invalid_input",
                        "evidence_nodes": ["validate"],
                    }
                ],
            },
        }
        prediction = {
            "completed": True,
            "final_answer": {"disposition": "invalid_input"},
            "calls": [
                call(
                    "v",
                    "ValidateDomain",
                    {"value": -1},
                    {"code": "out_of_domain"},
                    "error",
                )
            ],
        }
        self.assertTrue(score_workflow(ref, prediction)["joint_pass"])
        prediction["final_answer"]["disposition"] = "answered"
        self.assertFalse(score_workflow(ref, prediction)["answer_pass"])

    def test_schema_and_trace_fail_closed(self):
        for mutation in (
            lambda s: s.update(nodes=[]),
            lambda s: s["nodes"][0].update(depends_on=["score"]),
            lambda s: s["outcomes"][0].update(evidence_nodes=[]),
            lambda s: s["outcomes"][0].update(
                right={"source": "answer", "path": "/selected"}
            ),
        ):
            spec = fixture()["evaluation"]
            mutation(spec)
            with self.assertRaises(ValueError):
                validate_workflow(spec)
        prediction = run()
        prediction["calls"][-1]["observation_id"] = "o1"
        with self.assertRaises(ValueError):
            score_workflow(fixture(), prediction)

    def test_array_semantics_and_numeric_types(self):
        self.assertFalse(predicate({"op": "eq", "value": [2, 1]}, {}, [1, 2]))
        self.assertTrue(predicate({"op": "set_equal", "value": [2, 1, 1]}, {}, [1, 2]))
        self.assertFalse(
            predicate({"op": "multiset_equal", "value": [2, 1, 1]}, {}, [1, 2])
        )
        self.assertFalse(predicate({"op": "eq", "value": 1}, {}, True))
        self.assertFalse(predicate({"op": "finite"}, {}, float("nan")))
        self.assertEqual(pointer({"a/b": {"~x": 2}}, "/a~1b/~0x"), 2)

    def test_exhausted_search_is_explicit(self):
        result = score_workflow(fixture(), run(), search_limit=1)
        self.assertTrue(result["search_truncated"])
        self.assertTrue(result["pending_review"])
        self.assertFalse(result["joint_pass"])

    def test_public_contract_and_batch_denominator(self):
        contract = public_answer_contract(fixture())
        self.assertEqual(contract[0]["fields"], ["/selected"])
        self.assertNotIn("right", contract[0])
        self.assertNotIn("evidence_nodes", contract[0])
        other = copy.deepcopy(fixture())
        other["id"] = "missing"
        prediction = run()
        prediction["id"] = "test-screen"
        result = evaluate_workflows(
            [fixture(), other],
            [prediction],
            catalog_tools=[
                "ReadTable",
                "AuditUnits",
                "ScoreCandidates",
                "UnusedTool",
                "DescribeTools",
            ],
        )
        self.assertEqual(result["summary"]["joint_pass_rate"], 0.5)
        self.assertEqual(result["summary"]["missing_predictions"], 1)
        self.assertEqual(result["coverage_diagnostics"]["catalog_tool_coverage"], 0.75)
        self.assertFalse(
            result["coverage_diagnostics"]["coverage_affects_scientific_score"]
        )

    def test_pointer_strictness_and_additive_tolerance(self):
        for path in ("/-1", "/01", "/1.0", "/+1"):
            with self.assertRaises(MissingEvidence):
                pointer([1, 2], path)
        for path in ("/~", "/~2"):
            with self.assertRaises(ValueError):
                pointer({}, path)
        self.assertTrue(
            predicate(
                {"op": "eq", "value": 100.0, "atol": 1.0, "rtol": 0.01}, {}, 101.5
            )
        )
        self.assertFalse(predicate({"op": "finite"}, {}, 10**1000))
        self.assertFalse(
            predicate({"op": "eq", "value": float("inf")}, {}, float("inf"))
        )

    def test_valid_later_observation_is_not_lost_to_greedy_mapping(self):
        prediction = run()
        first = copy.deepcopy(prediction["calls"][-1])
        first["observation_id"] = "different-ranking"
        first["output"] = {
            "ranking": [{"id": "a", "score": 10}, {"id": "b", "score": 2}]
        }
        prediction["calls"].insert(2, first)
        result = score_workflow(fixture(), prediction)
        self.assertTrue(result["joint_pass"])
        self.assertEqual(result["nodes"][-1]["observation_id"], "o3")

    def test_irrelevant_tool_does_not_get_free_disambiguation_credit(self):
        prediction = run()
        prediction["calls"].insert(0, call("irrelevant", "UnrelatedTool", {}, {"x": 1}))
        self.assertEqual(
            score_workflow(fixture(), prediction)["selection_efficiency"], 0.75
        )


if __name__ == "__main__":
    unittest.main()
