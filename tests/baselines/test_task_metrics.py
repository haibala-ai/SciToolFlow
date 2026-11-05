"""Honest task cost accounting, including partial usage and dispatcher failures."""

import json

import pytest

from baselines.common.metrics import task_metrics
from baselines.common.resources import TaskResources


def test_roles_and_failed_attempts_share_one_token_and_call_total():
    resources = TaskResources(clock=lambda: 10)
    resources.requests = [
        {
            "phase": "planner",
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 40,
                "prompt_tokens_details": {"cached_tokens": 80},
                "completion_tokens_details": {"reasoning_tokens": 30},
            },
        },
        {"phase": "reviewer", "usage": {"prompt_tokens": 60, "completion_tokens": 20}},
    ]
    metrics = task_metrics(
        resources.snapshot(),
        [
            {"tool": "DescribeTools", "status": "success"},
            {"tool": "MatrixInverse", "status": "error"},
            {"tool": "MatrixInverse", "status": "success"},
        ],
        runtime_seconds=4.5,
        finished=True,
    )
    assert metrics["runtime_seconds"] == 4.5
    assert metrics["tool_calls"] == 3
    assert metrics["scientific_tool_calls"] == 2
    assert metrics["discovery_tool_calls"] == 1
    assert metrics["input_tokens"] == 160
    assert metrics["output_tokens"] == 60
    assert metrics["total_tokens"] == 220  # Cached/reasoning are already subsets.
    assert metrics["token_usage_complete"] and metrics["tool_calls_complete"]


@pytest.mark.parametrize("missing", ["prompt_tokens", "completion_tokens"])
def test_partial_usage_preserves_known_side_and_observed_subtotals(missing):
    resources = TaskResources(clock=lambda: 10)
    usage = {"prompt_tokens": 15, "completion_tokens": 7}
    usage.pop(missing)
    resources.requests = [
        {"usage": {"prompt_tokens": 20, "completion_tokens": 10}},
        {"status": "error", "usage": usage},
    ]
    metrics = task_metrics(resources.snapshot(), [], finished=True)
    assert not metrics["token_usage_complete"]
    assert metrics["total_tokens"] is None
    if missing == "prompt_tokens":
        assert metrics["input_tokens"] is None and metrics["output_tokens"] == 17
        assert metrics["observed_input_tokens"] == 20
        assert metrics["requests_missing_input_usage"] == 1
    else:
        assert metrics["input_tokens"] == 35 and metrics["output_tokens"] is None
        assert metrics["observed_output_tokens"] == 10
        assert metrics["requests_missing_output_usage"] == 1


def test_no_requests_is_zero_but_missing_ledger_is_unknown():
    zero = task_metrics(TaskResources(clock=lambda: 1).snapshot(), [], finished=True)
    assert zero["input_tokens"] == zero["output_tokens"] == zero["tool_calls"] == 0
    assert zero["token_usage_complete"]
    unknown = task_metrics(None, None)
    assert unknown["runtime_seconds"] is unknown["input_tokens"] is None
    assert unknown["output_tokens"] is unknown["tool_calls"] is None
    assert not unknown["token_usage_complete"] and not unknown["tool_calls_complete"]


def test_running_checkpoint_counts_inflight_calls_once():
    usage = TaskResources(clock=lambda: 1).snapshot()
    running = task_metrics(
        usage, [{"tool": "DescribeTools"}], pending_calls=[{"tool": "MatrixInverse"}]
    )
    final = task_metrics(
        usage, [{"tool": "DescribeTools"}, {"tool": "MatrixInverse"}], finished=True
    )
    assert running["tool_calls"] == final["tool_calls"] == 2
    assert not running["tool_calls_complete"] and final["tool_calls_complete"]


def test_scimas_persists_costs_on_success_and_timeout(tmp_path):
    from tests.scimas.test_runtime import run, Client

    result = run(tmp_path / "success", Client())
    metrics = result["metrics"]
    assert result["status"] == "completed"
    assert metrics["input_tokens"] == metrics["model_requests"] * 10
    assert metrics["output_tokens"] == metrics["model_requests"] * 5
    assert metrics["tool_calls"] == len(result["calls"]) == 2
    assert metrics["runtime_seconds"] == result["duration_seconds"]
    assert json.loads(open(result["trace_path"]).read())["metrics"] == metrics

    def timeout(payload, action):
        if payload.get("context", {}).get("stage") == "result":
            raise TimeoutError("Simulated read timeout")
        return action

    failed = run(tmp_path / "failure", Client(timeout))
    metrics = failed["metrics"]
    assert failed["status"] == "failed"
    assert metrics["runtime_seconds"] > 0
    assert metrics["tool_calls"] == len(failed["calls"]) == 1
    assert metrics["input_tokens"] is metrics["output_tokens"] is None
    assert metrics["observed_input_tokens"] > 0
    assert metrics["requests_missing_input_usage"] == 1
    assert json.loads(open(failed["trace_path"]).read())["metrics"] == metrics


