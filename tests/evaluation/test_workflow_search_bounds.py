"""Exact witness search must remain bounded on incomplete real evidence."""

import unittest
from evaluation.workflow import score_workflow


def independent_diagnostics(count=18):
    nodes, calls = [], []
    for i in range(count + 1):
        nodes.append(
            {
                "id": f"n{i}",
                "required": i == 0,
                "alternatives": [
                    {
                        "tools": [f"T{i}"],
                        "output_rules": [{"path": "/ok", "op": "eq", "value": True}],
                    }
                ],
            }
        )
        calls.append(
            {
                "observation_id": f"o{i}",
                "tool": f"T{i}",
                "arguments": {},
                "status": "success",
                "output": {"ok": i != 0},
            }
        )
    reference = {
        "evaluation": {
            "schema_version": "workflow.v1",
            "nodes": nodes,
            "outcomes": [
                {
                    "id": "answer",
                    "left": {"source": "answer", "path": "/x"},
                    "op": "eq",
                    "value": 1,
                    "evidence_nodes": ["n0"],
                }
            ],
        }
    }
    return reference, {"completed": True, "final_answer": {"x": 1}, "calls": calls}


class WorkflowSearchBoundsTest(unittest.TestCase):
    def test_repeated_ordering_parents_do_not_hide_impossible_literal_method(self):
        reference, prediction = independent_diagnostics(16)
        parents = [node["id"] for node in reference["evaluation"]["nodes"]]
        calls = []
        for call in prediction["calls"]:
            for repeat in range(2):
                calls.append({**call, "observation_id": call["observation_id"] + str(repeat),
                              "output": {"ok": True}})
        for method in ("observed", "absent"):
            reference["evaluation"]["nodes"].append({
                "id": method, "required": False, "depends_on": parents,
                "alternatives": [{"tools": ["Compute"], "output_rules": [
                    {"path": "/method", "op": "eq", "value": method}
                ]}],
            })
        reference["evaluation"]["capability_groups"] = [{
            "id": "method", "alternatives": [["observed"], ["absent"]]
        }]
        reference["evaluation"]["outcomes"][0]["evidence_groups"] = ["method"]
        calls.append({"observation_id": "computed", "tool": "Compute",
                      "arguments": {}, "status": "success",
                      "output": {"method": "observed"}})
        prediction["calls"] = calls
        score = score_workflow(reference, prediction, search_limit=100)
        self.assertTrue(score["joint_pass"])
        self.assertFalse(score["search_truncated"])
        self.assertEqual(score["matched_scientific_calls"], 18)

    def test_known_wrong_answer_does_not_enumerate_optional_subsets(self):
        reference, prediction = independent_diagnostics()
        prediction["calls"][0]["output"]["ok"] = True
        prediction["final_answer"]["x"] = 0
        score = score_workflow(reference, prediction, search_limit=100)
        self.assertFalse(score["joint_pass"])
        self.assertTrue(score["planning_pass"])
        self.assertFalse(score["search_truncated"])
        self.assertFalse(score["pending_review"])
        self.assertEqual(score["matched_scientific_calls"], 19)

    def test_unique_actual_source_can_bound_an_impossible_answer(self):
        reference, prediction = independent_diagnostics()
        prediction["calls"][0]["output"].update(ok=True, target=1)
        prediction["final_answer"]["x"] = 0
        outcome = reference["evaluation"]["outcomes"][0]
        outcome.pop("value")
        outcome["right"] = {"source": "node", "node": "n0", "path": "/target"}
        score = score_workflow(reference, prediction, search_limit=100)
        self.assertFalse(score["joint_pass"])
        self.assertFalse(score["search_truncated"])
        self.assertEqual(score["matched_scientific_calls"], 19)

    def test_ambiguous_source_is_not_replaced_by_first_candidate_for_answer_bound(self):
        reference, prediction = independent_diagnostics(0)
        prediction["calls"] = [
            {
                "observation_id": str(i),
                "tool": "T0",
                "arguments": {},
                "status": "success",
                "output": {"ok": True, "target": i},
            }
            for i in (1, 2)
        ]
        prediction["final_answer"]["x"] = 2
        outcome = reference["evaluation"]["outcomes"][0]
        outcome.pop("value")
        outcome["right"] = {"source": "node", "node": "n0", "path": "/target"}
        score = score_workflow(reference, prediction, search_limit=100)
        self.assertTrue(score["joint_pass"])
        self.assertEqual(score["nodes"][0]["observation_id"], "2")

    def test_ambiguous_branch_may_make_a_conditional_outcome_inactive(self):
        reference, prediction = independent_diagnostics(0)
        prediction["calls"] = [
            {
                "observation_id": str(i),
                "tool": "T0",
                "arguments": {},
                "status": "success",
                "output": {"ok": True, "active": active},
            }
            for i, active in enumerate((True, False))
        ]
        prediction["final_answer"]["x"] = 2
        reference["evaluation"]["outcomes"][0]["value"] = 2
        reference["evaluation"]["outcomes"].append(
            {
                "id": "conditional",
                "branch": "selected",
                "left": {"source": "answer", "path": "/x"},
                "op": "eq",
                "value": 1,
                "evidence_nodes": ["n0"],
            }
        )
        reference["evaluation"]["branches"] = [
            {
                "id": "selected",
                "when": {
                    "left": {"source": "node", "node": "n0", "path": "/active"},
                    "op": "eq",
                    "value": True,
                },
            }
        ]
        score = score_workflow(reference, prediction, search_limit=100)
        self.assertTrue(score["joint_pass"])
        self.assertEqual(score["nodes"][0]["observation_id"], "1")

    def test_duplicate_optional_routes_cannot_multiply_observation_capacity(self):
        reference, prediction = independent_diagnostics(16)
        nodes = reference["evaluation"]["nodes"]
        import copy

        for node in list(nodes[1:]):
            alternative = copy.deepcopy(node)
            alternative["id"] += "_equivalent"
            nodes.append(alternative)
        score = score_workflow(reference, prediction, search_limit=100)
        self.assertFalse(score["joint_pass"])
        self.assertFalse(score["search_truncated"])
        self.assertEqual(score["matched_scientific_calls"], 16)

    def test_all_calls_used_still_considers_higher_weight_alternative(self):
        reference, prediction = independent_diagnostics(0)
        import copy

        first = reference["evaluation"]["nodes"][0]
        first.update(required=False, weight=1)
        second = copy.deepcopy(first)
        second.update(id="higher", weight=3)
        reference["evaluation"]["nodes"].append(second)
        reference["evaluation"]["capability_groups"] = [
            {"id": "route", "alternatives": [["n0"], ["higher"]]}
        ]
        reference["evaluation"]["outcomes"][0].update(
            evidence_nodes=[], evidence_groups=["route"]
        )
        prediction["calls"][0]["output"]["ok"] = True
        score = score_workflow(reference, prediction)
        self.assertTrue(score["joint_pass"])
        self.assertEqual(score["matched_scientific_calls"], 1)
        self.assertEqual([n["id"] for n in score["nodes"] if n["matched"]], ["higher"])

    def test_missing_required_evidence_does_not_enumerate_optional_subsets(self):
        reference, prediction = independent_diagnostics()
        score = score_workflow(reference, prediction, search_limit=100)
        self.assertFalse(score["joint_pass"])
        self.assertFalse(score["search_truncated"])
        self.assertFalse(score["pending_review"])
        self.assertEqual(score["matched_scientific_calls"], 18)

    def test_bound_keeps_alternative_parent_observation_that_enables_child(self):
        reference, prediction = independent_diagnostics(1)
        parent = reference["evaluation"]["nodes"][0]
        parent["alternatives"][0]["output_rules"] = [
            {"path": "/key", "op": "type", "value": "number"}
        ]
        child = reference["evaluation"]["nodes"][1]
        child.update(
            required=True,
            depends_on=["n0"],
            bindings=[{"argument": "/key", "source_node": "n0", "output": "/key"}],
        )
        prediction["calls"] = [
            {
                "observation_id": "a",
                "tool": "T0",
                "status": "success",
                "arguments": {},
                "output": {"key": 1},
            },
            {
                "observation_id": "b",
                "tool": "T0",
                "status": "success",
                "arguments": {},
                "output": {"key": 2},
            },
            {
                "observation_id": "c",
                "tool": "T1",
                "status": "success",
                "arguments": {"key": 2},
                "output": {"ok": True},
            },
        ]
        score = score_workflow(reference, prediction, search_limit=100)
        self.assertTrue(score["joint_pass"])
        self.assertFalse(score["search_truncated"])
        self.assertEqual(score["nodes"][0]["observation_id"], "b")

    def test_missing_group_route_cannot_be_replaced_by_optional_weight(self):
        reference, prediction = independent_diagnostics(18)
        for node in reference["evaluation"]["nodes"]:
            node["required"] = False
        reference["evaluation"]["capability_groups"] = [
            {"id": "route", "alternatives": [["n0"], ["n1", "n2"]]}
        ]
        prediction["calls"][2]["output"]["ok"] = False
        score = score_workflow(reference, prediction, search_limit=100)
        self.assertFalse(score["joint_pass"])
        self.assertFalse(score["search_truncated"])
        self.assertEqual(score["matched_scientific_calls"], 17)
