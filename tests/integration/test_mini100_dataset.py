"""Frozen uniform subset, independent input assets and shared execution/scoring."""

from contextlib import redirect_stdout
import hashlib
from io import StringIO
import json
from pathlib import Path
import random
import shutil
import sys

import pytest

import cli
from tasks.assets import load_agent_input
from tasks.datasets import DATASETS, dataset_files, load_dataset
from src.utils.paths import project_root
from evaluation.suites import mini
from evaluation.integrity.traces import verify_release_envelope
from baselines.scimas.ablation import VARIANTS
from tests.scimas.test_ablation_recording import execute_recording_control

ROOT = project_root()


def test_frozen_draw_has_no_stratification_and_preserves_all_selected_public_rows():
    parent, subset = load_dataset("mini"), load_dataset("mini-100")
    sampling = json.loads((subset.asset_root / "sampling.json").read_text())
    drawn = random.Random(20261106).sample([q["id"] for q in parent.questions], 100)
    assert sampling["drawn_ids"] == drawn
    assert sampling["seed"] == 20261106 and sampling["draws_performed"] == 1
    assert sampling["stratified"] is False
    assert len(subset.questions) == len(set(drawn)) == 100
    assert [q["id"] for q in subset.questions] == sorted(drawn)
    by_id = {q["id"]: q for q in parent.questions}
    for q in subset.questions:
        assert q == by_id[q["id"]]
        assert subset.source_id(q["id"]) == parent.source_id(q["id"])
        load_agent_input(q, subset.asset_root)
    assert sampling["parent_questions_sha256"] == hashlib.sha256((parent.asset_root / "questions.jsonl").read_bytes()).hexdigest()
    assert "sampling.json" in {Path(p).name for p in dataset_files("mini-100")}
    excluded = next(q["id"] for q in parent.questions if q["id"] not in set(drawn))
    with pytest.raises(ValueError, match="Unknown"):
        subset.select(excluded)


def test_sampling_command_refuses_to_overwrite_the_frozen_release():
    from scripts.benchmark.mini100 import build

    metadata = ROOT / "tasks/mini-100/metadata.json"
    before = metadata.read_bytes()
    with pytest.raises(ValueError, match="already exists"):
        build(ROOT, seed=0)
    assert metadata.read_bytes() == before


def test_subset_public_loading_does_not_need_parent_or_private_data(tmp_path, monkeypatch):
    source = ROOT / "tasks/mini-100"
    target = tmp_path / "tasks/mini-100"
    target.mkdir(parents=True)
    for name in ["questions.jsonl", "metadata.json", "ids.tsv", "schema.json", "asset_manifest.json", "sampling.json"]:
        shutil.copyfile(source / name, target / name)
    shutil.copytree(source / "assets", target / "assets")
    original = Path.open

    def guarded(path, *args, **kwargs):
        if "evaluation" in path.parts or path.name == "selection.json":
            raise AssertionError("Public loader read private grading data")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    subset = load_dataset("mini-100", tmp_path)
    assert len(subset.questions) == 100
    for q in subset.questions:
        public = load_agent_input(q, subset.asset_root)
        assert all(Path(p.removeprefix("qchem:")).is_file() for p in public["files"])


def test_reference_relocation_preserves_scientific_criteria_provenance_and_trace_bytes():
    parent = load_dataset("mini")
    subset = load_dataset("mini-100")
    parent_sources, _ = mini.load_references(ROOT, parent)
    sources, views = mini.load_references(ROOT, subset)
    assert len(sources) == len(views) == 100
    for q in subset.questions:
        sid = subset.source_id(q["id"])
        source, original = sources[sid], parent_sources[sid]
        assert {k:v for k,v in source.items() if k != "reference_trace"} == {k:v for k,v in original.items() if k != "reference_trace"}
        assert (ROOT / source["reference_trace"]).read_bytes() == (ROOT / original["reference_trace"]).read_bytes()
        assert source["id"] == sid
        assert source["native_provenance"]["generation_manifest"]["task_id"] == sid


