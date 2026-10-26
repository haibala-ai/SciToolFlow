"""Current experiment resources do not reuse historical per-task call quotas."""

import hashlib
import json
import pytest
import tests.evaluation.test_workflow_integration as controls

POLICY = {
    "version": "task-resources.v1",
    "max_model_requests": 400,
    "task_seconds": 7200,
}


@pytest.fixture
def case():
    c = controls.WorkflowIntegrationTest("test_real_trace_without_exact_reference_path")
    c.setUp()
    yield c
    c.doCleanups()


def install(c, count=1, usage=True):
    c.save_reference()
    c.trace["steps"][0]["model"] = {}
    if count > 1:
        c.trace["steps"] = [
            {"type": "think", "model": {}, "calls": []} for _ in range(count - 1)
        ] + c.trace["steps"]
    c.trace["limits"] = {
        "resource_policy": "task-resources.v1",
        "model_requests": 400,
        "task_seconds": 7200,
    }
    c.trace["resource_usage"] = {
        "policy_version": "task-resources.v1",
        "model_requests": count,
        "max_model_requests": 400,
        "task_seconds": 7200,
        "elapsed_seconds": 10,
        "requests": [
            {
                "request": i,
                "phase": "react",
                "status": "returned",
                "usage": (
                    {"prompt_tokens": 3, "completion_tokens": 2} if usage else None
                ),
            }
            for i in range(1, count + 1)
        ],
    }
    c.save_trace()
    c.save_predictions()
    c.envelope["settings"]["resource_policy"] = POLICY
    c.envelope["fingerprint"] = hashlib.sha256(
        json.dumps(c.envelope["settings"], sort_keys=True).encode()
    ).hexdigest()
    controls.write(c.root / "results/run/predictions.json", c.envelope)


def test_no_independent_scientific_call_quota(case):
    install(case)
    result = case.evaluate()
    assert result["results"][0]["joint_pass"]
    assert "budget_calls" not in result["results"][0]
    assert not result["results"][0]["resource_limit_exceeded"]
    assert (
        result["summary"]["evaluation_policy_version"]
        == "workflow.v1+task-resources.v1"
    )


def test_400_requests_can_pass_and_401_cannot(case):
    install(case, count=400)
    assert case.evaluate()["results"][0]["joint_pass"]


def test_consistent_but_over_limit_trace_cannot_pass(case):
    install(case, count=401)
    result = case.evaluate()
    assert (
        not result["results"][0]["joint_pass"]
        and result["results"][0]["resource_limit_exceeded"]
    )


def test_missing_or_mismatched_ledger_cannot_pass(case):
    install(case)
    case.trace["resource_usage"]["max_model_requests"] = 999
    case.save_trace()
    case.envelope["predictions"] = [case.prediction]
    controls.write(case.root / "results/run/predictions.json", case.envelope)
    result = case.evaluate()
    assert not result["results"][0]["joint_pass"]
    assert result["summary"]["resource_integrity_failures"] == 1


def test_missing_tokens_are_reported_unknown(case):
    install(case, usage=False)
    row = case.evaluate()["results"][0]
    assert row["joint_pass"] and row["resource_usage"]["prompt_tokens"] is None


@pytest.mark.parametrize("key", ["think_steps", "consecutive_thinks"])
def test_optional_think_limits_checked_from_actual_trace(case, key):
    install(case, count=4)
    case.trace["limits"][key] = 2
    case.save_trace()
    case.envelope["predictions"] = [case.prediction]
    case.envelope["settings"]["resource_policy"] = dict(POLICY, **{key: 2})
    case.envelope["fingerprint"] = hashlib.sha256(
        json.dumps(case.envelope["settings"], sort_keys=True).encode()
    ).hexdigest()
    controls.write(case.root / "results/run/predictions.json", case.envelope)
    result = case.evaluate()
    assert result["results"][0]["resource_limit_exceeded"]
    assert not result["results"][0]["joint_pass"]


def test_missing_resource_policy_is_rejected_without_legacy_fallback(case):
    install(case)
    case.envelope["settings"].pop("resource_policy")
    case.envelope["fingerprint"] = hashlib.sha256(
        json.dumps(case.envelope["settings"], sort_keys=True).encode()
    ).hexdigest()
    controls.write(case.root / "results/run/predictions.json", case.envelope)
    with pytest.raises(ValueError, match="Unsupported experiment resource policy"):
        case.evaluate()


def test_exact_deadline_is_not_a_valid_completed_submission(case):
    install(case)
    case.trace["resource_usage"]["elapsed_seconds"] = 7200
    case.save_trace()
    case.envelope["predictions"] = [case.prediction]
    controls.write(case.root / "results/run/predictions.json", case.envelope)
    row = case.evaluate()["results"][0]
    assert row["resource_limit_exceeded"] and not row["joint_pass"]


@pytest.mark.parametrize(
    "usage,expected_prompt,expected_completion",
    [({"prompt_tokens": 3}, 3, None), ({"completion_tokens": 2}, None, 2)],
)
def test_partially_known_token_usage_is_not_discarded(
    case, usage, expected_prompt, expected_completion
):
    install(case)
    case.trace["resource_usage"]["requests"][0]["usage"] = usage
    case.save_trace()
    case.envelope["predictions"] = [case.prediction]
    controls.write(case.root / "results/run/predictions.json", case.envelope)
    row = case.evaluate()["results"][0]
    assert row["joint_pass"]
    assert row["resource_usage"]["prompt_tokens"] == expected_prompt
    assert row["resource_usage"]["completion_tokens"] == expected_completion


@pytest.mark.parametrize("mutation", ["zero_requests", "boolean_ordinal"])
def test_completed_submission_requires_real_well_formed_generation_records(
    case, mutation
):
    install(case)
    if mutation == "zero_requests":
        case.trace["resource_usage"]["requests"] = []
        case.trace["resource_usage"]["model_requests"] = 0
        case.trace["steps"][0].pop("model")
    else:
        case.trace["resource_usage"]["requests"][0]["request"] = True
    case.save_trace()
    case.envelope["predictions"] = [case.prediction]
    controls.write(case.root / "results/run/predictions.json", case.envelope)
    result = case.evaluate()
    assert not result["results"][0]["joint_pass"]
    assert result["summary"]["resource_integrity_failures"] == 1
