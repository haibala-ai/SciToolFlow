"""Task-wide boundaries across free thinking, tool dispatch and KG role handoffs."""

import json
import tempfile
from unittest.mock import patch
import pytest
from baselines.react.runtime import run_react
from baselines.common.resources import TaskResources, BudgetedClient
from baselines.common.session import SessionOptions
from baselines.scitoolagent.runtime import run_scitoolagent
from tests.support.planner import PLAN, CALL, FINISH, SCHEMA, StaticRetriever
from tools import execute
from tools.catalog import ToolCatalog


class Client:
    model = "bounded-test-control"
    backend = "injected"

    def __init__(self, replies, usage=None):
        self.replies = iter(replies)
        self.calls = 0
        self.usage = usage

    def request(self, messages, **kwargs):
        self.calls += 1
        return {"text": json.dumps(next(self.replies)), "usage": self.usage}


def run(replies, **kwargs):
    client = Client(replies, {"prompt_tokens": 3, "completion_tokens": 2})
    catalog = ToolCatalog()
    with tempfile.TemporaryDirectory() as folder:
        result = run_react(
            "Use actual observed inputs.",
            catalog=catalog,
            client=client,
            invoke=lambda n, a, **kw: execute(n, a, catalog=catalog, **kw),
            trace_dir=folder,
            session=SessionOptions(persist=False),
            **kwargs,
        )
    return result, client


def test_400th_finish_is_accepted():
    result, client = run(
        [{"think": "Work through the model"}] * 399 + [{"finish": {"value": 7}}]
    )
    assert result["status"] == "completed" and client.calls == 400
    assert result["resource_usage"]["model_requests"] == 400
    assert result["resource_usage"]["prompt_tokens"] == 1200
    assert result["resource_usage"]["completion_tokens"] == 800


def test_401st_request_is_never_sent():
    result, client = run(
        [{"think": "Work through the model"}] * 400 + [{"finish": {"value": 7}}]
    )
    assert client.calls == 400 and len(result["steps"]) == 400
    assert result["failure_reason"] == "ModelRequestBudget"


def test_scientific_calls_can_exceed_old_default_without_repeating_arguments():
    replies = [
        {
            "actions": [
                {
                    "tool": "ParseJSONDocument",
                    "arguments": {"json_text": json.dumps({"row": i})},
                }
            ]
        }
        for i in range(35)
    ]
    result, client = run(replies + [{"finish": {"value": 7}}])
    assert result["status"] == "completed" and result["stats"]["scientific_calls"] == 35
    assert result["limits"]["scientific_calls"] is None


@pytest.mark.parametrize("finish", [True, False])
def test_kg_roles_share_the_400_request_ledger(finish):
    replies = [PLAN, CALL] + [{"think": "Check evidence"}] * (397 if finish else 398)
    if finish:
        replies.append(FINISH)
    client = Client(replies)
    catalog = ToolCatalog()
    with (
        tempfile.TemporaryDirectory() as folder,
        patch("baselines.scitoolagent.runtime.atomic_json"),
    ):
        result = run_scitoolagent(
            "Use supplied JSON",
            catalog=catalog,
            client=client,
            invoke=lambda n, a, **kw: execute(n, a, catalog=catalog, **kw),
            trace_dir=folder,
            answer_schema=SCHEMA,
            retriever=StaticRetriever(),
        )
    assert client.calls == result["resource_usage"]["model_requests"] == 400
    assert result["status"] == ("completed" if finish else "failed")
    if not finish:
        assert result["failure_reason"] == "ModelRequestBudget"
    assert {r["phase"] for r in result["resource_usage"]["requests"]} == {
        "planner",
        "executor",
        "summarizer",
    }


def test_late_valid_finish_is_a_deadline_failure():
    clock = [0]
    client = Client([{"finish": {"value": 7}}])
    original = client.request

    def late(*args, **kwargs):
        result = original(*args, **kwargs)
        clock[0] = 2
        return result

    client.request = late
    with tempfile.TemporaryDirectory() as folder:
        result = run_react(
            "Return result",
            catalog=ToolCatalog(),
            client=client,
            invoke=lambda *a, **kw: None,
            trace_dir=folder,
            clock=lambda: clock[0],
            task_timeout=1,
            session=SessionOptions(persist=False),
        )
    assert result["failure_reason"] == "TaskDeadline" and result["final_answer"] is None
    assert result["resource_usage"]["model_requests"] == 1


