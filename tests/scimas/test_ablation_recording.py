"""Ablation recording acceptance with real tools and the current Mini grader.

Role replies and token counts are controlled test inputs, not model results.
The actor only reads public task context and executed observations. Reviewed
references are loaded separately by the evaluator after execution.
"""

from argparse import Namespace
from copy import deepcopy
import json
from pathlib import Path
import time

import pytest

from baselines.scimas.ablation import VARIANTS
from baselines.scimas.context import request_payload
from src.utils.paths import project_root
from tools import ToolCatalog


class RecordingKnowledge:
    def __init__(self, catalog):
        self.catalog = catalog
        self.allowed = lambda name: name in self.tools
        self.manifest = {"graph_sha256": "recording-control-not-a-retrieval-experiment"}
        self.embedding = type("Embedding", (), {"stats": {"requests": 0}})()
        self.tools = {
            name: {"planning": {
                "parallel_safe": "isolated_processes_with_resource_limits",
                "output_access": "native_fields",
            }} for name in ["ParseJSONDocument", "MatrixSVD"]
        }

    def planning_view(self, names):
        return {name: self.catalog.describe(name)["tools"][name] for name in names}

    def search(self, queries, deadline):
        return {"tools": self.planning_view(self.tools), "queries": queries}


def spectroscopy_plan():
    nodes = [{
        "id": "read", "tool": "ParseJSONDocument", "object": "channel designs",
        "purpose": "Read the supplied channel design table",
        "arguments": {"json_file": {"kind": "task", "path": ["inputs", "channel_design_file"]}},
    }]
    for index in range(3):
        nodes.append({
            "id": "candidate_" + str(index), "tool": "MatrixSVD", "object": "candidate " + str(index),
            "purpose": "Evaluate singular values on the supplied unscaled basis",
            "arguments": {"values": {"kind": "node", "node": "read",
                "path": ["document", "data", index, "augmented_response_matrix"]}},
        })
    nodes.append({
        "id": "original", "tool": "MatrixSVD", "object": "original channels",
        "purpose": "Check identifiability of the original two response rows",
        "arguments": {"values": {"kind": "list", "items": [
            {"kind": "node", "node": "read", "path": ["document", "data", 0, "augmented_response_matrix", i]}
            for i in range(2)
        ]}},
    })
    return {"nodes": nodes, "deliverables": [{
        "requirement": "report", "nodes": [n["id"] for n in nodes],
        "description": "Compare every candidate and report the original-channel identifiability",
    }]}


class RecordingClient:
    backend = "api"
    model = "recording-control-not-a-model-result"
    supports_response_schema = True
    scenario = "success"

    def __init__(self, *args, **kwargs):
        self.calls = 0

    def public_settings(self):
        return {"endpoint": "http://localhost/recording-control", "sampling": {}}

    def request(self, messages, **kwargs):
        self.calls += 1
        payload = request_payload(messages)
        stage = payload.get("stage")
        if stage == "decompose":
            decision = {"requirements": [{
                "id": "report", "description": "Choose a channel and report the requested measurements",
                "evidence": "Report selected_channel_id, minimum_singular_value and original_channels_identifiable.",
                "mode": "complete",
            }], "queries": ["Read JSON and compute matrix singular values"]}
        elif stage == "graph":
            if self.scenario == "communication_failure":
                from src.models.communication import CommunicationError
                time.sleep(0.01)
                raise CommunicationError("Injected communication failure", service="generation",
                    category="ConnectTimeout", request_may_have_been_sent=False)
            plan = spectroscopy_plan()
            if self.scenario == "redundant_work":
                duplicate = deepcopy(plan["nodes"][2])
                duplicate.update(id="repeat_candidate", purpose="Deliberately redundant recording control")
                plan["nodes"].append(duplicate)
                plan["deliverables"][0]["nodes"].append(duplicate["id"])
            decision = {"plan": plan}
        else:
            ctx = payload["context"]
            if "stage" in ctx:
                if ctx["stage"] == "result":
                    decision = {"accept": {"reason": "Controlled recording check", "semantics": []}}
                else:
                    decision = {"approve": {"reason": "Controlled recording check", "gates": []}}
            elif "ready" in ctx:
                decision = {"dispatch": [r["id"] for r in ctx["ready"]][:ctx["available_slots"]]}
            elif "request" in ctx:
                raise AssertionError("Unexpected repair in the deterministic recording control")
            else:
                observed = {o["node"]: o["output"] for o in ctx["observations"].values()
                            if o.get("accepted_for_current_graph")}
                records = observed["read"]["document"]["data"]
                minima = [min(observed["candidate_" + str(i)]["singular_values"]) for i in range(3)]
                best = max(minima)
                selected = min((i for i in range(3) if abs(minima[i] - best) <= 1e-8),
                               key=lambda i: records[i]["record_id"])
                answer = {"selected_channel_id": records[selected]["record_id"],
                    "minimum_singular_value": minima[selected],
                    "original_channels_identifiable": min(observed["original"]["singular_values"]) > 1e-12}
                if self.scenario == "wrong_answer":
                    answer["selected_channel_id"] = "deliberately-wrong-recording-control"
                decision = {"finish": answer}
        return {"text": json.dumps(decision), "usage": {
            "prompt_tokens": 11, "completion_tokens": 7,
            "prompt_tokens_details": {"cached_tokens": 3},
            "completion_tokens_details": {"reasoning_tokens": 2},
        }}

    def close(self):
        pass


