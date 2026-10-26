"""Explicit reusable test controls; never benchmark gold values."""


def fixture():
    return {
        "id": "test-screen",
        "inputs": {"dataset": "known-v1", "needs_confirmation": False},
        "evaluation": {
            "schema_version": "workflow.v1",
            "nodes": [
                {
                    "id": "load",
                    "alternatives": [
                        {
                            "tools": ["ReadTable", "ReadJSON"],
                            "input_rules": [
                                {
                                    "path": "/dataset",
                                    "op": "eq",
                                    "right": {"source": "inputs", "path": "/dataset"},
                                }
                            ],
                            "output_rules": [
                                {"path": "/rows", "op": "type", "value": "array"}
                            ],
                        }
                    ],
                },
                {
                    "id": "audit",
                    "alternatives": [
                        {
                            "tools": ["AuditUnits"],
                            "input_rules": [],
                            "output_rules": [
                                {"path": "/consistent", "op": "eq", "value": True}
                            ],
                        }
                    ],
                },
                {
                    "id": "score",
                    "depends_on": ["load", "audit"],
                    "bindings": [
                        {"argument": "/rows", "source_node": "load", "output": "/rows"}
                    ],
                    "alternatives": [
                        {
                            "tools": ["ScoreCandidates", "EvaluateCandidates"],
                            "output_rules": [
                                {"path": "/ranking", "op": "type", "value": "array"}
                            ],
                        }
                    ],
                },
            ],
            "outcomes": [
                {
                    "id": "selection",
                    "left": {"source": "answer", "path": "/selected"},
                    "op": "set_equal",
                    "right": {
                        "operation": "argmax",
                        "args": [
                            {"source": "node", "node": "score", "path": "/ranking"}
                        ],
                        "value_path": "/score",
                        "id_path": "/id",
                        "tie_atol": 0.001,
                    },
                    "evidence_nodes": ["load", "audit", "score"],
                }
            ],
            "efficiency": {
                "free_recovery_calls": 1,
                "free_disambiguation_calls": 1,
                "disambiguation_tools": ["InspectSchema"],
            },
        },
    }


ROWS = [{"id": "a", "score": 1.0}, {"id": "b", "score": 2.0}]


def call(identifier, tool, arguments, output, status="success"):
    return {
        "observation_id": identifier,
        "tool": tool,
        "arguments": arguments,
        "output": output,
        "status": status,
    }


def run():
    return {
        "completed": True,
        "final_answer": {"selected": ["b"]},
        "calls": [
            call("o1", "ReadTable", {"dataset": "known-v1"}, {"rows": ROWS}),
            call("o2", "AuditUnits", {}, {"consistent": True}),
            call("o3", "ScoreCandidates", {"rows": ROWS}, {"ranking": ROWS}),
        ],
    }
