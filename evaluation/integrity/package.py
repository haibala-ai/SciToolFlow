"""Frozen benchmark, implementation and reference-integrity checks."""

from pathlib import Path
from collections import Counter
import hashlib, json
from src.utils.io import read_jsonl
from tasks.schema import validation_errors
from tasks.assets import load_agent_input
from evaluation.integrity.files import manifest, safe_file, verify_file_identities
from tools.catalog.counts import tool_counts


def validate_tool_counts(metadata, catalog):
    """Require the complete current release-count contract."""
    counts = tool_counts(catalog)
    for key, actual in counts.items():
        if type(metadata.get(key)) is not int or metadata[key] != actual:
            raise ValueError("MANIFEST tool count missing or different: " + key)
    describe = catalog.get("DescribeTools")
    if not describe or describe.get("domain") != "General":
        raise ValueError("DescribeTools must be a registered General tool")
    if any(
        describe.get("indexing", {}).get(index, False)
        for index in ("graph", "embedding")
    ):
        raise ValueError(
            "DescribeTools must be excluded from graph and embedding indexes"
        )
    return counts


def validate_unit_annotations(task, answer):
    """Resolve field annotations; preserve explicit task-wide description notes.

    A description-only object documents the complete task's units or model
    scope. It makes no claim about a particular answer field. Every annotation
    containing field metadata still needs an exact, resolvable path.
    """
    from evaluation.workflow.values import pointer, MissingEvidence

    for annotation in task.get("unit_annotations", []):
        try:
            if not isinstance(annotation, dict):
                raise ValueError("Unit annotation must be an object")
            if set(annotation) == {"description"}:
                description = annotation["description"]
                if not isinstance(description, str) or not description.strip():
                    raise ValueError("Task-wide unit description must be nonempty")
                continue
            path = annotation.get("path")
            if isinstance(path, str):
                pointer(answer, path)
            elif isinstance(path, list) and all(type(k) in (str, int) for k in path):
                value = answer
                for key in path:
                    if isinstance(value, list) and (type(key) is not int or key < 0):
                        raise ValueError(
                            "Array paths require nonnegative integer indices"
                        )
                    value = value[key]
            else:
                raise ValueError("Unit annotation needs an explicit path")
        except (KeyError, IndexError, TypeError, ValueError, MissingEvidence) as error:
            raise ValueError("Unresolvable unit annotation") from error


def validate_package(root):
    root = Path(root).resolve()
    metadata = manifest(root)
    for name, expected in metadata["files"].items():
        if hashlib.sha256(safe_file(root, name).read_bytes()).hexdigest() != expected:
            raise ValueError("Hash mismatch: " + name)
    tasks = read_jsonl(root / metadata["public_tasks"])
    refs = read_jsonl(root / metadata["references"])
    if (
        len(tasks) != 500
        or len(refs) != 500
        or len({r["id"] for r in tasks}) != 500
        or {r["id"] for r in tasks} != {r["id"] for r in refs}
    ):
        raise ValueError("Expected 500 aligned unique public tasks and references")
    index = json.loads((root / "tasks/full/index.json").read_text())
    entries = index["tasks"]
    if (
        index["count"] != len(tasks)
        or len(entries) != len(tasks)
        or any(
            (
                entry["id"],
                entry["domain"],
                entry["line"],
                entry["question_preview"],
                entry["has_files"],
            )
            != (
                task["id"],
                task["domain"],
                line,
                task["question"][:160],
                bool(task.get("files")),
            )
            for line, (entry, task) in enumerate(zip(entries, tasks), 1)
        )
    ):
        raise ValueError(
            "Public task index differs from canonical tasks; run scripts/benchmark/index_tasks.py"
        )
    by_id = {r["id"]: r for r in refs}
    categories = Counter(entry.get("category") for entry in entries)
    declared = json.loads((root / "tasks/full/metadata.json").read_text())["task_categories"]
    if dict(categories) != declared or index.get("categories") != declared:
        raise ValueError("Task category counts differ from task metadata/index")
    catalog = json.loads((root / "tools/catalog/catalog.json").read_text())["tools"]
    from tools.catalog import ToolCatalog

    registry = ToolCatalog(root).registry()
    sources = {name: spec["source"] for name, spec in catalog.items()}
    if set(catalog) != set(registry["tools"]) or set(catalog) != set(sources):
        raise ValueError("Tool metadata coverage differs")
    counts = validate_tool_counts(metadata, catalog)
    for name, spec in catalog.items():
        if not all(
            spec.get(k)
            for k in [
                "description",
                "call_signature",
                "output_description",
                "output_schema",
                "returns",
            ]
        ):
            raise ValueError("Incomplete documentation: " + name)
        if any(
            not p.get("description") or not p.get("type") for p in spec["parameters"]
        ):
            raise ValueError("Missing parameter documentation: " + name)
        source = sources[name]
        if (
            hashlib.sha256(safe_file(root, source["file"]).read_bytes()).hexdigest()
            != source["sha256"]
        ):
            raise ValueError("Implementation hash mismatch: " + name)
    from evaluation.workflow import SCHEMA_VERSION

    versions = {r.get("evaluation", {}).get("schema_version") for r in refs}
    if versions != {SCHEMA_VERSION}:
        raise ValueError("Mixed or unsupported evaluation schemas in task release")
    count = 0
    for task in tasks:
        reference = by_id[task["id"]]
        if (
            task["question"] != reference["question"]
            or task["inputs"] != reference["inputs"]
        ):
            raise ValueError("Public task/reference drift")
        if task["answer_schema"] != reference["answer_contract"] or validation_errors(
            reference["expected_answer"], task["answer_schema"]
        ):
            raise ValueError("Invalid answer contract")
        load_agent_input(task, root / "tasks/full")
        validate_unit_annotations(task, reference["expected_answer"])
        from evaluation.integrity.reference import validate_workflow_reference

        count += validate_workflow_reference(root, task, reference, catalog, registry)
    verify_file_identities(root)
    datasets = {"full": len(tasks)}
    if (root / "tasks/mini/metadata.json").is_file():
        from evaluation.integrity.mini import validate_mini
        mini = validate_mini(root)
        datasets["mini"] = mini["tasks"]
    default_dataset = "mini" if "mini" in datasets else "full"
    return {
        "package_valid": True,
        "default_dataset": default_dataset,
        "public_tasks": datasets[default_dataset],
        "references": mini["references"] if default_dataset == "mini" else len(refs),
        "source_tasks": len(tasks),
        "source_references": len(refs),
        "datasets": datasets,
        **counts,
        "inline_outputs": count,
        "new_model_api_calls": 0,
    }
