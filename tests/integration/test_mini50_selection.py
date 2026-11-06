"""A fixed cost-saving selection must retain failures and grade exactly 50 IDs."""

from contextlib import redirect_stdout
from io import StringIO
import json
import random
import sys

import pytest

import cli
from scripts.benchmark.mini50 import build, draw, verify
from src.utils.paths import project_root
from tasks.assets import load_agent_input
from tasks.datasets import load_dataset
from baselines.scimas.ablation import VARIANTS

ROOT = project_root()


def test_fixed_selection_includes_all_started_conditions_and_reproduces_free_draw():
    result = verify(ROOT)
    sampling = json.loads((ROOT / "tasks/mini-50/sampling.json").read_text())
    evidence = json.loads((ROOT / "tasks/mini-50/inclusion_evidence.json").read_text())
    required = set().union(*(set(g["started_ids"]) for g in evidence["groups"]))
    recorded = set().union(*(set(g["recorded_ids"]) for g in evidence["groups"]))
    selected = set(result["selected_ids"])
    assert len(evidence["groups"]) == 6
    assert len(required) == 8 and recorded <= required <= selected
    assert len(selected) == 50
    pool = [tid for tid in sampling["population_ids"] if tid not in required]
    assert random.Random(sampling["seed"]).sample(pool, 42) == sampling["random_drawn_ids"]
    assert set(sampling["random_drawn_ids"]).isdisjoint(required)
    assert result["execution_dataset"] == "mini-100"
    assert not (ROOT / "tasks/mini-50/questions.jsonl").exists()
    for row in load_dataset("mini-100").select(result["selected_ids"]):
        load_agent_input(row, ROOT / "tasks/mini-100")


def test_draw_refuses_to_drop_started_tasks_or_admit_foreign_ids():
    population = [f"T-{i}" for i in range(100)]
    with pytest.raises(ValueError, match="Started IDs"):
        draw(population, population[:51])
    with pytest.raises(ValueError, match="Started IDs"):
        draw(population, ["foreign"])
    assert draw(population, population[:50])[2] == sorted(population[:50])


def test_frozen_selection_is_not_overwritten():
    path = ROOT / "tasks/mini-50/sampling.json"
    original = path.read_bytes()
    with pytest.raises(ValueError, match="already exists"):
        build("unused-suite.json", ROOT)
    assert path.read_bytes() == original


@pytest.mark.parametrize("baseline,variant", [
    *(('scimas', v) for v in VARIANTS), ('react', 'full'), ('scitoolagent', 'full')])
def test_same_public_run_and_score_interface_selects_50(monkeypatch, tmp_path, baseline, variant):
    ids = verify(ROOT)["selected_ids"]
    selected = ",".join(ids)
    captured = []
    monkeypatch.setattr("baselines.react.runner.run_batch", captured.append)
    monkeypatch.setattr(sys, "argv", ["cli.py", "run", "--dataset", "mini-100",
        "--baseline", baseline, "--scimas-ablation", variant, "--tasks", selected,
        "--backend", "api", "--output", str(tmp_path / "predictions.json")])
    cli.main()
    assert captured[0].dataset == "mini-100"
    assert captured[0].baseline == baseline
    assert len(load_dataset("mini-100").select(captured[0].tasks)) == 50
    monkeypatch.setattr("evaluation.runner.evaluate_package", lambda *a, **kw: captured.append(kw) or {"summary": {}})
    monkeypatch.setattr(sys, "argv", ["cli.py", "score", "--dataset", "mini-100", "--tasks", selected,
        "--predictions", "unused.json", "--output", str(tmp_path / "scores.json")])
    with redirect_stdout(StringIO()):
        cli.main()
    assert captured[-1]["dataset"] == "mini-100" and captured[-1]["task_ids"] == ids


@pytest.fixture(scope="module")
def references():
    from evaluation.suites.mini import load_references
    return load_references(ROOT, load_dataset("mini-100"))


@pytest.mark.parametrize("variant", VARIANTS)
def test_real_tools_and_authenticated_scoring_keep_the_50_task_denominator(monkeypatch, tmp_path, references, variant):
    from evaluation.suites import mini
    from tests.scimas.test_ablation_recording import execute_recording_control

    selected = verify(ROOT)["selected_ids"]
    assert "SMAS-0103" in selected
    folder = tmp_path / variant
    envelope, prediction, trace, table = execute_recording_control(
        monkeypatch, folder, variant, dataset_name="mini-100")
    assert prediction["completed"], prediction["failure_reason"]
    assert prediction["dataset"] == trace["dataset"] == "mini-100"
    assert prediction["metrics"] == trace["metrics"]
    metrics = prediction["metrics"]
    assert metrics["runtime_seconds"] > 0 and metrics["runtime_reportable"]
    assert metrics["scientific_tool_calls"] == 5
    assert metrics["input_tokens"] > 0 and metrics["output_tokens"] > 0
    assert table["tasks"][0]["input_tokens"] == metrics["input_tokens"]
    assert table["tasks"][0]["output_tokens"] == metrics["output_tokens"]
    monkeypatch.setattr(mini, "load_references", lambda *args: references)
    report = mini.evaluate(ROOT, folder / "predictions.json", folder / "scores.json",
                           task_ids=selected, dataset="mini-100")
    assert report["summary"]["tasks"] == 50
    assert {row["id"] for row in report["tasks"]} == set(selected)
    row = next(row for row in report["tasks"] if row["id"] == "SMAS-0103")
    assert row["evidence_integrity"]["verified"] and row["resource_policy_compliant"]
    assert row["runtime_completed"] and row["tool_plan_correct"] and row["answer_correct"]
    for metric in ["runtime_completion_rate", "tool_planning_accuracy", "answer_accuracy"]:
        assert report["summary"][metric] == pytest.approx(1 / 50)
    if variant == "full":
        main = mini.evaluate(ROOT, folder / "predictions.json", folder / "scores_main100.json",
                             dataset="mini-100")
        assert main["summary"]["tasks"] == 100
        for metric in ["runtime_completion_rate", "tool_planning_accuracy", "answer_accuracy"]:
            assert main["summary"][metric] == pytest.approx(1 / 100)


