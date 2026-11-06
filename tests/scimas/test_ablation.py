"""Mechanism-level counterfactuals using fixed role decisions, not model scores."""

from copy import deepcopy
import json
import threading
import time

import pytest

from baselines.scimas.ablation import VARIANTS, resolve_ablation
from baselines.scimas.ablation.policy import runtime_options
from baselines.scimas.task_graph import TaskGraph
from baselines.scimas.runtime import run_scimas
from .test_runtime import Client, Knowledge, fixture_invoke, run
from .test_knowledge_planner import public_example, valid_plan


@pytest.mark.parametrize("variant", VARIANTS)
def test_all_variants_complete_real_scientific_tools_and_preserve_trace(tmp_path, variant):
    from tools import execute
    from evaluation.integrity.traces import verify_trajectory

    client = Client()
    trace = run(tmp_path, client, invoke=execute, scimas_ablation=variant)
    assert trace["status"] == "completed", trace["failure_reason"]
    assert trace["final_answer"]["product"] == [[1, 0], [0, 1]]
    assert trace["metrics"]["scientific_tool_calls"] == 2
    assert trace["metrics"]["runtime_reportable"]
    assert trace["ablation"] == resolve_ablation(variant).document()
    assert json.loads(open(trace["trace_path"]).read())["ablation"] == trace["ablation"]
    verify_trajectory(trace, dict(trace, id="EXAMPLE", completed=True),
                      {"tools": Knowledge().catalog.tools})
    contexts = [p["context"] for p in client.contexts if "context" in p]
    if variant in {"wo-exp", "wo-all"}:
        assert trace["experiences"] == []
        assert all(c["experience"] == [] for c in contexts)
    else:
        assert trace["experiences"]
        assert any(c["experience"] for c in contexts)


def screening_hook(payload, action):
    if payload.get("stage") == "decompose":
        action["requirements"][0]["mode"] = "screen"
    if payload.get("stage") == "graph":
        plan = action["plan"]
        plan["nodes"][1]["when"] = {
            "op": "gt",
            "left": {"kind": "node", "node": "inverse", "path": ["condition_number"]},
            "right": {"kind": "literal", "value": 3},
            "evidence": "condition number exceeds 3",
        }
        child = deepcopy(plan["nodes"][1])
        child.pop("when")
        child["id"] = "downstream"
        child["arguments"]["right"] = {"kind": "node", "node": "check", "path": ["product"]}
        plan["nodes"].append(child)
        plan["deliverables"][0]["nodes"].append("downstream")
    if "finish" in action:
        # Eligibility does not change just because the ablation computed more.
        action["finish"]["product"] = []
    return action


def run_screen(tmp_path, variant, hook=screening_hook, invoke=fixture_invoke,
               condition="condition number exceeds 3"):
    knowledge = Knowledge()
    return run_scimas(
        public_example()["question"] + " Only check if " + condition + ".",
        catalog=knowledge.catalog, knowledge=knowledge, client=Client(hook),
        invoke=invoke, trace_dir=tmp_path, case_id="SCREEN", dataset="custom",
        inputs=public_example()["inputs"], scimas_ablation=variant,
    )


@pytest.mark.parametrize("variant", VARIANTS)
def test_screening_and_descendants_are_executed_only_when_disabled(tmp_path, variant):
    trace = run_screen(tmp_path, variant)
    assert trace["status"] == "completed", trace["failure_reason"]
    screened = resolve_ablation(variant).early_stop
    assert len(trace["calls"]) == (1 if screened else 3)
    assert set(trace["pruned"]) == ({"check", "downstream"} if screened else set())
    records = [g for g in trace["gate_evaluations"] if g["state"] is False]
    assert len(records) == 1
    assert records[0]["action"] == ("prune" if screened else "continue_without_screening")
    assert records[0]["source_observations"]["inverse"]
    assert trace["final_answer"]["product"] == []


