"""Public Full/Mini dataset loading and source-identity mapping."""
from dataclasses import dataclass
import csv,hashlib,json
from pathlib import Path
from src.utils.io import read_jsonl
from src.utils.paths import project_root

DATASETS=("mini","full")
DEFAULT_DATASET="mini"


def dataset_files(name):
    """Public actor inputs only; authoring sources and private gold are excluded."""
    if name not in DATASETS:raise ValueError("Unknown dataset: "+str(name))
    if name=="mini":
        return ["tasks/mini/"+item for item in ["questions.jsonl","ids.tsv","metadata.json","asset_manifest.json"]]
    return ["tasks/full/questions.jsonl"]


def select_tasks(rows,selection="all"):
    if selection=="all" or selection is None:return list(rows)
    ids=[part.strip() for part in selection.split(",")] if isinstance(selection,str) else list(selection)
    by_id={row["id"]:row for row in rows}
    if not ids or any(not isinstance(tid,str) or not tid for tid in ids) or len(set(ids))!=len(ids) or set(ids)-set(by_id):
        raise ValueError("Unknown, empty or duplicate task selection in selected dataset")
    return [by_id[tid] for tid in ids]


@dataclass
class TaskDataset:
    name:str
    root:Path
    questions:list
    source_ids:dict
    @property
    def asset_root(self):return self.root/("tasks/mini" if self.name=="mini" else "tasks/full")
    def select(self,selection="all"):return select_tasks(self.questions,selection)
    def source_id(self,task_id):
        try:return self.source_ids[task_id]
        except KeyError as error:raise ValueError("Unknown task in "+self.name+": "+str(task_id)) from error


def load_dataset(name=DEFAULT_DATASET,root=None):
    """Load only public task data; Mini-200 is the default open interface."""
    dataset_files(name);root=Path(root or project_root()).resolve()
    if name=="mini":return _load_mini(root)
    questions=read_jsonl(root/"tasks/full/questions.jsonl");mapping={q["id"]:q["id"] for q in questions}
    if len(mapping)!=len(questions):raise ValueError("Duplicate source task IDs")
    return TaskDataset("full",root,questions,mapping)


def _load_mini(root):
    """Load only public files. Private references/selection notes are excluded."""
    folder = root / "tasks/mini"
    metadata = json.loads((folder / "metadata.json").read_text())
    for name in ["questions.jsonl", "ids.tsv", "asset_manifest.json", "schema.json"]:
        if hashlib.sha256((folder/name).read_bytes()).hexdigest() != metadata["sha256"][name]:
            raise ValueError("Mini artifact hash mismatch: " + name)
    questions = read_jsonl(folder / "questions.jsonl")
    with (folder / "ids.tsv").open(newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        if reader.fieldnames != ["mini_id", "origin", "source_id"]:
            raise ValueError("Invalid Mini source mapping columns")
        pairs = list(reader)
    expected = [f"SMAS-{i:04d}" for i in range(1, 201)]
    if (metadata.get("tasks") != 200 or [q["id"] for q in questions] != expected
        or [p["mini_id"] for p in pairs] != expected
        or len({p["source_id"] for p in pairs}) != 200):
        raise ValueError("Mini requires 200 aligned contiguous IDs and unique sources")
    for i,pair in enumerate(pairs):
        if i < 100:
            valid = pair["origin"] == "special100" and pair["source_id"] == expected[i]
        else:
            valid = pair["origin"] == "full" and pair["source_id"].startswith("FLOW-")
        if not valid:raise ValueError("Invalid Mini origin identity: " + pair["mini_id"])
    return TaskDataset("mini", root, questions, {p["mini_id"]:p["source_id"] for p in pairs})
