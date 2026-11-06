"""Freeze a 50-task Mini-100 selection while retaining every started task.

Mini-50 is an explicit selection within Mini-100, not a relabelled dataset.
The shared run/score interface keeps dataset and trace identities intact.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import tempfile

from src.utils.io import atomic_json
from src.utils.paths import project_root
from tasks.datasets import load_dataset

DEFAULT_SEED = 2026110602
VARIANTS = {"full", "wo-exp", "wo-parallel", "wo-early-stop", "wo-local-repair", "wo-all"}


def draw(population, required, seed=DEFAULT_SEED):
    """Uniformly sample the free slots, without outcome-based replacement."""
    if type(seed) is not int or len(population) != 100 or len(set(population)) != 100:
        raise ValueError("Expected an integer seed and 100 unique parent IDs")
    required = sorted(set(required))
    if len(required) > 50 or not set(required) <= set(population):
        raise ValueError("Started IDs must belong to Mini-100 and fit within 50 slots")
    remaining = [tid for tid in population if tid not in required]
    sampled = random.Random(seed).sample(remaining, 50 - len(required))
    return required, sampled, sorted(required + sampled)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def started_tasks(suite_file):
    """Include failed and suspended work as well as completed predictions."""
    suite_file = Path(suite_file).resolve()
    suite = json.loads(suite_file.read_text())
    if set(suite["groups"]) != VARIANTS:
        raise ValueError("A six-condition suite is required")
    required, receipts = set(), []
    for variant, group in suite["groups"].items():
        folder = Path(group["directory"])
        checkpoint = folder / "predictions.json"
        predictions = json.loads(checkpoint.read_text())["predictions"]
        progress = json.loads((folder / "progress.json").read_text())
        ids = {row["id"] for row in predictions}
        ids.update(progress.get("active_tasks", []))
        ids.update(progress.get("suspended_tasks", []))
        traces = []
        for path in sorted((folder / "trajectories").glob("*/trajectory.json")):
            trace = json.loads(path.read_text())
            tid = trace["task_id"]
            ids.add(tid)
            traces.append({"id": tid, "file": str(path.relative_to(folder)),
                           "sha256": digest(path), "status": trace["status"]})
        required.update(ids)
        receipts.append({"variant": variant, "execution_dataset": group["dataset"],
                         "started_ids": sorted(ids), "recorded_ids": [r["id"] for r in predictions],
                         "prediction_sha256": digest(checkpoint), "traces": traces})
    return suite, sorted(required), receipts


def build(suite_file, root=None, seed=DEFAULT_SEED):
    root = Path(root or project_root()).resolve()
    target = root / "tasks/mini-50"
    if target.exists():
        raise ValueError("Mini-50 already exists; the frozen selection will not be overwritten")
    parent = load_dataset("mini-100", root)
    population = [q["id"] for q in parent.questions]
    suite, required, receipts = started_tasks(suite_file)
    required, sampled, selected = draw(population, required, seed)
    # Match the public release that generated the paid attempts before selecting.
    old_parent = Path(suite["source_root"]) / "tasks/mini-100/questions.jsonl"
    parent_questions = parent.asset_root / "questions.jsonl"
    if digest(old_parent) != digest(parent_questions):
        raise ValueError("The paid suite and current Mini-100 public tasks differ")
    rows = {q["id"]: q for q in parent.questions}
    with tempfile.TemporaryDirectory(prefix=".mini50-", dir=root / "tasks") as temp:
        stage = Path(temp) / "mini-50"
        stage.mkdir()
        (stage / "ids.txt").write_text("".join(tid + "\n" for tid in selected))
        source_lines = (parent.asset_root / "ids.tsv").read_text().splitlines()
        (stage / "ids.tsv").write_text("\n".join([source_lines[0]] + [
            line for line in source_lines[1:] if line.split("\t")[0] in selected]) + "\n")
        atomic_json(stage / "sampling.json", {
            "schema_version": "scitoolflow.constrained_random_selection.v1",
            "name": "Mini-50", "execution_dataset": "mini-100", "tasks": 50,
            "parent_questions_sha256": digest(parent_questions),
            "parent_metadata_sha256": digest(parent.asset_root / "metadata.json"),
            "population_ids": population, "required_ids": required,
            "required_reason": "All started tasks in the six conditions, regardless of outcome",
            "method": "required_started_plus_uniform_without_replacement",
            "seed": seed, "draws_performed": 1, "stratified": False,
            "random_drawn_ids": sampled, "selected_ids": selected,
            "algorithm": "required_ids + random.Random(seed).sample(remaining_parent_ids, 50-len(required_ids))",
            "domains": dict(Counter(rows[tid]["domain"] for tid in selected)),
        })
        atomic_json(stage / "inclusion_evidence.json", {
            "source_suite": suite["experiment_id"], "actor_commit": suite["actor_commit"],
            "suite_sha256": digest(suite_file), "groups": receipts,
            "note": "Receipts fix inclusion only. They do not certify compatibility with a repaired actor or turn interrupted traces into completed runs.",
        })
        atomic_json(stage / "metadata.json", {
            "name": "SciMas Mini-50 ablation selection", "execution_dataset": "mini-100",
            "tasks": 50, "required_tasks": len(required), "randomly_sampled_tasks": len(sampled),
            "sha256": {p.name: digest(p) for p in sorted(stage.iterdir())},
            "assets_and_grading": "Shared from tasks/mini-100; no task, answer, asset or trace relabelling",
        })
        stage.rename(target)
    return verify(root)


def verify(root=None):
    root = Path(root or project_root()).resolve()
    folder = root / "tasks/mini-50"
    metadata = json.loads((folder / "metadata.json").read_text())
    for name, expected in metadata["sha256"].items():
        if Path(name).name != name or digest(folder / name) != expected:
            raise ValueError("Mini-50 artifact hash mismatch: " + name)
    sampling = json.loads((folder / "sampling.json").read_text())
    parent = load_dataset("mini-100", root)
    if (sampling["parent_questions_sha256"] != digest(parent.asset_root / "questions.jsonl")
            or sampling["parent_metadata_sha256"] != digest(parent.asset_root / "metadata.json")
            or sampling["population_ids"] != [q["id"] for q in parent.questions]):
        raise ValueError("Mini-50 parent release changed")
    required, sampled, selected = draw(sampling["population_ids"], sampling["required_ids"], sampling["seed"])
    receipts = json.loads((folder / "inclusion_evidence.json").read_text())["groups"]
    included = set().union(*(set(row["started_ids"]) for row in receipts))
    if any(not (set(row["recorded_ids"]) | {t["id"] for t in row["traces"]}) <= set(row["started_ids"])
           for row in receipts):
        raise ValueError("Mini-50 inclusion evidence omits recorded or traced work")
    if (set(row["variant"] for row in receipts) != VARIANTS or included != set(required)
            or sampled != sampling["random_drawn_ids"] or selected != sampling["selected_ids"]
            or (folder / "ids.txt").read_text().splitlines() != selected
            or sampling["method"] != "required_started_plus_uniform_without_replacement"
            or sampling["draws_performed"] != 1 or sampling["stratified"] is not False):
        raise ValueError("Mini-50 selection does not reproduce its six-condition inclusion record")
    rows = parent.select(selected)
    mapping = (parent.asset_root / "ids.tsv").read_text().splitlines()
    expected_mapping = [mapping[0]] + [line for line in mapping[1:] if line.split("\t")[0] in selected]
    if ((folder / "ids.tsv").read_text().splitlines() != expected_mapping
            or sampling["domains"] != dict(Counter(q["domain"] for q in rows))):
        raise ValueError("Mini-50 source mapping or domain counts differ from the parent")
    return {"selection": "mini-50", "execution_dataset": "mini-100", "tasks": len(selected),
            "required_tasks": len(required), "randomly_sampled_tasks": len(sampled),
            "seed": sampling["seed"], "domains": sampling["domains"],
            "selected_ids": selected, "status": "passed", "new_model_requests": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--print-tasks", action="store_true")
    args = parser.parse_args()
    if args.verify or args.print_tasks:
        result = verify()
    elif args.suite:
        result = build(args.suite, seed=args.seed)
    else:
        parser.error("Use --suite to freeze a selection, or --verify / --print-tasks")
    print(",".join(result["selected_ids"]) if args.print_tasks else json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