def independent_hook(payload, action):
    if payload.get("stage") == "graph":
        plan = action["plan"]
        # Put a dependent before its parent to exercise topological ordering.
        independent = deepcopy(plan["nodes"][0])
        independent["id"] = "anchor"
        plan["nodes"] = [plan["nodes"][1], independent, plan["nodes"][0]]
        plan["deliverables"][0]["nodes"].append("anchor")
    return action


@pytest.mark.parametrize("variant", VARIANTS)
def test_actual_overlap_and_stable_serial_order(tmp_path, variant):
    parallel = resolve_ablation(variant).parallel
    lock, both_running = threading.Lock(), threading.Event()
    active, peak = 0, 0

    def invoke(name, args, **kwargs):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
            if active == 2:
                both_running.set()
        try:
            if parallel and name == "MatrixInverse":
                assert both_running.wait(3), "Independent calls did not overlap"
            time.sleep(0.01)
            return fixture_invoke(name, args, **kwargs)
        finally:
            with lock:
                active -= 1

    trace = run(tmp_path, Client(independent_hook), invoke=invoke, scimas_ablation=variant)
    assert trace["status"] == "completed", trace["failure_reason"]
    assert peak == (2 if parallel else 1)
    if not parallel:
        assert trace["limits"]["tool_concurrency"] == 1
        assert [s["node"] for s in trace["steps"] if s["type"] == "dispatch"] == [
            "anchor", "inverse", "check"
        ]


@pytest.mark.parametrize("variant", VARIANTS)
def test_nonretryable_failure_repairs_only_affected_branch_or_fails(tmp_path, variant):
    failed = False

    def plan(repaired=False):
        value = valid_plan()
        anchor = deepcopy(value["nodes"][0])
        anchor["id"] = "anchor"
        # Independent valid evidence must survive a later repair.
        anchor["arguments"]["values"] = {"kind": "literal", "value": [[1, 0], [0, 1]]}
        if repaired:
            value["nodes"][0]["purpose"] = "Retry corrected branch after injected failure"
        value["nodes"].insert(0, anchor)
        value["deliverables"][0]["nodes"].append("anchor")
        return value

    def hook(payload, action):
        ctx = payload.get("context", {})
        if payload.get("stage") == "graph":
            return {"plan": plan()}
        if ctx.get("stage") == "result" and ctx["structural_validation"] != "passed":
            return {"repair": {"nodes": [ctx["node"]], "reason": "Injected branch failure"}}
        if "request" in ctx:
            return {"plan": plan(True)}
        return action

    def invoke(name, args, **kwargs):
        nonlocal failed
        if name == "MatrixInverse" and args["values"][0][0] == 2 and not failed:
            failed = True
            return {"status": "error", "output": None, "error_type": "ValueError", "error": "Injected"}
        return fixture_invoke(name, args, **kwargs)

    trace = run(tmp_path, Client(hook), invoke=invoke, scimas_ablation=variant,
                config={"tool_concurrency": 1})
    if resolve_ablation(variant).local_repair:
        assert trace["status"] == "completed", trace["failure_reason"]
        assert len(trace["repairs"]) == 1
        assert trace["repairs"][0]["retained"] == ["anchor"]
        assert len([c for c in trace["calls"] if c["node"] == "anchor"]) == 1
    else:
        assert trace["status"] == "failed"
        assert "LocalRepairDisabled" in trace["failure_reason"]
        assert not trace["repairs"]
        assert not any(s.get("role") == "repair" for s in trace["steps"])
        assert len(trace["calls"]) == 2