@pytest.fixture(scope="module")
def recording_reference():
    # Controller-side only: never passed to the actor or its Knowledge/Client.
    from evaluation.suites.mini import load_references
    return load_references(project_root())


def execute_recording_control(monkeypatch, folder, variant, scenario="success", dataset_name="mini"):
    import baselines.react.runner as batch
    import baselines.scimas.runtime as runtime
    from tests.integration.test_mini_dataset import options

    options_row = options(monkeypatch, folder)
    options_row.update(baseline="scimas", scimas_ablation=variant, embedding_backend="api",
        tasks="SMAS-0103", dataset=dataset_name, model=RecordingClient.model,
        output=str(folder / "predictions.json"), concurrency=1)
    actor = type("ControlledClient", (RecordingClient,), {"scenario": scenario})
    original = runtime.run_scimas

    def wrapped(*args, **kwargs):
        return original(*args, **kwargs, knowledge=RecordingKnowledge(kwargs["catalog"]))

    def inline_jobs(jobs, function, concurrency, on_active, should_schedule=None):
        for task_id, payload in jobs:
            if should_schedule is not None and not should_schedule():
                break
            on_active([task_id])
            yield task_id, {"ok": True, "result": function(payload)}
            on_active([])

    monkeypatch.setattr(batch, "GenerationClient", actor)
    monkeypatch.setattr(batch, "iter_tasks", inline_jobs)
    monkeypatch.setattr(runtime, "run_scimas", wrapped)
    for variable in ["SCITOOLFLOW_WORK_DIR", "SCITOOLFLOW_ARTIFACTS_DIR"]:
        monkeypatch.setenv(variable, str(folder / variable.lower()))
    monkeypatch.setenv("SCITOOL_EMBEDDING_BACKEND", "api")
    path = batch.run_batch(Namespace(**options_row))
    envelope = json.loads(Path(path).read_text())
    prediction = envelope["predictions"][0]
    trace = json.loads(Path(prediction["trace_path"]).read_text())
    table = json.loads((folder / "task_metrics.json").read_text())
    return envelope, prediction, trace, table