def test_batch_writes_one_metric_row_per_attempt_and_resume_does_not_double_count(
    tmp_path, monkeypatch
):
    from argparse import Namespace
    from tests.integration.test_mini_dataset import options
    from baselines.react import runner

    args = Namespace(**options(monkeypatch, tmp_path))
    args.baseline = "scimas"
    args.resume = args.retry_failed = False

    class Client:
        backend = "api"
        model = "offline-test"

        def __init__(self, *a, **kw):
            pass

        def public_settings(self):
            return {"endpoint": "http://localhost/offline-test"}

        def close(self):
            pass

    batches = []

    def offline_jobs(jobs, function, concurrency, on_active):
        batches.append(len(jobs))
        for task_id, _ in jobs:
            ledger = TaskResources(clock=lambda: 1)
            ledger.requests = [{"usage": {"prompt_tokens": 11, "completion_tokens": 3}}]
            success = len(batches) > 1
            yield task_id, {
                "ok": True,
                "result": {
                    "id": task_id,
                    "status": "completed" if success else "failed",
                    "completed": success,
                    "metrics": task_metrics(
                        ledger.snapshot(),
                        [{"tool": "MatrixInverse"}],
                        runtime_seconds=2,
                        finished=True,
                    ),
                },
            }

    monkeypatch.setattr(runner, "GenerationClient", Client)
    monkeypatch.setattr(runner, "actor_file_hashes", lambda *a: {})
    monkeypatch.setattr(runner, "iter_tasks", offline_jobs)
    path = runner.run_batch(args)
    table = json.loads(path.with_name("task_metrics.json").read_text())
    envelope = json.loads(path.read_text())
    assert table["fingerprint"] == envelope["fingerprint"]
    assert table["tasks"][0]["input_tokens"] == 11
    assert table["tasks"][0]["output_tokens"] == 3
    assert table["tasks"][0]["tool_calls"] == 1
    assert table["tasks"][0]["runtime_seconds"] == 2
    args.resume = True
    runner.run_batch(args)
    assert batches == [1, 0]
    assert (
        json.loads(path.with_name("task_metrics.json").read_text())["tasks"]
        == table["tasks"]
    )
    args.retry_failed = True
    runner.run_batch(args)
    table = json.loads(path.with_name("task_metrics.json").read_text())
    assert batches == [1, 0, 1]
    assert len(table["tasks"]) == 1 and table["tasks"][0]["completed"]
    assert table["tasks"][0]["input_tokens"] == 11


def test_scitoolagent_counts_automatic_contract_reads_without_duplicating_phase_calls(
    tmp_path,
):
    from baselines.scitoolagent.runtime import run_scitoolagent
    from tests.baselines.test_task_resources import Client
    from tests.support.planner import PLAN, CALL, FINISH, SCHEMA, StaticRetriever
    from tools import execute, ToolCatalog

    result = run_scitoolagent(
        "Use supplied JSON",
        catalog=ToolCatalog(),
        client=Client(
            [PLAN, CALL, FINISH], {"prompt_tokens": 3, "completion_tokens": 2}
        ),
        invoke=execute,
        trace_dir=tmp_path,
        answer_schema=SCHEMA,
        retriever=StaticRetriever(),
    )
    assert result["status"] == "completed", result["failure_reason"]
    metrics = result["metrics"]
    assert metrics["tool_calls"] == len(result["calls"]) == 2
    assert metrics["scientific_tool_calls"] == metrics["discovery_tool_calls"] == 1
    assert metrics["input_tokens"] == 9 and metrics["output_tokens"] == 6


@pytest.mark.parametrize("baseline", ["react", "scitoolagent"])
def test_interrupted_dispatch_is_recorded_in_last_trace(tmp_path, baseline):
    from baselines.react.runtime import run_react
    from baselines.scitoolagent.runtime import run_scitoolagent
    from tests.baselines.test_task_resources import Client
    from tests.support.planner import PLAN, CALL, SCHEMA, StaticRetriever
    from tools import ToolCatalog

    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt

    runtime = run_react if baseline == "react" else run_scitoolagent
    replies = [CALL] if baseline == "react" else [PLAN]
    kwargs = {} if baseline == "react" else {"retriever": StaticRetriever()}
    with pytest.raises(KeyboardInterrupt):
        runtime(
            "Use supplied JSON",
            catalog=ToolCatalog(),
            client=Client(replies, {"prompt_tokens": 3, "completion_tokens": 2}),
            invoke=interrupt,
            trace_dir=tmp_path,
            answer_schema=SCHEMA,
            **kwargs,
        )
    trace = json.loads(next(tmp_path.glob("*/trajectory.json")).read_text())
    assert trace["status"] == "interrupted"
    assert trace["metrics"]["tool_calls"] == 1
    assert not trace["metrics"]["tool_calls_complete"]
    assert trace["metrics"]["input_tokens"] == 3
    assert trace["metrics"]["output_tokens"] == 2