@pytest.mark.parametrize("variant", ["wo-local-repair", "wo-all"])
@pytest.mark.parametrize("recovers", [True, False])
def test_transient_retry_is_preserved_and_exhaustion_fails(tmp_path, variant, recovers):
    attempts = 0

    def invoke(name, args, **kwargs):
        nonlocal attempts
        if name == "MatrixInverse":
            attempts += 1
            if attempts == 1 or not recovers:
                return {"status": "error", "output": None, "error_type": "Timeout"}
        return fixture_invoke(name, args, **kwargs)

    trace = run(tmp_path, invoke=invoke, scimas_ablation=variant)
    assert attempts == 2
    assert trace["status"] == ("completed" if recovers else "failed")
    assert len([s for s in trace["steps"] if s["type"] == "retry"]) == 1
    assert not trace["repairs"]
    if not recovers:
        assert "LocalRepairDisabled" in trace["failure_reason"]


def test_no_early_stop_still_requires_approved_resolvable_conditions_and_valid_inputs():
    catalog = Knowledge().catalog
    plan = screening_hook({"stage": "graph"}, {"plan": valid_plan()})["plan"]
    graph = TaskGraph.create(public_example(), [], plan, catalog, "custom")
    gates = {"check": graph.node_identity("check")}
    assert graph.ready({}, catalog, approved_gates=gates, early_stop=False) == ["inverse"]
    result = graph.accept_result("inverse", fixture_invoke("MatrixInverse", {}), catalog)
    results = {"inverse": result}
    assert not graph.ready(results, catalog, early_stop=False)  # Gate unapproved.
    assert graph.ready(results, catalog, approved_gates=gates, early_stop=False) == ["check"]
    # Invalid data cannot become usable by bypassing screening.
    results["inverse"]["output"]["inverse"] = "not a matrix"
    assert not graph.ready(results, catalog, approved_gates=gates, early_stop=False)


@pytest.mark.parametrize("variant", ["wo-local-repair", "wo-all"])
def test_reviewer_graph_repair_does_not_sneak_into_disabled_variant(tmp_path, variant):
    def hook(payload, action):
        if payload.get("context", {}).get("stage") == "graph":
            return {"repair": {"nodes": ["inverse"], "reason": "Graph correction required"}}
        return action
    trace = run(tmp_path, Client(hook), scimas_ablation=variant)
    assert "LocalRepairDisabled" in trace["failure_reason"]
    assert not trace["calls"] and not trace["repairs"]


def test_invalid_variant_and_wrong_baseline_rejected():
    with pytest.raises(ValueError, match="Unknown"):
        resolve_ablation("typo")
    with pytest.raises(ValueError, match="baseline=scimas"):
        runtime_options("react", "wo-exp")
    assert runtime_options("scimas", "wo-exp") == {"scimas_ablation": "wo-exp"}
    assert runtime_options("react") == {}


@pytest.mark.parametrize("variant", ["wo-early-stop", "wo-all"])
def test_disabling_screening_does_not_accept_failed_output(tmp_path, variant):
    def invoke(name, args, **kwargs):
        if name == "MatrixMultiply":
            return {"status": "success", "output": {"product": "corrupt"}}
        return fixture_invoke(name, args, **kwargs)
    trace = run_screen(tmp_path, variant, invoke=invoke)
    assert trace["status"] == "failed"
    assert "check" not in trace["results"]
    assert all(c["node"] != "downstream" for c in trace["calls"])


@pytest.mark.parametrize("variant", ["full", "wo-early-stop", "wo-all"])
def test_positive_gate_still_executes(tmp_path, variant):
    def hook(payload, action):
        action = screening_hook(payload, action)
        if payload.get("stage") == "graph":
            action["plan"]["nodes"][1]["when"]["op"] = "lt"
            action["plan"]["nodes"][1]["when"]["evidence"] = "condition number is less than 3"
        return action
    trace = run_screen(tmp_path, variant, hook, condition="condition number is less than 3")
    assert trace["status"] == "completed", trace["failure_reason"]
    assert len(trace["calls"]) == 3
    assert not trace["pruned"]
    assert any(g["state"] is True for g in trace["gate_evaluations"])


