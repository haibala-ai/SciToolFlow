"""Equivalent one-call and multi-call scientific methods require real evidence."""

import copy
import unittest

from evaluation.workflow import (
    score_workflow,
    validate_workflow,
    public_answer_contract,
)
from tests.support.workflows import call


def fixture():
    nodes = [
        {
            "id": "source",
            "alternatives": [
                {
                    "tools": ["Read"],
                    "output_rules": [{"path": "/known", "op": "eq", "value": True}],
                }
            ],
        }
    ]
    for name, curve, result in [
        ("net", "difference", -10),
        ("gas", "gas", 20),
        ("liquid", "liquid", 30),
    ]:
        nodes.append(
            {
                "id": name,
                "required": False,
                "depends_on": ["source"],
                "alternatives": [
                    {
                        "tools": ["Integrate"],
                        "input_rules": [{"path": "/curve", "op": "eq", "value": curve}],
                        "output_rules": [
                            {"path": "/integral", "op": "eq", "value": result}
                        ],
                    }
                ],
            }
        )
    return {
        "id": "two-valid-methods",
        "evaluation": {
            "schema_version": "workflow.v1",
            "nodes": nodes,
            "capability_groups": [
                {"id": "correction", "alternatives": [["net"], ["gas", "liquid"]]}
            ],
            "outcomes": [
                {
                    "id": "enthalpy",
                    "left": {"source": "answer", "path": "/correction"},
                    "op": "eq",
                    "value": -10,
                    "evidence_nodes": ["source"],
                    "evidence_groups": ["correction"],
                }
            ],
        },
    }


def prediction(*curves, answer=-10):
    results = {"difference": -10, "gas": 20, "liquid": 30}
    calls = [call("o0", "Read", {}, {"known": True})]
    calls += [
        call(f"o{i+1}", "Integrate", {"curve": curve}, {"integral": results[curve]})
        for i, curve in enumerate(curves)
    ]
    return {"completed": True, "calls": calls, "final_answer": {"correction": answer}}


