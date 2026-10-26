"""Coverage reports must not mistake draft plans for executed evidence."""

import unittest

from scripts.references.audit_workflow_design import analyze
from scripts.references.audit_cross_task_patterns import inspect_task


class DesignAuditTests(unittest.TestCase):
    def fixture(self):
        catalog = {
            "tools": {
                "Calculate": {"kind": "scientific", "domain": "MachineLearning"},
                "Unused": {"kind": "scientific", "domain": "MachineLearning"},
                "DescribeTools": {"kind": "discovery", "domain": "General"},
            }
        }
        public = {
            "FLOW-0001": {
                "id": "FLOW-0001",
                "domain": "MachineLearning",
                "question": "Assess whether 10 units are supportable.",
            },
            "FLOW-0002": {
                "id": "FLOW-0002",
                "domain": "MachineLearning",
                "question": "Assess whether 20 units are supportable.",
            },
        }
        hidden = {
            key: {
                "id": key,
                "family_id": "capacity",
                "evaluation": {
                    "nodes": [
                        {
                            "id": "measurement",
                            "alternatives": [{"tools": ["Calculate"]}],
                        }
                    ]
                },
            }
            for key in public
        }
        return public, hidden, catalog

    def test_proposed_alternative_never_counts_as_verified(self):
        report = analyze(*self.fixture())
        counts = report["coverage_by_tool_discipline"]["MachineLearning"]
        self.assertEqual(counts["registered_scientific_tools"], 2)
        self.assertEqual(counts["proposed_alternative_tools"], 1)
        self.assertEqual(counts["verified_native_reference_tools"], 0)
        self.assertNotIn("DescribeTools", report["tools"])

    def test_numeric_substitution_signals_manual_duplicate_review(self):
        report = analyze(*self.fixture())
        self.assertEqual(len(report["potential_duplicate_pairs"]), 1)
        pair = report["potential_duplicate_pairs"][0]
        self.assertEqual(pair["question_shape_similarity"], 1)
        self.assertIn("not_automatic_rejection", pair["status"])
        self.assertTrue(
            any(
                i["issue"] == "no_declared_observation_to_argument_handoff"
                for i in report["design_issues"]
            )
        )

    def test_late_route_edits_cannot_leave_a_stale_tool_inventory_unnoticed(self):
        public, hidden, catalog = self.fixture()
        hidden["FLOW-0001"]["capability_coverage"] = ["removed-tool"]
        report = analyze(public, hidden, catalog)
        issues = [
            r
            for r in report["design_issues"]
            if r["issue"] == "stale_derived_tool_inventory"
        ]
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["task_id"], "FLOW-0001")
        self.assertNotIn("removed-tool", issues[0]["current_workflow_tools"])

    def test_unverified_review_label_cannot_inflate_coverage(self):
        report = analyze(
            *self.fixture(),
            references={"FLOW-0001": {"review": {"status": "approved"}}},
        )
        self.assertEqual(len(report["reference_validation_issues"]), 1)
        self.assertEqual(
            report["coverage_by_tool_discipline"]["MachineLearning"][
                "verified_coverage_fraction"
            ],
            0,
        )

    def test_scoped_argument_rule_is_a_real_handoff(self):
        public, hidden, catalog = self.fixture()
        for spec in hidden.values():
            spec["evaluation"]["nodes"][0]["alternatives"][0]["input_rules"] = [
                {
                    "path": "/matrix",
                    "op": "eq",
                    "right": {
                        "operation": "record_value",
                        "args": [
                            {"source": "node", "node": "read", "path": "/records"}
                        ],
                    },
                }
            ]
        report = analyze(public, hidden, catalog)
        self.assertFalse(
            any(
                row["issue"] == "no_declared_observation_to_argument_handoff"
                for row in report["design_issues"]
            )
        )

    def test_dependency_or_output_only_rule_does_not_prove_argument_handoff(self):
        public, hidden, catalog = self.fixture()
        for spec in hidden.values():
            node = spec["evaluation"]["nodes"][0]
            node["depends_on"] = ["read"]
            node["alternatives"][0]["output_rules"] = [
                {
                    "path": "/result",
                    "op": "eq",
                    "right": {"source": "node", "node": "read"},
                }
            ]
        report = analyze(public, hidden, catalog)
        self.assertEqual(
            sum(
                row["issue"] == "no_declared_observation_to_argument_handoff"
                for row in report["design_issues"]
            ),
            2,
        )


class OptionalEvidenceAuditTests(unittest.TestCase):
    def fixture(self):
        public = {"question": "Estimate the finite-population mean.", "files": []}
        hidden = {
            "evaluation": {
                "nodes": [
                    {"id": "source", "alternatives": [{"tools": ["Read"]}]},
                    {
                        "id": "helper",
                        "required": False,
                        "alternatives": [{"tools": ["Prepare"]}],
                    },
                ],
                "outcomes": [{"id": "mean", "evidence_nodes": ["source", "helper"]}],
            }
        }
        return public, hidden

    def test_optional_direct_dependency_is_a_related_review_candidate(self):
        public, hidden = self.fixture()
        findings = [
            v
            for v in inspect_task(public, hidden)
            if v["pattern"] == "optional_node_required_by_outcome"
        ]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["detail"]["optional_nodes"], ["helper"])
        self.assertEqual(
            findings[0]["status"], "related_candidate_not_a_confirmed_defect"
        )

    def test_alternative_group_is_not_a_blanket_optional_dependency_defect(self):
        public, hidden = self.fixture()
        hidden["evaluation"]["outcomes"][0]["evidence_nodes"] = ["source"]
        hidden["evaluation"]["outcomes"][0]["evidence_groups"] = ["method"]
        hidden["evaluation"]["capability_groups"] = [
            {"id": "method", "alternatives": [["helper"]]}
        ]
        self.assertFalse(
            any(
                v["pattern"] == "optional_node_required_by_outcome"
                for v in inspect_task(public, hidden)
            )
        )


if __name__ == "__main__":
    unittest.main()
