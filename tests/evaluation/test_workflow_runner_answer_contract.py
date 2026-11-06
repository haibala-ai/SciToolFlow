"""Formatting diagnostics must not override independent execution/science metrics."""

import copy
import pytest
import evaluation.runner as runner
import evaluation.integrity.traces as integrity


@pytest.mark.parametrize("dataset", ["full", "mini"])
@pytest.mark.parametrize("extra,expected", [(False, True), (True, True)])
def test_scoring_separates_unknown_fields_from_scientific_correctness(
    monkeypatch, tmp_path, extra, expected, dataset
):
    registry = {"tools": {"Measure": {"parameters": []}}, "aliases": {}}

    class Catalog:
        def __init__(self, root):
            self.tools = registry["tools"]

        def registry(self):
            return registry

    monkeypatch.setattr(runner, "ToolCatalog", Catalog)
    monkeypatch.setattr(
        integrity,
        "authenticate_prediction",
        lambda row, *args, dataset="full": (copy.deepcopy(row), {"verified": True}),
    )
    monkeypatch.setattr(
        runner, "check_resources", lambda *args: {"verified": True, "exceeded": False}
    )
    reference = {
        "id": "t1",
        "question": "Report the measurement",
        "inputs": {},
        "answer_contract": {
            "type": "object",
            "properties": {"result": {"type": "number"}},
            "required": ["result"],
            "additionalProperties": False,
        },
        "evaluation": {
            "schema_version": "workflow.v1",
            "nodes": [
                {
                    "id": "measurement",
                    "alternatives": [
                        {
                            "tools": ["Measure"],
                            "output_rules": [
                                {"path": "/value", "op": "eq", "value": 2}
                            ],
                        }
                    ],
                }
            ],
            "outcomes": [
                {
                    "id": "result",
                    "left": {"source": "answer", "path": "/result"},
                    "op": "eq",
                    "value": 2,
                    "evidence_nodes": ["measurement"],
                }
            ],
        },
    }
    prediction = {
        "id": "t1",
        "dataset": dataset,
        "completed": True,
        "status": "completed",
        "final_answer": {"result": 2},
        "calls": [
            {
                "tool": "Measure",
                "arguments": {},
                "status": "success",
                "output": {"value": 2},
                "observation_id": "o001",
            }
        ],
    }
    if extra:
        prediction["final_answer"]["unsupported_claim"] = True
    import evaluation.suites.reference_context as contexts
    monkeypatch.setattr(contexts, "prediction_from_reference", lambda *args: copy.deepcopy(prediction))
    result = runner._evaluate_workflow_package(
        tmp_path,
        [reference],
        [prediction],
        tmp_path / "scores.json",
        tmp_path,
        None,
        "test-fingerprint",
        dataset=dataset,
        execution_policy={
            "version": "task-resources.v1",
            "max_model_requests": 400,
            "task_seconds": 7200,
        },
    )["results"][0]
    assert result["joint_pass"] is expected
    assert result["planning_pass"] is True
    assert result["answer_pass"] is expected
    assert result["scientific_fields_pass"] is True
    assert bool(result["answer_contract_errors"]) is extra
    assert result["runtime_pass"] is True
    assert result["answer_schema_valid"] is (not extra)