class EquivalentMethodsTest(unittest.TestCase):
    def test_public_inputs_do_not_need_a_fake_common_reader(self):
        reference = fixture()
        spec = reference["evaluation"]
        spec["nodes"] = spec["nodes"][1:]
        for node in spec["nodes"]:
            node.pop("depends_on")
        spec["outcomes"][0]["evidence_nodes"] = []
        for route in [("difference",), ("gas", "liquid")]:
            pred = prediction(*route)
            pred["calls"] = pred["calls"][1:]
            self.assertTrue(score_workflow(reference, pred)["joint_pass"])
        spec["outcomes"][0].pop("evidence_groups")
        with self.assertRaises(ValueError):
            validate_workflow(spec)

    def test_either_complete_method_has_full_credit(self):
        for route in [("difference",), ("gas", "liquid"), ("liquid", "gas")]:
            with self.subTest(route=route):
                result = score_workflow(fixture(), prediction(*route))
                self.assertTrue(result["joint_pass"])
                self.assertEqual(result["orchestration_credit"], 1)
                self.assertFalse(result["pending_review"])

    def test_one_phase_or_duplicate_phase_cannot_supply_other_phase(self):
        for route in [(), ("gas",), ("gas", "gas"), ("liquid", "liquid")]:
            with self.subTest(route=route):
                result = score_workflow(fixture(), prediction(*route))
                self.assertFalse(result["planning_pass"])
                self.assertFalse(result["answer_pass"])
                self.assertEqual(result["answer_only_credit"], 1)

    def test_wrong_answer_does_not_erase_valid_orchestration(self):
        result = score_workflow(fixture(), prediction("liquid", "gas", answer=10))
        self.assertTrue(result["planning_pass"])
        self.assertFalse(result["answer_pass"])

    def test_optional_diagnostic_omission_is_not_a_capability_failure(self):
        reference = fixture()
        reference["evaluation"]["nodes"].append(
            {
                "id": "optional_audit",
                "required": False,
                "depends_on": ["source"],
                "alternatives": [
                    {
                        "tools": ["Audit"],
                        "output_rules": [{"path": "/ok", "op": "eq", "value": True}],
                    }
                ],
            }
        )
        result = score_workflow(reference, prediction("difference"))
        self.assertTrue(result["joint_pass"])
        self.assertEqual(result["orchestration_credit"], 1)

    def test_already_executed_optional_diagnostics_are_not_discarded(self):
        reference = fixture()
        reference["evaluation"]["nodes"].append(
            {
                "id": "optional_audit",
                "required": False,
                "depends_on": ["net"],
                "alternatives": [
                    {
                        "tools": ["Audit"],
                        "output_rules": [{"path": "/ok", "op": "eq", "value": True}],
                    }
                ],
            }
        )
        pred = prediction("difference")
        pred["calls"].append(call("o2", "Audit", {}, {"ok": True}))
        result = score_workflow(reference, pred)
        self.assertTrue(result["joint_pass"])
        self.assertTrue(
            next(n for n in result["nodes"] if n["id"] == "optional_audit")["matched"]
        )
        self.assertEqual(result["selection_efficiency"], 1)

    def test_actual_prerequisite_must_precede_integrals(self):
        pred = prediction("gas", "liquid")
        pred["calls"] = pred["calls"][1:] + pred["calls"][:1]
        self.assertFalse(score_workflow(fixture(), pred)["joint_pass"])

    def test_equivalent_shared_observation_keeps_valid_downstream_work(self):
        reference = fixture()
        source, direct = reference["evaluation"]["nodes"][:2]
        direct["id"] = "direct"
        preparation = {
            "id": "preparation",
            "required": False,
            "depends_on": ["source"],
            "alternatives": [
                {
                    "tools": ["Prepare"],
                    "output_rules": [{"path": "/ok", "op": "eq", "value": True}],
                }
            ],
        }
        wrapped = copy.deepcopy(direct)
        wrapped.update(id="wrapped", depends_on=["preparation"])
        diagnostic = {
            "id": "diagnostic",
            "required": False,
            "depends_on": ["wrapped"],
            "alternatives": [
                {
                    "tools": ["Audit"],
                    "output_rules": [{"path": "/ok", "op": "eq", "value": True}],
                }
            ],
        }
        spec = reference["evaluation"]
        spec["nodes"] = [source, direct, preparation, wrapped, diagnostic]
        spec["capability_groups"] = [
            {
                "id": "correction",
                "alternatives": [["direct"], ["preparation", "wrapped"]],
            }
        ]
        pred = prediction("difference")
        pred["calls"].insert(1, call("prepare", "Prepare", {}, {"ok": True}))
        pred["calls"].append(call("audit", "Audit", {}, {"ok": True}))
        result = score_workflow(reference, pred)
        self.assertTrue(result["joint_pass"])
        self.assertFalse(result["search_truncated"])
        self.assertEqual(result["selection_efficiency"], 1)
        self.assertTrue(
            next(n for n in result["nodes"] if n["id"] == "diagnostic")["matched"]
        )
        # The direct one-call solution is independently valid and needs neither
        # preparation nor the optional downstream diagnostic.
        self.assertTrue(
            score_workflow(reference, prediction("difference"))["joint_pass"]
        )

    def test_shared_tool_call_cannot_count_twice(self):
        reference = fixture()
        # Two operations with identical admissible signatures still require two
        # actual dispatches when a scientific route declares two operations.
        reference["evaluation"]["nodes"][3]["alternatives"] = copy.deepcopy(
            reference["evaluation"]["nodes"][2]["alternatives"]
        )
        self.assertFalse(score_workflow(reference, prediction("gas"))["joint_pass"])
        self.assertTrue(
            score_workflow(reference, prediction("gas", "gas"))["joint_pass"]
        )

    def test_invalid_groups_rejected_and_public_format_has_no_routes(self):
        reference = fixture()
        for alternatives in [[], [[]], [["unknown"]], [["gas", "gas"]]]:
            bad = copy.deepcopy(reference["evaluation"])
            bad["capability_groups"][0]["alternatives"] = alternatives
            with self.subTest(alternatives=alternatives), self.assertRaises(ValueError):
                validate_workflow(bad)
        bad = copy.deepcopy(reference["evaluation"])
        bad["outcomes"][0]["evidence_groups"] = ["nonexistent"]
        with self.assertRaises(ValueError):
            validate_workflow(bad)
        self.assertNotIn("gas", str(public_answer_contract(reference)))


if __name__ == "__main__":
    unittest.main()
