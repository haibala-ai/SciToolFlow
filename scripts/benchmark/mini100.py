"""Freeze one uniform, non-stratified 100-task draw from the current Mini-200."""

import argparse
from collections import Counter
from copy import deepcopy
import csv
import gzip
import hashlib
import json
from pathlib import Path
import random
import shutil
import sys
import tempfile

from src.utils.io import atomic_json, read_jsonl
from src.utils.paths import project_root
from tasks.datasets import load_dataset

DEFAULT_SEED = 20261106


def asset_names(task):
    found = set()

    def visit(value):
        if isinstance(value, str) and value.startswith(("asset://", "qchem:asset://")):
            name = value.split("asset://", 1)[1]
            if Path(name).name != name:
                raise ValueError("Unsafe task asset name")
            found.add(name)
        elif isinstance(value, list):
            for item in value:
                visit(item)
        elif isinstance(value, dict):
            for item in value.values():
                visit(item)

    visit(task["inputs"])
    visit(task.get("files", []))
    return found


def build(root=None, seed=DEFAULT_SEED):
    root = Path(root or project_root()).resolve()
    parent = load_dataset("mini", root)
    source = parent.asset_root
    target = root / "tasks/mini-100"
    if target.exists():
        raise ValueError("Mini-100 already exists; its frozen sample will not be overwritten")
    if type(seed) is not int:
        raise ValueError("Sampling seed must be an integer")
    population = [q["id"] for q in parent.questions]
    drawn = random.Random(seed).sample(population, 100)
    chosen = set(drawn)
    questions = [q for q in parent.questions if q["id"] in chosen]
    with (source / "ids.tsv").open(newline="") as stream:
        mappings = [row for row in csv.DictReader(stream, delimiter="\t") if row["mini_id"] in chosen]
    parent_meta = json.loads((source / "metadata.json").read_text())
    # The parent private reference and selection must belong to its release.
    for name in ["evaluation/references.jsonl.gz", "selection.json"]:
        if hashlib.sha256((source / name).read_bytes()).hexdigest() != parent_meta["sha256"][name]:
            raise ValueError("Parent Mini private artifact hash mismatch: " + name)
    references = {r["id"]: r for r in read_jsonl(source / parent_meta["references"])}
    reviews = json.loads((source / "selection.json").read_text())["tasks_review"]
    inventory = json.loads((source / "asset_manifest.json").read_text())["files"]
    domains = dict(Counter(q["domain"] for q in questions))
    with tempfile.TemporaryDirectory(prefix=".mini100-", dir=root / "tasks") as temp:
        stage = Path(temp) / "mini-100"
        (stage / "assets").mkdir(parents=True)
        (stage / "evaluation/trajectories").mkdir(parents=True)
        lines = (source / "questions.jsonl").read_text().splitlines()
        (stage / "questions.jsonl").write_text("\n".join(
            line for line in lines if json.loads(line)["id"] in chosen) + "\n")
        (stage / "ids.tsv").write_text("mini_id\torigin\tsource_id\n" + "".join(
            "\t".join(row[k] for k in ["mini_id", "origin", "source_id"]) + "\n" for row in mappings))
        (stage / "ids.txt").write_text("".join(q["id"] + "\n" for q in questions))
        schema = json.loads((source / "schema.json").read_text())
        schema["title"] = "SciToolFlow Mini-100 public task"
        atomic_json(stage / "schema.json", schema)
        names = set.union(*(asset_names(q) for q in questions))
        for name in list(names):
            companion = Path(name).with_suffix(".provenance.json").name
            if companion in inventory:
                names.add(companion)
        for name in sorted(names):
            original = source / "assets" / name
            if hashlib.sha256(original.read_bytes()).hexdigest() != inventory[name]["sha256"]:
                raise ValueError("Parent Mini attachment hash mismatch: " + name)
            shutil.copyfile(original, stage / "assets" / name)
        atomic_json(stage / "asset_manifest.json", {"files": {n: inventory[n] for n in sorted(names)}})
        selected_references = []
        for row in mappings:
            ref = deepcopy(references[row["source_id"]])
            original = root / ref["reference_trace"]
            filename = row["source_id"] + ".json.gz"
            destination = stage / "evaluation/trajectories" / filename
            if original.suffix == ".gz":
                shutil.copyfile(original, destination)
            else:
                destination.write_bytes(gzip.compress(original.read_bytes(), mtime=0))
            ref["reference_trace"] = "tasks/mini-100/evaluation/trajectories/" + filename
            selected_references.append(ref)
        raw = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in selected_references).encode()
        (stage / "evaluation/references.jsonl.gz").write_bytes(gzip.compress(raw, mtime=0))
        atomic_json(stage / "selection.json", {
            "schema_version": "scitoolflow.mini.random_subset.selection.v1",
            "dataset": "mini-100", "tasks": 100,
            "tasks_review": [r for r in reviews if r["id"] in chosen],
        })
        atomic_json(stage / "sampling.json", {
            "schema_version": "scitoolflow.random_subset.v1", "parent_dataset": "mini",
            "parent_questions_sha256": hashlib.sha256((source / "questions.jsonl").read_bytes()).hexdigest(),
            "parent_metadata_sha256": hashlib.sha256((source / "metadata.json").read_bytes()).hexdigest(),
            "method": "uniform_without_replacement", "stratified": False,
            "seed": seed, "algorithm": "random.Random(seed).sample(population_ids, 100)",
            "python_version": sys.version.split()[0], "draws_performed": 1,
            "population_ids": population, "drawn_ids": drawn,
            "stored_ids": [q["id"] for q in questions], "domains": domains,
        })
        identities = {str(p.relative_to(stage)): hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in sorted(stage.rglob("*")) if p.is_file()}
        atomic_json(stage / "metadata.json", {
            "schema_version": "scitoolflow.mini_subset.v1", "name": "SciToolFlow Mini-100",
            "dataset": "mini-100", "tasks": 100, "parent_dataset": "mini",
            "selected_ids": [q["id"] for q in questions], "sampling_seed": seed,
            "domains": domains, "origins": dict(Counter(r["origin"] for r in mappings)),
            "references": "evaluation/references.jsonl.gz",
            "reference_identity": "Unchanged original source IDs and raw trace bytes; only reference file locations are relocated",
            "primary_metrics": parent_meta["primary_metrics"],
            "metric_definition_version": "independent-runtime-answer.v2",
            "parent_questions_sha256": hashlib.sha256((source / "questions.jsonl").read_bytes()).hexdigest(),
            "parent_metadata_sha256": hashlib.sha256((source / "metadata.json").read_bytes()).hexdigest(),
            "sha256": identities,
        })
        stage.rename(target)
    return {"dataset": "mini-100", "tasks": 100, "seed": seed, "domains": domains,
            "folder": str(target), "new_model_requests": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()
    print(json.dumps(build(seed=args.seed), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