@pytest.mark.parametrize("baseline", ["react", "scitoolagent"])
def test_other_baselines_execute_real_tools_and_score_the_same_selection(monkeypatch, tmp_path, references, baseline):
    """Scripted decisions validate adapters/graders; no model API is invoked."""
    from argparse import Namespace
    import baselines.react.runner as batch
    import baselines.scitoolagent.runtime as kg_runtime
    from evaluation.suites import mini
    from tests.integration.test_mini_dataset import options
    from tools import execute

    folder = tmp_path / baseline
    selected = verify(ROOT)["selected_ids"]
    dataset = load_dataset("mini-100")
    public = load_agent_input(dataset.select("SMAS-0103")[0], dataset.asset_root)
    observed = []

    def invoke(name, arguments, **kwargs):
        result = execute(name, arguments, **kwargs)
        if name != "DescribeTools":
            assert result["status"] == "success", result
            observed.append(result["output"])
        return result

    class Client:
        backend = "api"
        model = "controlled-adapter-test-not-a-model-result"
        supports_response_schema = True

        def __init__(self, *args, **kwargs):
            self.turn = 0

        def public_settings(self):
            return {"endpoint": "http://localhost/controlled-test", "sampling": {}}

        def request(self, *args, **kwargs):
            if baseline == "scitoolagent" and self.turn == 0:
                decision = {"finish": {"plan": ["ParseJSONDocument"] + ["MatrixSVD"] * 4}}
            elif not observed:
                decision = {"actions": [{"tool": "ParseJSONDocument", "arguments": {
                    "json_file": public["inputs"]["channel_design_file"]}}]}
            elif len(observed) <= 4:
                records = observed[0]["document"]["data"]
                index = len(observed) - 1
                values = (records[index]["augmented_response_matrix"] if index < 3
                          else records[0]["augmented_response_matrix"][:2])
                decision = {"actions": [{"tool": "MatrixSVD", "arguments": {"values": values}}]}
            else:
                records = observed[0]["document"]["data"]
                minima = [min(result["singular_values"]) for result in observed[1:4]]
                best = max(minima)
                chosen = min((i for i, v in enumerate(minima) if abs(v - best) <= 1e-8),
                             key=lambda i: records[i]["record_id"])
                decision = {"finish": {"selected_channel_id": records[chosen]["record_id"],
                    "minimum_singular_value": minima[chosen],
                    "original_channels_identifiable": min(observed[4]["singular_values"]) > 1e-12}}
            self.turn += 1
            return {"text": json.dumps(decision), "usage": {"prompt_tokens": 11, "completion_tokens": 7}}

        def close(self):
            pass

    class Retriever:
        def __init__(self, *args, **kwargs):
            pass

        def retrieve(self, question, deadline):
            return {"tools": [{"name": name} for name in ["ParseJSONDocument", "MatrixSVD"]]}

    def inline_jobs(jobs, function, concurrency, on_active, should_schedule=None):
        for tid, payload in jobs:
            on_active([tid])
            yield tid, {"ok": True, "result": function(payload)}
        on_active([])

    args = options(monkeypatch, folder)
    args.update(baseline=baseline, dataset="mini-100", tasks="SMAS-0103",
                backend="api", model=Client.model, output=str(folder / "predictions.json"))
    monkeypatch.setattr(batch, "GenerationClient", Client)
    monkeypatch.setattr(batch, "execute", invoke)
    monkeypatch.setattr(batch, "iter_tasks", inline_jobs)
    monkeypatch.setattr(batch, "start_monitor", lambda *a, **kw: None)
    monkeypatch.setattr(kg_runtime, "GraphRetriever", Retriever)
    monkeypatch.setenv("SCITOOLFLOW_WORK_DIR", str(folder / "work"))
    monkeypatch.setenv("SCITOOLFLOW_ARTIFACTS_DIR", str(folder / "artifacts"))
    monkeypatch.setenv("SCITOOL_EMBEDDING_BACKEND", "api")
    batch.run_batch(Namespace(**args))
    envelope = json.loads((folder / "predictions.json").read_text())
    prediction = envelope["predictions"][0]
    assert prediction["completed"], prediction["failure_reason"]
    assert prediction["baseline"] == baseline and prediction["dataset"] == "mini-100"
    assert prediction["metrics"]["scientific_tool_calls"] == 5
    assert prediction["metrics"]["input_tokens"] > 0 and prediction["metrics"]["output_tokens"] > 0
    assert prediction["metrics"]["runtime_reportable"] and prediction["metrics"]["runtime_seconds"] > 0
    monkeypatch.setattr(mini, "load_references", lambda *args: references)
    for ids, denominator in [(selected, 50), (None, 100)]:
        report = mini.evaluate(ROOT, folder / "predictions.json", folder / f"scores_{denominator}.json",
                               task_ids=ids, dataset="mini-100")
        assert report["summary"]["tasks"] == denominator
        row = next(row for row in report["tasks"] if row["id"] == "SMAS-0103")
        assert row["evidence_integrity"]["verified"] and row["resource_policy_compliant"]
        assert row["runtime_completed"] and row["tool_plan_correct"] and row["answer_correct"]
        for metric in ["runtime_completion_rate", "tool_planning_accuracy", "answer_accuracy"]:
            assert report["summary"][metric] == pytest.approx(1 / denominator)