def parsed_args(monkeypatch, tmp_path, variant):
    import sys
    import cli
    from baselines.react import runner

    captured = []
    with monkeypatch.context() as patch:
        patch.setattr(sys, "argv", [
            "scitoolflow", "run", "--baseline", "scimas", "--scimas-ablation", variant,
            "--dataset", "mini", "--backend", "api", "--model", "test-no-network",
            "--concurrency", "2", "--output", str(tmp_path / "predictions.json"),
        ])
        patch.setattr(runner, "run_batch", captured.append)
        cli.main()
    return captured[0]


def test_cli_batch_metadata_and_variant_resume_isolation(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from baselines.react import runner
    from baselines.common.metrics import task_metrics

    args = parsed_args(monkeypatch, tmp_path, "wo-parallel")
    class MetadataClient:
        backend = "api"
        model = "test-no-network"
        def __init__(self, backend):
            pass
        def public_settings(self):
            return {"endpoint": "test-no-network", "sampling": {}}
        def close(self):
            pass

    jobs_seen = []
    def pool(jobs, worker, concurrency, progress, **kwargs):
        assert concurrency == 2
        for task_id, payload in jobs:
            jobs_seen.append(payload)
            yield task_id, {"ok": True, "result": {
                "id": task_id, "completed": False, "status": "failed",
                "metrics": task_metrics(None, None),
            }}

    monkeypatch.setattr(runner, "GenerationClient", MetadataClient)
    monkeypatch.setattr(runner, "load_environment", lambda: None)
    monkeypatch.setattr(runner, "actor_file_hashes", lambda *args: {})
    monkeypatch.setattr(runner, "load_dataset", lambda *args: SimpleNamespace(
        name="mini", select=lambda _: [{"id": "SMAS-0001"}]))
    monkeypatch.setattr(runner, "iter_tasks", pool)
    runner.run_batch(args)
    data = json.loads((tmp_path / "predictions.json").read_text())
    config = data["settings"]["scimas_execution"]
    assert config["variant"] == "wo-parallel" and not config["parallel"]
    assert config["config"]["tool_concurrency"] == 1
    assert data["settings"]["concurrency"] == 2
    assert jobs_seen[0][1]["scimas_ablation"] == "wo-parallel"
    args.resume = True
    runner.run_batch(args)  # Same variant can resume.
    args.scimas_ablation = "wo-exp"
    with pytest.raises(ValueError, match="settings changed"):
        runner.run_batch(args)


def test_worker_forwards_variant_and_records_prediction(tmp_path, monkeypatch):
    from baselines.react import runner
    import baselines.scimas.runtime as runtime

    args = parsed_args(monkeypatch, tmp_path, "wo-exp")
    public = public_example()
    public.update(files=[], answer_schema={"type": "object"})
    monkeypatch.setattr(runner, "load_environment", lambda: None)
    monkeypatch.setattr(runner, "load_agent_input", lambda *a: public)
    client = Client()
    client.close = lambda: None
    monkeypatch.setattr(runner, "GenerationClient", lambda *a: client)
    monkeypatch.setattr(runner, "execute", fixture_invoke)
    original = runtime.run_scimas
    variants = []
    def wrapped(*a, **kwargs):
        variants.append(kwargs["scimas_ablation"])
        return original(*a, **kwargs, knowledge=Knowledge())
    monkeypatch.setattr(runtime, "run_scimas", wrapped)
    # Put worker namespace writes inside pytest's temp tree.
    monkeypatch.setattr(runner, "project_root", lambda: tmp_path)
    monkeypatch.setattr(runner, "ToolCatalog", lambda *a: Knowledge().catalog)
    prediction = runner.run_task((public, vars(args), str(tmp_path / "predictions.json"), "test"))
    assert prediction["completed"], prediction["failure_reason"]
    assert variants == ["wo-exp"]
    assert prediction["ablation"]["variant"] == "wo-exp"
    trace = json.loads(open(prediction["trace_path"]).read())
    assert not trace["experiences"]
