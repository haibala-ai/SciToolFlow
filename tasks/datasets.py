"""Public dataset selection, task namespaces and Mini-to-full identity mapping."""

from dataclasses import dataclass
import csv
import hashlib
import json
from pathlib import Path

from src.utils.io import read_jsonl
from src.utils.paths import project_root

DATASETS = ("full", "mini")


def dataset_files(name):
    """Public files whose identities define a dataset; never read author notes."""
    if name not in DATASETS:
        raise ValueError("Unknown dataset: " + str(name))
    files = ["tasks/questions.jsonl"]
    if name == "mini":
        files.extend(
            [
                "tasks/mini/questions.jsonl",
                "tasks/mini/ids.tsv",
                "tasks/mini/metadata.json",
            ]
        )
    return files


def select_tasks(rows, selection="all"):
    """Interpret IDs only inside the selected dataset's public namespace."""
    if selection == "all" or selection is None:
        return list(rows)
    ids = (
        [part.strip() for part in selection.split(",")]
        if isinstance(selection, str)
        else list(selection)
    )
    by_id = {row["id"]: row for row in rows}
    if (
        not ids
        or any(not isinstance(tid, str) or not tid for tid in ids)
        or len(set(ids)) != len(ids)
        or set(ids) - set(by_id)
    ):
        raise ValueError(
            "Unknown, empty or duplicate task selection in selected dataset"
        )
    return [by_id[tid] for tid in ids]


@dataclass
class TaskDataset:
    name: str
    root: Path
    questions: list
    source_ids: dict

    @property
    def asset_root(self):
        return self.root / "tasks"

    def select(self, selection="all"):
        return select_tasks(self.questions, selection)

    def source_id(self, task_id):
        try:
            return self.source_ids[task_id]
        except KeyError as error:
            raise ValueError(
                "Unknown task in " + self.name + ": " + str(task_id)
            ) from error


def load_dataset(name="full", root=None):
    """Load agent-visible tasks, validating Mini's bijection and unchanged content."""
    dataset_files(name)
    root = Path(root or project_root()).resolve()
    full = read_jsonl(root / "tasks/questions.jsonl")
    by_source = {row["id"]: row for row in full}
    if len(by_source) != len(full):
        raise ValueError("Duplicate source task IDs")
    if name == "full":
        return TaskDataset(name, root, full, {tid: tid for tid in by_source})
    folder = root / "tasks/mini"
    metadata = json.loads((folder / "metadata.json").read_text())
    for filename in ("questions.jsonl", "ids.tsv"):
        if (
            hashlib.sha256((folder / filename).read_bytes()).hexdigest()
            != metadata["sha256"][filename]
        ):
            raise ValueError("Mini artifact hash mismatch: " + filename)
    questions = read_jsonl(folder / "questions.jsonl")
    with (folder / "ids.tsv").open(newline="") as stream:
        reader = csv.reader(stream, delimiter="\t")
        if next(reader, None) != ["mini_id", "full_id"]:
            raise ValueError("Mini ID mapping needs mini_id and full_id columns")
        pairs = list(reader)
    if any(len(row) != 2 for row in pairs):
        raise ValueError("Malformed Mini ID mapping")
    mapping = dict(pairs)
    expected_ids = [f"FLOW-{i:04d}" for i in range(1, len(questions) + 1)]
    if (
        not questions
        or metadata["tasks"] != len(questions)
        or [row["id"] for row in questions] != expected_ids
        or [row[0] for row in pairs] != expected_ids
        or len(mapping) != len(pairs)
        or len(set(mapping.values())) != len(pairs)
    ):
        raise ValueError("Mini requires contiguous IDs and a bijective source mapping")
    for question in questions:
        source_id = mapping[question["id"]]
        if source_id not in by_source:
            raise ValueError("Unknown full task in Mini mapping: " + source_id)
        if {**question, "id": source_id} != by_source[source_id]:
            raise ValueError(
                "Mini task differs from its source beyond ID: " + question["id"]
            )
    return TaskDataset(name, root, questions, mapping)
