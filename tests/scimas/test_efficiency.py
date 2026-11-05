"""Lossless contexts, safe caches and correction delivery boundaries."""

from copy import deepcopy
import json
import pytest
from baselines.scimas.context import role_messages, request_diagnostics, request_payload
from baselines.scimas.knowledge import ToolKnowledge
from .test_runtime import Client, run


def test_context_is_lossless_and_stable_before_changing_state():
    payload = {
        "ready": ["a"],
        "task": {"question": "µ spectrum"},
        "graph": {"nodes": [1, 2]},
        "contracts": {"a": {"type": "number"}},
        "observations": {"o1": {"output": "x: y, z"}},
        "feedback": [],
    }
    old = deepcopy(payload)
    first = role_messages("prompt", payload, {"type": "object"})
    decoded = request_payload(first)
    assert decoded["context"] == old and payload == old
    assert decoded["response_schema"] == {"type": "object"}
    payload["ready"] = ["b"]
    second = role_messages("prompt", payload, {"type": "object"})
    shared = request_diagnostics(second, first)["same_role_prefix_chars"]
    assert shared > len("prompt") + len(json.dumps(payload["task"])) + len(
        json.dumps(payload["graph"])
    )
    assert len(first[-1]["content"]) < len(json.dumps(decoded, ensure_ascii=False))
    assert request_diagnostics(first)["same_role_prefix_chars"] == 0
    assert "JSON object" in first[0]["content"]


@pytest.mark.parametrize("mode", ["format", "scientific"])
def test_final_correction_survives_role_loop_and_inspection(tmp_path, mode):
    counts = {"summary": 0, "final": 0}
    seen = []

    def hook(payload, action):
        ctx = payload.get("context", {})
        if "finish" in action:
            counts["summary"] += 1
            if counts["summary"] == 1 and mode == "format":
                return {"finish": {"wrong": 1}}
            if counts["summary"] == 2:
                seen.append(deepcopy(ctx["feedback"]))
                return {
                    "inspect": {
                        "observation_id": next(iter(ctx["observations"])),
                        "path": [],
                        "decoded": False,
                    }
                }
            if counts["summary"] == 3:
                seen.append(deepcopy(ctx["feedback"]))
        if ctx.get("stage") == "final":
            counts["final"] += 1
            if counts["final"] == 1 and mode == "scientific":
                return {
                    "revise_answer": "Check the reported identity product against accepted evidence."
                }
        return action

    result = run(tmp_path, Client(hook))
    assert result["status"] == "completed", result["failure_reason"]
    key = "format_errors" if mode == "format" else "scientific_review"
    assert seen and key in seen[0][0] and key in seen[1][0]
    assert "inspection" in seen[1][-1]


def test_connection_cache_reranks_and_isolates_mutable_results(monkeypatch):
    kg = ToolKnowledge()
    original = kg._connection_candidates
    calls = []

    def measured(name, direction):
        calls.append((name, direction))
        return original(name, direction)

    monkeypatch.setattr(kg, "_connection_candidates", measured)
    first = kg.connections("MatrixMultiply", limit=500)
    assert first["connections"]
    favored = first["connections"][-1]["source_tool"]
    second = kg.connections("MatrixMultiply", limit=500, relevance={favored: 1})
    assert second["connections"][0]["source_tool"] == favored
    assert len(calls) == 1
    first["connections"][0]["checks"].append("corrupt")
    assert all(
        "corrupt" not in r["checks"]
        for r in kg.connections("MatrixMultiply", limit=500)["connections"]
    )
    kg.connections("MatrixMultiply", "successors")
    assert len(calls) == 2