def test_missing_usage_is_unknown_and_failed_provider_usage_is_preserved():
    ledger = TaskResources()
    client = BudgetedClient(Client([{"finish": {"value": 7}}]), ledger)
    client.request([])
    snapshot = ledger.snapshot()
    assert snapshot["prompt_tokens"] is None and not snapshot["token_usage_complete"]

    def fail(*args, **kw):
        error = RuntimeError("output limit")
        error.generation_usage = {"prompt_tokens": 5, "completion_tokens": 9}
        raise error

    base = Client([])
    base.request = fail
    ledger = TaskResources()
    with pytest.raises(RuntimeError):
        BudgetedClient(base, ledger).request([])
    assert (
        ledger.snapshot()["completion_tokens"] == 9
        and ledger.snapshot()["model_requests"] == 1
    )


@pytest.mark.parametrize("stage", ["input_budget", "count_tokens"])
def test_preflight_failure_preserves_a_zero_generation_trace(stage):
    class Preflight(Client):
        backend = "vllm"
        supports_preflight_timeout = True

        def input_budget(self, output_tokens, timeout=None):
            if stage == "input_budget":
                raise ConnectionError("Preflight unavailable")
            return 10000

        def count_tokens(self, messages, timeout=None):
            raise ConnectionError("Tokenizer unavailable")

    client = Preflight([])
    with tempfile.TemporaryDirectory() as folder:
        result = run_react(
            "Use supplied values",
            catalog=ToolCatalog(),
            client=client,
            invoke=lambda *a, **kw: None,
            trace_dir=folder,
        )
        saved = json.loads(open(result["trace_path"]).read())
    assert saved["status"] == "failed" and saved["steps"] == []
    assert saved["resource_usage"]["model_requests"] == client.calls == 0
    assert "ConnectionError" in saved["failure_reason"]


def test_token_preflight_obeys_shared_remaining_time_without_generation_charge():
    now = [0]
    received = []

    class Preflight(Client):
        backend = "vllm"
        supports_preflight_timeout = True

        def input_budget(self, output_tokens, timeout=None):
            received.append(timeout)
            now[0] = 0.5
            return 10000

        def count_tokens(self, messages, timeout=None):
            received.append(timeout)
            now[0] = 2
            return 10

    client = Preflight([])
    with tempfile.TemporaryDirectory() as folder:
        result = run_react(
            "Use supplied values",
            catalog=ToolCatalog(),
            client=client,
            invoke=lambda *a, **kw: None,
            trace_dir=folder,
            task_timeout=1,
            clock=lambda: now[0],
        )
    assert received == [1, 0.5]
    assert result["failure_reason"] == "TaskDeadline"
    assert result["resource_usage"]["model_requests"] == client.calls == 0


def test_finish_time_is_checked_and_frozen_from_one_clock_read():
    ticks = iter([0, 7199.9, 7200.2])
    resources = TaskResources(clock=lambda: next(ticks))
    resources.complete()
    assert resources.snapshot()["elapsed_seconds"] == 7199.9


@pytest.mark.parametrize("flag", ["--task-timeout", "--tool-timeout"])
@pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
def test_cli_rejects_nonfinite_time_limits_before_running(flag, value):
    from cli import main

    with (
        patch("sys.argv", ["scitoolflow", "run", flag + "=" + value]),
        patch("baselines.react.runner.run_batch") as run_batch,
    ):
        with pytest.raises(SystemExit) as error:
            main()
    assert error.value.code == 2 and not run_batch.called


def test_production_vllm_preflight_passes_remaining_timeout_to_transport():
    from src.models.client import GenerationClient

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"data": [{"id": "control", "max_model_len": 12000}], "count": 20}

    class Transport:
        def __init__(self):
            self.timeouts = []

        def get(self, *args, **kwargs):
            self.timeouts.append(kwargs["timeout"])
            return Response()

        post = get

    transport = Transport()
    client = GenerationClient("vllm", session=transport)
    client.model = "control"
    with patch.dict(
        "os.environ", {"SCITOOLFLOW_VLLM_BASE": "http://127.0.0.1:8016/v1"}
    ):
        assert client.input_budget(4096, timeout=0.25) == 7904
        assert client.count_tokens([], timeout=0.125) == 20
    assert transport.timeouts == [0.25, 0.125]
