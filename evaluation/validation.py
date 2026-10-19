"""Frozen benchmark, implementation and reference-integrity checks."""

from pathlib import Path
import hashlib, json, math, re
from scitoolflow.io import read_jsonl
from scitoolflow.benchmark.schema import validation_errors
from scitoolflow.benchmark.assets import load_agent_input
from .files import manifest, safe_file, normalizer
from .planning import budget_for
from .answer import resolve_candidates, path_candidates


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
    index = json.loads((root / "tasks/index.json").read_text())
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
                entry["max_tool_calls"],
                entry["has_files"],
            )
            != (
                task["id"],
                task["domain"],
                line,
                task["question"][:160],
                task["max_tool_calls"],
                bool(task.get("files")),
            )
            for line, (entry, task) in enumerate(zip(entries, tasks), 1)
        )
    ):
        raise ValueError(
            "Public task index differs from canonical tasks; run scripts/index_tasks.py"
        )
    by_id = {r["id"]: r for r in refs}
    catalog = json.loads((root / "tools/catalog.json").read_text())["tools"]
    from tools.catalog import ToolCatalog

    registry = ToolCatalog(root).registry()
    sources = {name: spec["source"] for name, spec in catalog.items()}
    if set(catalog) != set(registry["tools"]) or set(catalog) != set(sources):
        raise ValueError("Tool metadata coverage differs")
    if len(catalog) != 547 or catalog["DescribeTools"]["kind"] != "discovery":
        raise ValueError("Expected 546 scientific tools and DescribeTools")
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
        if task["max_tool_calls"] != budget_for(reference):
            raise ValueError("Call budget differs from policy")
        if "DescribeTools" in reference["tool_path"]:
            raise ValueError("Reference tool_path contains DescribeTools")
        load_agent_input(task, root / "tasks")
        for item in task.get("unit_annotations", []):
            if not resolve_candidates(reference["expected_answer"], [item["path"]])[0]:
                raise ValueError("Unresolvable unit annotation")
        for rule in reference["scoring"]["field_rules"]:
            if not resolve_candidates(
                reference["expected_answer"],
                path_candidates(rule.get("path", rule["field"])),
            )[0]:
                raise ValueError("Unresolvable scoring rule")
            if any(
                not math.isfinite(float(rule.get(k, 0))) or float(rule.get(k, 0)) < 0
                for k in ["atol", "rtol"]
            ):
                raise ValueError("Invalid tolerance")
        events = read_jsonl(safe_file(root, reference["reference_trace"]))
        observations = {
            e["observation_id"]: e for e in events if e.get("event") == "tool_result"
        }
        if len(observations) != sum(e.get("event") == "tool_result" for e in events):
            raise ValueError("Duplicate observation ID")
        if reference["tool_path"] != [
            observations[o]["tool"] for o in reference["necessary_observation_ids"]
        ]:
            raise ValueError("Reference path differs from actual evidence")
        for event in observations.values():
            count += 1
            if event.get("output") is None:
                raise ValueError("Missing reference output")
            encoded = (
                event["output"]
                if isinstance(event["output"], str)
                else json.dumps(
                    event["output"], sort_keys=True, ensure_ascii=False, allow_nan=False
                )
            )
            if (
                hashlib.sha256(encoded.encode()).hexdigest()
                != event["packaged_output_sha256"]
            ):
                raise ValueError("Reference output hash mismatch")
            if event["tool"] not in catalog or event["tool"] == "DescribeTools":
                raise ValueError("Invalid reference scientific tool")
            params = catalog[event["tool"]]["parameters"]
            required = {p["name"] for p in params if p.get("required")}
            declared = {p["name"] for p in params}
            if required - set(event["arguments"]) or set(event["arguments"]) - declared:
                raise ValueError(
                    "Historical invocation does not match declared parameter names"
                )
        positions = {name: i for i, name in enumerate(observations)}
        for edge in reference.get("dependency_graph", {}).get("edges", []):
            if edge["from"] not in positions or (
                edge["to"] != "final_answer"
                and (
                    edge["to"] not in positions
                    or positions[edge["from"]] >= positions[edge["to"]]
                )
            ):
                raise ValueError("Invalid evidence DAG")

        def citations(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key in {"evidence", "observation", "observations"} and any(
                        o not in observations
                        for o in re.findall(r"\bo\d{3}\b", json.dumps(child))
                    ):
                        raise ValueError("Dangling evidence citation")
                    citations(child)
            elif isinstance(value, list):
                for child in value:
                    citations(child)

        citations(reference["expected_answer"])
    normalizer(root)
    return {
        "package_valid": True,
        "public_tasks": len(tasks),
        "references": len(refs),
        "scientific_tools": 546,
        "discovery_tools": 1,
        "inline_outputs": count,
        "new_model_api_calls": 0,
    }