@pytest.mark.parametrize("variant", VARIANTS)
@pytest.mark.parametrize("scenario", ["success", "wrong_answer", "redundant_work", "communication_failure"])
def test_current_mini_scores_and_costs_roundtrip(monkeypatch, tmp_path, recording_reference, variant, scenario):
    from evaluation.suites import mini

    folder = tmp_path / variant / scenario
    envelope, prediction, trace, table = execute_recording_control(monkeypatch, folder, variant, scenario)
    metrics = prediction["metrics"]
    assert trace["metrics"] == metrics
    assert table["fingerprint"] == envelope["fingerprint"]
    for name, value in metrics.items():
        assert table["tasks"][0][name] == value
    assert table["ablation"] == prediction["ablation"] == trace["ablation"]
    assert table["ablation"]["variant"] == variant
    assert metrics["wall_runtime_seconds"] == trace["duration_seconds"] > 0
    assert metrics["active_runtime_seconds"] + metrics["communication_wait_seconds"] == pytest.approx(metrics["wall_runtime_seconds"])
    assert metrics["scientific_tool_calls"] == len([c for c in prediction["calls"] if c["tool"] != "DescribeTools"])
    assert metrics["model_requests"] == len(trace["resource_usage"]["requests"])
    if scenario == "communication_failure":
        assert prediction["status"] == "failed"
        assert metrics["runtime_seconds"] is None and not metrics["runtime_reportable"]
        assert metrics["input_tokens"] is metrics["output_tokens"] is None
        assert metrics["observed_input_tokens"] == 11
        assert metrics["observed_output_tokens"] == 7
        assert metrics["requests_missing_input_usage"] == metrics["requests_missing_output_usage"] == 1
        assert metrics["scientific_tool_calls"] == 0
    else:
        assert prediction["completed"], prediction["failure_reason"]
        assert metrics["runtime_reportable"] and metrics["runtime_seconds"] == metrics["wall_runtime_seconds"]
        assert metrics["input_tokens"] == 11 * metrics["model_requests"]
        assert metrics["output_tokens"] == 7 * metrics["model_requests"]
        assert metrics["token_usage_complete"]
        assert metrics["scientific_tool_calls"] == (6 if scenario == "redundant_work" else 5)
    # Reuse the frozen controller-side references, not grading decisions. All
    # actor source hashes, public inputs, raw traces and resource checks remain live.
    monkeypatch.setattr(mini, "load_references", lambda *args: recording_reference)
    report = mini.evaluate(project_root(), folder / "predictions.json", folder / "scores.json",
                           task_ids=["SMAS-0103"])
    persisted = json.loads((folder / "scores.json").read_text())
    assert persisted == report
    assert report["schema_version"] == "scitoolflow.mini.three_metrics.v3"
    assert report["metric_definition_version"] == "independent-runtime-answer.v2"
    row = report["tasks"][0]
    assert row["evidence_integrity"]["verified"], row
    assert row["resource_policy_compliant"], row
    if scenario != "communication_failure":
        assert report["summary"]["runtime_completion_rate"] == 1
        assert report["summary"]["answer_accuracy"] == (scenario != "wrong_answer")
    else:
        assert report["summary"]["runtime_completion_rate"] == report["summary"]["answer_accuracy"] == 0
    c, e = row["orchestration_credit"], row["selection_efficiency"]
    expected = 3 * c * e / (2 * e + c) if c and e else 0
    assert row["tool_orchestration_score"] == pytest.approx(expected)
    assert report["summary"]["tool_planning_accuracy"] == pytest.approx(expected)
    if scenario == "redundant_work":
        assert 0 < expected < 1
        assert report["summary"]["strict_tool_planning_accuracy"] == 1


@pytest.mark.parametrize("variant", VARIANTS)
def test_api_failure_overlapping_tool_work_is_not_subtracted_twice(tmp_path, variant):
    import threading
    from baselines.scimas.ablation import resolve_ablation
    from src.models.communication import CommunicationError
    from .test_runtime import run, Client, fixture_invoke
    from .test_ablation import independent_hook

    parallel = resolve_ablation(variant).parallel
    lock, slow_started = threading.Lock(), threading.Event()
    sequence = 0

    def invoke(name, arguments, **kwargs):
        nonlocal sequence
        with lock:
            sequence += 1
            index = sequence
        if index == 2:
            slow_started.set()
            time.sleep(0.15)
        elif parallel:
            assert slow_started.wait(3)
            time.sleep(0.01)
        return fixture_invoke(name, arguments, **kwargs)

    def hook(payload, action):
        action = independent_hook(payload, action)
        if payload.get("context", {}).get("stage") == "result":
            time.sleep(0.05)
            raise CommunicationError("Injected reviewer transport failure", service="generation",
                category="ReadTimeout", request_may_have_been_sent=True)
        return action

    result = run(tmp_path, Client(hook), invoke=invoke, scimas_ablation=variant)
    metrics = result["metrics"]
    assert result["status"] == "failed"
    assert metrics["runtime_seconds"] is None and not metrics["runtime_reportable"]
    assert metrics["tool_calls_complete"]
    assert metrics["scientific_tool_calls"] == (2 if parallel else 1)
    assert metrics["active_runtime_seconds"] + metrics["communication_wait_seconds"] == pytest.approx(metrics["wall_runtime_seconds"])
    assert metrics["communication_fault_seconds"] >= 0.045
    if parallel:
        # The still-running tool covers the failed reviewer request interval.
        assert metrics["communication_wait_seconds"] < 0.005
        assert metrics["communication_overlap_seconds"] >= 0.045
    else:
        assert metrics["communication_overlap_seconds"] == pytest.approx(0)
        assert metrics["communication_wait_seconds"] >= 0.045
    persisted = json.loads(Path(result["trace_path"]).read_text())
    assert persisted["metrics"] == metrics