@pytest.mark.parametrize("baseline", ["react", "scitoolagent", "scimas"])
@pytest.mark.parametrize("backend", ["api", "vllm", "local"])
def test_cli_accepts_subset_for_every_baseline_and_backend(monkeypatch, baseline, backend, tmp_path):
    captured = []
    monkeypatch.setattr("baselines.react.runner.run_batch", captured.append)
    monkeypatch.setattr(sys, "argv", ["cli.py", "run", "--dataset", "mini-100", "--baseline", baseline,
        "--backend", backend, "--tasks", "SMAS-0103", "--output", str(tmp_path / "predictions.json")])
    cli.main()
    assert captured[0].dataset == "mini-100" and captured[0].baseline == baseline
    monkeypatch.setattr("evaluation.runner.evaluate_package", lambda *args, **kwargs: captured.append(kwargs) or {"summary": {}})
    monkeypatch.setattr(sys, "argv", ["cli.py", "score", "--dataset", "mini-100", "--tasks", "SMAS-0103",
        "--predictions", "unused.json", "--output", str(tmp_path / "scores.json")])
    with redirect_stdout(StringIO()):
        cli.main()
    assert captured[-1]["dataset"] == "mini-100" and captured[-1]["task_ids"] == ["SMAS-0103"]


@pytest.mark.parametrize("command", ["task", "plan"])
def test_subset_task_and_planning_entrypoints(monkeypatch, tmp_path, command):
    if command == "task":
        monkeypatch.setattr(sys, "argv", ["cli.py", "task", "SMAS-0103", "--dataset", "mini-100"])
        output = StringIO()
        with redirect_stdout(output):
            cli.main()
        assert json.loads(output.getvalue())["id"] == "SMAS-0103"
    else:
        captured = []
        monkeypatch.setattr("baselines.scimas.runner.run_planning", lambda args: captured.append(args) or {"planned": 1, "failed": 0})
        monkeypatch.setattr(sys, "argv", ["cli.py", "plan", "--tasks", "SMAS-0103", "--dataset", "mini-100", "--output", str(tmp_path)])
        with redirect_stdout(StringIO()):
            cli.main()
        assert captured[0].dataset == "mini-100"


@pytest.fixture(scope="module")
def subset_references():
    return mini.load_references(ROOT, load_dataset("mini-100"))


@pytest.mark.parametrize("variant", VARIANTS)
def test_every_ablation_executes_real_subset_tools_and_scores(monkeypatch, tmp_path, subset_references, variant):
    envelope, prediction, trace, table = execute_recording_control(
        monkeypatch, tmp_path / variant, variant, dataset_name="mini-100")
    assert prediction["completed"], prediction["failure_reason"]
    assert prediction["dataset"] == trace["dataset"] == table["dataset"] == "mini-100"
    assert prediction["metrics"] == trace["metrics"]
    assert prediction["metrics"]["scientific_tool_calls"] == 5
    assert trace["planning"]["graph"]["dataset"] == "mini-100"
    for call in prediction["calls"]:
        if call["tool"] == "ParseJSONDocument":
            assert Path(call["arguments"]["json_file"]).parent == ROOT / "tasks/mini-100/assets"
    # Public input, actor source, trace and resource validation remain enabled.
    monkeypatch.setattr(mini, "load_references", lambda *args: subset_references)
    report = mini.evaluate(ROOT, tmp_path / variant / "predictions.json", tmp_path / variant / "scores.json",
                           task_ids=["SMAS-0103"], dataset="mini-100")
    assert report["dataset"] == report["summary"]["dataset"] == "mini-100"
    assert report["summary"]["tasks"] == 1
    assert all(report["summary"][k] == 1 for k in ["runtime_completion_rate", "tool_planning_accuracy", "answer_accuracy"])
    assert report["tasks"][0]["evidence_integrity"]["verified"]
    assert report["tasks"][0]["resource_policy_compliant"]
    with pytest.raises(ValueError, match="differs"):
        verify_release_envelope(envelope, ROOT, dataset="mini")
    if variant == "full":
        empty = {**envelope, "predictions": []}
        empty_path = tmp_path / "empty.json"
        empty_path.write_text(json.dumps(empty))
        missing = mini.evaluate(ROOT, empty_path, tmp_path / "missing.json", dataset="mini-100")
        assert missing["summary"]["tasks"] == 100
        assert missing["summary"]["runtime_completion_rate"] == 0
