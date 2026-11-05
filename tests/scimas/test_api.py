"""The complete SciMas role loop uses the shared real HTTP transport."""

from src.models.client import GenerationClient
from tools import execute
from tests.baselines.test_model_backends import api_server
from .test_knowledge_planner import decomposition, valid_plan
from .test_runtime import run

import json
from types import SimpleNamespace
from unittest.mock import Mock
import pytest


def test_complete_workflow_through_api_transport(tmp_path):
    approve = {
        "approve": {"reason": "Public scientific requirements checked", "gates": []}
    }
    accept = {"accept": {"reason": "Actual output checked", "semantics": []}}
    replies = [
        decomposition(),
        {"plan": valid_plan()},
        approve,
        {"dispatch": ["inverse"]},
        accept,
        {"dispatch": ["check"]},
        accept,
        {"finish": {"inverse": [[0.5, 0], [0, 0.25]], "product": [[1, 0], [0, 1]]}},
        approve,
    ]
    with api_server(replies, SCITOOLFLOW_API_STRUCTURED_OUTPUT="0") as sent:
        client = GenerationClient("api")
        try:
            result = run(tmp_path, client, invoke=execute)
        finally:
            client.close()
    assert result["status"] == "completed", result["failure_reason"]
    assert len(sent) == 9
    assert all(r["path"] == "/v1/chat/completions" for r in sent)
    assert all(r["payload"]["model"] == "mock-model" for r in sent)
    assert all("max_tokens" in r["payload"] for r in sent)
    assert all(
        any("json" in m["content"].lower() for m in r["payload"]["messages"])
        for r in sent
    )
    assert any(len(r["payload"]["messages"]) == 3 for r in sent)
    assert result["stats"]["scientific_calls"] == 2


@pytest.mark.parametrize("blank_only", [False, True])
def test_blank_json_completion_uses_bounded_protocol_correction_and_counts_usage(
    tmp_path, monkeypatch, blank_only
):
    for key, value in {
        "SCITOOLFLOW_API_BASE": "https://api.example.com",
        "SCITOOLFLOW_API_KEY": "TEST_ONLY",
        "SCITOOLFLOW_API_JSON_MODE": "1",
        "SCITOOLFLOW_API_STRUCTURED_OUTPUT": "0",
        "SCITOOLFLOW_API_EXTRA_BODY": "{}",
    }.items():
        monkeypatch.setenv(key, value)
    approve = {"approve": {"reason": "Checked", "gates": []}}
    accept = {"accept": {"reason": "Checked", "semantics": []}}
    pending = iter(
        [
            " \n ",
            decomposition(),
            {"plan": valid_plan()},
            approve,
            {"dispatch": ["inverse"]},
            accept,
            {"dispatch": ["check"]},
            accept,
            {"finish": {"inverse": [[0.5, 0], [0, 0.25]], "product": [[1, 0], [0, 1]]}},
            approve,
        ]
    )
    if blank_only:
        pending = iter([" \n "] * 10)

    def post(*args, **kwargs):
        content = next(pending)
        if not isinstance(content, str):
            content = json.dumps(content)
        return SimpleNamespace(
            status_code=200,
            json=lambda: {
                "model": "fixture",
                "choices": [{"finish_reason": "stop", "message": {"content": content}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        )

    session = Mock()
    session.post.side_effect = post
    client = GenerationClient("api", session=session)
    client.model = "fixture"
    result = run(tmp_path, client)
    assert result["status"] == ("failed" if blank_only else "completed"), result[
        "failure_reason"
    ]
    assert session.post.call_count == 10
    first = result["steps"][0]
    assert first["model"]["response"]["text"] == " \n "
    assert first["model"]["response"]["empty_json_completion"]
    assert first["validation_errors"]
    assert result["stats"]["protocol_errors"] == (10 if blank_only else 1)
    assert result["metrics"]["model_requests"] == 10
    assert (
        result["metrics"]["input_tokens"] == 100
        and result["metrics"]["output_tokens"] == 50
    )
    assert result["metrics"]["tool_calls"] == (0 if blank_only else 2)


@pytest.mark.parametrize(
    "reason,mode", [("length", "1"), ("content_filter", "1"), ("stop", "0")]
)
def test_blank_recovery_does_not_bypass_failure_boundaries(monkeypatch, reason, mode):
    for key, value in {
        "SCITOOLFLOW_API_BASE": "https://api.example.com",
        "SCITOOLFLOW_API_KEY": "TEST_ONLY",
        "SCITOOLFLOW_API_JSON_MODE": mode,
        "SCITOOLFLOW_API_EXTRA_BODY": "{}",
    }.items():
        monkeypatch.setenv(key, value)
    session = Mock()
    session.post.return_value = SimpleNamespace(
        status_code=200,
        json=lambda: {
            "choices": [{"finish_reason": reason, "message": {"content": "   "}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        },
    )
    client = GenerationClient("api", session=session)
    client.model = "fixture"
    with client.generation_scope(), pytest.raises(RuntimeError):
        client.request([{"role": "user", "content": "Return JSON"}])
    assert session.post.call_count == 1
