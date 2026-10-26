"""Only actual matched prediction-input/label pairs establish metric provenance."""

import copy
import unittest

from evaluation.workflow import (
    MissingEvidence,
    operand,
    score_workflow,
    validate_workflow,
)


def literal(value):
    return {"value": value}


def select(source, path, node=None):
    return {"source": source, "path": path, **({"node": node} if node else {})}


def operation(name, *args):
    return {"operation": name, "args": list(args)}


def fixture():
    nodes = [
        {
            "id": "read",
            "alternatives": [
                {
                    "tools": ["Read"],
                    "output_rules": [
                        {"path": "/features", "op": "eq", "value": [[1], [2], [3]]}
                    ],
                }
            ],
        },
        {
            "id": "predict",
            "depends_on": ["read"],
            "alternatives": [
                {
                    "tools": ["Predict"],
                    "input_rules": [
                        {
                            "path": "/features",
                            "op": "multiset_equal",
                            "right": select("node", "/features", "read"),
                        }
                    ],
                    "output_rules": [
                        {"path": "/predictions", "op": "type", "value": "array"}
                    ],
                }
            ],
        },
        {
            "id": "metric",
            "depends_on": ["read", "predict"],
            "alternatives": [
                {
                    "tools": ["Metric"],
                    "input_rules": [
                        {
                            "path": "/predictions",
                            "op": "eq",
                            "right": select("node", "/predictions", "predict"),
                        },
                        {
                            "left": operation(
                                "paired_rows",
                                select("node_arguments", "/features", "predict"),
                                select("call_arguments", "/truth"),
                            ),
                            "op": "multiset_equal",
                            "right": operation(
                                "paired_rows",
                                select("node", "/features", "read"),
                                select("node", "/labels", "read"),
                            ),
                        },
                        {
                            "left": select("node_arguments", "/threshold", "predict"),
                            "op": "eq",
                            "value": 0.5,
                        },
                    ],
                    "output_rules": [{"path": "/accuracy", "op": "finite"}],
                }
            ],
        },
    ]
    reference = {
        "evaluation": {
            "schema_version": "workflow.v1",
            "nodes": nodes,
            "outcomes": [
                {
                    "id": "accuracy",
                    "left": select("answer", "/accuracy"),
                    "op": "eq",
                    "right": select("node", "/accuracy", "metric"),
                    "evidence_nodes": ["read", "predict", "metric"],
                }
            ],
        }
    }
    prediction = {
        "completed": True,
        "final_answer": {"accuracy": 1},
        "calls": [
            {
                "tool": "Read",
                "status": "success",
                "observation_id": "r",
                "arguments": {},
                "output": {"features": [[1], [2], [3]], "labels": [1, 0, 1]},
            },
            {
                "tool": "Predict",
                "status": "success",
                "observation_id": "p",
                "arguments": {"features": [[3], [1], [2]]},
                "output": {"predictions": [1, 1, 0]},
            },
            {
                "tool": "Metric",
                "status": "success",
                "observation_id": "m",
                "arguments": {"predictions": [1, 1, 0], "truth": [1, 1, 0]},
                "output": {"accuracy": 1},
            },
        ],
    }
    contracts = {
        "Predict": {
            "parameters": [
                {"name": "threshold", "required": False, "default_value": 0.5}
            ]
        }
    }
    return reference, prediction, contracts


class NodeArgumentTests(unittest.TestCase):
    def test_common_permutation_succeeds_but_same_label_marginals_do_not(self):
        reference, prediction, contracts = fixture()
        before = copy.deepcopy(prediction)
        self.assertTrue(
            score_workflow(reference, prediction, tool_contracts=contracts)[
                "joint_pass"
            ]
        )
        self.assertEqual(prediction, before)
        prediction["calls"][2]["arguments"]["truth"] = [1, 0, 1]
        prediction["calls"][2]["output"]["accuracy"] = 1 / 3
        prediction["final_answer"]["accuracy"] = 1 / 3
        self.assertFalse(
            score_workflow(reference, prediction, tool_contracts=contracts)[
                "planning_pass"
            ]
        )
        prediction["calls"][1]["_effective_arguments"] = {
            "features": [[1], [2], [3]],
            "threshold": 0.5,
        }
        self.assertFalse(
            score_workflow(reference, prediction, tool_contracts=contracts)[
                "planning_pass"
            ]
        )

    def test_missing_or_unmatched_arguments_are_not_invented(self):
        for context in [
            {},
            {"nodes": {"p": {"output": {}}}},
            {"nodes": {"p": {"arguments": {}}}},
        ]:
            with self.assertRaises(MissingEvidence):
                operand(select("node_arguments", "/features", "p"), context)
        self.assertEqual(
            operand(
                select("node_arguments", "/threshold", "p"),
                {"nodes": {"p": {"arguments": {"threshold": None}}}},
            ),
            None,
        )

    def test_argument_selectors_require_declared_known_prerequisites(self):
        reference, _, _ = fixture()
        validate_workflow(reference["evaluation"])
        reference["evaluation"]["nodes"][2]["depends_on"] = ["read"]
        with self.assertRaises(ValueError):
            validate_workflow(reference["evaluation"])
        reference, _, _ = fixture()
        reference["evaluation"]["nodes"][2]["alternatives"][0]["input_rules"][2][
            "left"
        ]["node"] = "unknown"
        with self.assertRaises(ValueError):
            validate_workflow(reference["evaluation"])
