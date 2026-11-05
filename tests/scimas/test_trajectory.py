"""Complete step records with offline-only case export and no extra requests."""

import hashlib
import json
from pathlib import Path

import pytest

from baselines.common.resources import TaskResources
from baselines.scimas.roles import RecordedClient
from baselines.scimas.trajectory import export_case
from src.models.client import response_error
from .test_runtime import Client, run, fixture_invoke


def test_live_trace_preserves_public_input_and_step_details_without_sidecar_writes(
    tmp_path,
):
    client = Client()

    def invoke(*args, **kwargs):
        return dict(fixture_invoke(*args, **kwargs), worker_stderr="diagnostic fixture")

    result = run(tmp_path, client, invoke=invoke)
    trace = json.loads(Path(result["trace_path"]).read_text())
    assert trace["status"] == "completed"
    assert trace["task"]["inputs"] and trace["task"]["question"]
    assert len({s["step_id"] for s in trace["steps"]}) == len(trace["steps"])
    assert [s["recorded_seconds"] for s in trace["steps"]] == sorted(
        s["recorded_seconds"] for s in trace["steps"]
    )
    model_steps = [s for s in trace["steps"] if "model" in s]
    assert (
        len(model_steps) == len(client.contexts) == trace["metrics"]["model_requests"]
    )
    for step in model_steps:
        assert step["model"]["messages"] and step["model"]["response"]["text"]
        assert step["decision"] and step["validation_errors"] == []
        assert step["model"]["started_at"] <= step["model"]["finished_at"]
        assert step["model"]["duration_seconds"] >= 0
        assert step["model"]["usage"] == {"prompt_tokens": 10, "completion_tokens": 5}
        assert step["model"]["options"]["max_tokens"] == 8192
    assert trace["pending_calls"] == []
    calls = [c for s in trace["steps"] for c in s.get("calls", [])]
    assert len(calls) == 2
    assert all(
        c["dispatcher_metadata"]["worker_stderr"] == "diagnostic fixture" for c in calls
    )
    assert all(c["files"] == [] and c["timeout_seconds"] > 0 for c in calls)
    folder = Path(result["trace_path"]).parent
    assert not (folder / "analysis").exists()
    assert not (folder / "requests").exists()


def test_offline_export_is_lossless_and_never_rewrites_the_original_trace(tmp_path):
    result = run(tmp_path)
    source = Path(result["trace_path"])
    before = source.read_bytes()
    exported = export_case(source)
    assert source.read_bytes() == before
    assert exported["source_sha256"] == hashlib.sha256(before).hexdigest()
    folder = source.parent / "analysis"
    report = (folder / "trajectory.md").read_text()
    assert result["task_id"] in report and "逐步轨迹" in report
    requests = [json.loads(p.read_text()) for p in (folder / "requests").glob("*.json")]
    actual = [s for s in result["steps"] if "model" in s]
    assert len(requests) == len(actual)
    for step in actual:
        saved = json.loads(
            (folder / "requests" / (step["step_id"] + ".json")).read_text()
        )
        assert saved["model"] == step["model"] and saved["decision"] == step["decision"]
    for call in result["calls"]:
        request = json.loads(
            (folder / "calls" / call["observation_id"] / "request.json").read_text()
        )
        response = json.loads(
            (folder / "calls" / call["observation_id"] / "response.json").read_text()
        )
        assert request["arguments"] == call["arguments"]
        assert response["output"] == call["output"]
    assert len(result["steps"]) == exported["steps"]


def test_partial_completion_and_validation_metadata_add_no_checkpoint_writes():
    trace, saves = {"steps": []}, []
    resources = TaskResources()
    partial = {
        "id": "fixture",
        "model": "fixture",
        "choices": [
            {
                "message": {
                    "content": '{"plan":',
                    "reasoning_content": "provider returned fixture",
                },
                "finish_reason": "length",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20},
    }

    class Broken:
        def request(self, *args, **kwargs):
            raise response_error("Output truncated", partial)

    client = RecordedClient(
        Broken(), resources, "planner", trace, lambda: saves.append(1)
    )
    with pytest.raises(RuntimeError, match="Output truncated"):
        client.request([{"role": "user", "content": "fixture"}], max_tokens=20)
    assert len(saves) == 2  # Same pre/post request checkpoints as before.
    step = trace["steps"][0]
    assert step["model"]["response"]["text"] == '{"plan":'
    assert step["model"]["response"]["finish_reason"] == "length"
    assert step["model"]["usage"] == partial["usage"]
    client.record_validation(None, ["Invalid JSON"])
    assert len(saves) == 2
    assert step["validation_errors"] == ["Invalid JSON"]


def test_planning_progress_survives_interruption(tmp_path):
    contexts = []

    def interrupted(payload, action):
        contexts.append(payload)
        if payload.get("stage") == "graph":
            raise KeyboardInterrupt
        return action

    result = run(tmp_path, Client(interrupted))
    trace = json.loads(Path(result["trace_path"]).read_text())
    assert trace["status"] == "interrupted"
    assert trace["planning_progress"]["retrievals"]
    assert trace["planning_progress"]["requirements"]
    assert "steps" not in trace["planning_progress"]
    assert trace["steps"][-1]["model"]["error"].startswith("KeyboardInterrupt")
    assert trace["steps"][-1]["model"]["messages"]
