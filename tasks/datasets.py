"""Public dataset loading, frozen random subsets and scientific source identity."""

import csv
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from src.utils.io import read_jsonl
from src.utils.paths import project_root

MINI_DATASETS = ("mini", "mini-100")
DATASETS = (*MINI_DATASETS, "full")
DEFAULT_DATASET = "mini"


def dataset_files(name):
    """Actor dependencies contain public inputs, never grading or selection notes."""
    if name not in DATASETS:
        raise ValueError("Unknown dataset: " + str(name))
    if name in MINI_DATASETS:
        files = ["questions.jsonl", "ids.tsv", "metadata.json", "asset_manifest.json"]
        if name == "mini-100":
            files.append("sampling.json")
        return ["tasks/" + name + "/" + item for item in files]
    return ["tasks/full/questions.jsonl"]


def select_tasks(rows, selection="all"):
    if selection == "all" or selection is None:
        return list(rows)
    ids = ([part.strip() for part in selection.split(",")]
           if isinstance(selection, str) else list(selection))
    by_id = {row["id"]: row for row in rows}
    if (not ids or any(not isinstance(tid, str) or not tid for tid in ids)
            or len(ids) != len(set(ids)) or set(ids) - set(by_id)):
        raise ValueError("Unknown, empty or duplicate task selection in selected dataset")
    return [by_id[tid] for tid in ids]


@dataclass
class TaskDataset:
    name: str
    root: Path
    questions: list
    source_ids: dict

    @property
    def asset_root(self):
        return self.root / "tasks" / self.name

    def select(self, selection="all"):
        return select_tasks(self.questions, selection)

    def source_id(self, task_id):
        try:
            return self.source_ids[task_id]
        except KeyError as error:
            raise ValueError("Unknown task in " + self.name + ": " + str(task_id)) from error


def load_dataset(name=DEFAULT_DATASET, root=None):
    """Load public task data only. The default remains Mini-200."""
    dataset_files(name)
    root = Path(root or project_root()).resolve()
    if name in MINI_DATASETS:
        return _load_mini(root, name)
    questions = read_jsonl(root / "tasks/full/questions.jsonl")
    mapping = {q["id"]: q["id"] for q in questions}
    if len(mapping) != len(questions):
        raise ValueError("Duplicate source task IDs")
    return TaskDataset("full", root, questions, mapping)


def _load_mini(root, name="mini"):
    """Validate a public Mini snapshot without reading private grader material."""
    folder = root / "tasks" / name
    metadata = json.loads((folder / "metadata.json").read_text())
    files = ["questions.jsonl", "ids.tsv", "asset_manifest.json", "schema.json"]
    if name == "mini-100":
        files.append("sampling.json")
    for item in files:
        if hashlib.sha256((folder / item).read_bytes()).hexdigest() != metadata["sha256"][item]:
            raise ValueError(name + " artifact hash mismatch: " + item)
    questions = read_jsonl(folder / "questions.jsonl")
    with (folder / "ids.tsv").open(newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        if reader.fieldnames != ["mini_id", "origin", "source_id"]:
            raise ValueError("Invalid Mini source mapping columns")
        pairs = list(reader)
    population = [f"SMAS-{i:04d}" for i in range(1, 201)]
    if name == "mini":
        expected, count = population, 200
    else:
        count = 100
        expected = metadata.get("selected_ids", [])
        sampling = json.loads((folder / "sampling.json").read_text())
        drawn = sampling.get("drawn_ids", [])
        if (len(expected) != count or len(set(expected)) != count
                or expected != sorted(expected) or not set(expected) <= set(population)
                or sampling.get("parent_dataset") != "mini"
                or sampling.get("population_ids") != population
                or len(drawn) != count or len(set(drawn)) != count
                or sorted(drawn) != expected):
            raise ValueError("Mini-100 requires 100 unique sampled Mini-200 IDs")
    if (metadata.get("dataset") != name or metadata.get("tasks") != count
            or [q["id"] for q in questions] != expected
            or [p["mini_id"] for p in pairs] != expected
            or len({p["source_id"] for p in pairs}) != count):
        raise ValueError(name + " requires aligned public IDs and unique scientific sources")
    for pair in pairs:
        tid = pair["mini_id"]
        if int(tid.split("-")[1]) <= 100:
            valid = pair["origin"] == "special100" and pair["source_id"] == tid
        else:
            valid = pair["origin"] == "full" and pair["source_id"].startswith("FLOW-")
        if not valid:
            raise ValueError("Invalid Mini origin identity: " + tid)
    return TaskDataset(name, root, questions, {p["mini_id"]: p["source_id"] for p in pairs})
