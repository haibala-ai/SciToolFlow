"""Offline, per-record evidence/contract audit; never execute scientific tools or models.

Passing these checks establishes internal consistency, not scientific truth. Content
reviews and independent recalculations are separate, attributable inputs to the report.
"""

import argparse
import ast
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evaluation.answer import (
    expand_leaves,
    field_paths,
    resolve_candidates,
    path_candidates,
    score_answer,
)
from scitoolflow.benchmark.schema import validation_errors


def load_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def digest(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def nodes(value, path=()):
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from nodes(child, path + (str(key),))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from nodes(child, path + (str(index),))


def decoded(value):
    if not isinstance(value, str):
        return value
    for parser in [json.loads, ast.literal_eval]:
        try:
            return parser(value)
        except (ValueError, SyntaxError, TypeError):
            pass
    return value


def check_task(task, reference, catalog):
    identifier = task["id"]
    issues = []
    checks = {}

    def check(name, valid, detail=None):
        checks[name] = bool(valid)
        if not valid:
            issues.append({"code": name, "severity": "error", "detail": detail})

    check(
        "question_inputs_match_reference",
        task["question"] == reference["question"]
        and task["inputs"] == reference["inputs"],
    )
    check(
        "public_contract_matches_private",
        task["answer_schema"] == reference["answer_contract"],
    )
    check(
        "legacy_input_matches_public", json.loads(task["Parameter"]) == task["inputs"]
    )
    check(
        "gold_matches_final_json",
        decoded(reference["final_answer"]) == reference["expected_answer"],
    )
    schema_errors = validation_errors(
        reference["expected_answer"], task["answer_schema"]
    )
    check("gold_satisfies_public_schema", not schema_errors, schema_errors)
    check(
        "gold_has_no_nonfinite_number",
        all(
            math.isfinite(v)
            for _, v in nodes(reference["expected_answer"])
            if type(v) in (int, float)
        ),
    )
    events = load_rows(ROOT / reference["reference_trace"])
    calls = [event for event in events if event.get("event") == "tool_result"]
    ids = [event["observation_id"] for event in calls]
    check("unique_reference_observation_ids", len(ids) == len(set(ids)))
    necessary = reference.get("necessary_observation_ids", ids)
    check("necessary_observations_present", set(necessary).issubset(ids))
    expected_calls = [event for event in calls if event["observation_id"] in necessary]
    check(
        "reference_path_matches_necessary_evidence",
        reference["tool_path"] == [event["tool"] for event in expected_calls],
    )
    check(
        "reference_path_excludes_discovery",
        "DescribeTools" not in reference["tool_path"],
    )
    check(
        "reference_fits_scientific_budget",
        len(reference["tool_path"]) <= task["max_tool_calls"],
    )
    bad_args, bad_hashes, unknown, unsuccessful = [], [], [], []
    for event in calls:
        name = catalog.get("aliases", {}).get(event["tool"], event["tool"])
        spec = catalog["tools"].get(name)
        if spec is None:
            unknown.append(event["tool"])
        else:
            errors = validation_errors(event["arguments"], spec["input_schema"])
            if errors:
                bad_args.append(
                    {
                        "observation_id": event["observation_id"],
                        "tool": name,
                        "errors": errors,
                    }
                )
        if event.get("status") != "success":
            unsuccessful.append(event["observation_id"])
        value = event.get("output")
        encoding = event.get("packaged_output_encoding")
        if encoding == "utf8_text" and isinstance(value, str):
            raw = value.encode("utf-8")
        elif encoding == "canonical_json_utf8":
            raw = json.dumps(
                value, ensure_ascii=False, sort_keys=True, allow_nan=False
            ).encode("utf-8")
        else:
            raw = None
        if raw is None or hashlib.sha256(raw).hexdigest() != event.get(
            "packaged_output_sha256"
        ):
            bad_hashes.append(event["observation_id"])
    check("reference_tools_registered", not unknown, unknown)
    check("reference_arguments_match_current_contracts", not bad_args, bad_args)
    check("reference_outputs_hash_verified", not bad_hashes, bad_hashes)
    failed_required = sorted(set(unsuccessful) & set(necessary))
    check(
        "necessary_measurement_observations_successful",
        not failed_required,
        failed_required,
    )
    if unsuccessful:
        issues.append(
            {
                "code": "archived_failed_supporting_attempts",
                "severity": "information",
                "detail": unsuccessful,
            }
        )
    graph = reference.get("dependency_graph", {})
    index = {name: pos for pos, name in enumerate(ids)}
    bad_edges = [
        edge
        for edge in graph.get("edges", [])
        if edge.get("from") not in index
        or (
            edge.get("to") != "final_answer"
            and (
                edge.get("to") not in index
                or index.get(edge.get("from"), 1) >= index.get(edge.get("to"), 0)
            )
        )
    ]
    check("dependency_edges_topologically_valid", not bad_edges, bad_edges)
    rules = field_paths(reference)
    unresolved = []
    covered = set()
    for entry in rules:
        rule = entry["rule"]
        path = rule.get("path", rule.get("field", ""))
        found, value, parts = resolve_candidates(
            reference["expected_answer"], path_candidates(path)
        )
        if not found:
            unresolved.append(path)
        else:
            covered.update(
                tuple(leaf["parts"])
                for leaf in expand_leaves(value, parts)
                if leaf["kind"] != "length"
            )
    check("scoring_paths_resolvable", not unresolved, unresolved)
    scored = score_answer(reference, reference["expected_answer"])
    check("gold_self_score_consistent", scored["status"] == "passed", scored["status"])
    metadata_keys = {
        "evidence",
        "observations",
        "observation",
        "observation_id",
        "provenance",
        "task",
        "task_id",
        "failures_worked_around",
    }
    required_leaves = {
        path
        for path, value in nodes(reference["expected_answer"])
        if not isinstance(value, (dict, list))
        and path
        and not any(key in metadata_keys for key in path)
    }
    unscored = sorted(".".join(path) for path in required_leaves - covered)
    if unscored:
        issues.append(
            {
                "code": "gold_fields_outside_scoring_rules",
                "severity": "review",
                "detail": unscored,
            }
        )
    gold_nodes = list(nodes(reference["expected_answer"]))
    strings = [(path, value) for path, value in gold_nodes if isinstance(value, str)]
    private_paths = [
        ".".join(path)
        for path, _ in gold_nodes
        if path and path[-1] == "review_artifact_manifest"
    ]
    volatile = [
        ".".join(path)
        for path, _ in gold_nodes
        if path
        and path[-1]
        in {
            "fetched_at_utc",
            "retrieved_at_utc",
            "retrieval_timestamp",
            "cached_at",
            "cache_timestamp",
        }
    ]
    operational = [
        ".".join(path)
        for path, _ in gold_nodes
        if path
        and path[-1]
        in {
            "calls_used",
            "total_tool_calls",
            "tool_calls_used",
            "tool_call_count",
            "tool_call_summary",
            "call_summary",
            "tool_call_summary",
            "failure_worked_around",
            "failures_worked_around",
            "failures_or_workarounds",
        }
    ]
    if private_paths:
        issues.append(
            {
                "code": "review_bookkeeping_in_scientific_answer",
                "severity": "confirmed_contract_issue",
                "detail": private_paths,
            }
        )
    if volatile:
        issues.append(
            {
                "code": "retrieval_timestamp_in_archival_answer",
                "severity": "review",
                "detail": volatile,
            }
        )
    if operational:
        issues.append(
            {
                "code": "run_specific_bookkeeping_in_answer",
                "severity": "review",
                "detail": operational,
            }
        )
    unknown_booleans = []

    def inspect_schema(schema, path=()):
        if schema.get("type") == "boolean" and any(
            word in ".".join(path).lower()
            for word in ["available", "established", "membership", "supported"]
        ):
            unknown_booleans.append(".".join(path))
        for key, child in schema.get("properties", {}).items():
            inspect_schema(child, path + (key,))
        if isinstance(schema.get("items"), dict):
            inspect_schema(schema["items"], path + ("[]",))

    inspect_schema(task["answer_schema"])
    tools = reference["tool_path"]
    invariance_tools = sorted(
        set(tools)
        & {
            "PrincipalComponentProjection",
            "KMeansClustering",
            "DBSCANClustering",
            "SymmetricEigenDecomposition",
            "MatrixSVD",
        }
    )
    if invariance_tools:
        issues.append(
            {
                "code": "mathematical_representation_equivalence",
                "severity": (
                    "information"
                    if reference.get("scoring", {}).get("mathematical_equivalence")
                    else "review"
                ),
                "detail": invariance_tools,
                "joint_verification_policy_enabled": bool(
                    reference.get("scoring", {}).get("mathematical_equivalence")
                ),
            }
        )
    leaves = [
        (path, value)
        for path, value in gold_nodes
        if not isinstance(value, (dict, list))
    ]
    return {
        "id": identifier,
        "domain": task["domain"],
        "task_sha256": digest(task),
        "reference_sha256": digest(reference),
        "checks": checks,
        "issues": issues,
        "reference_calls": len(tools),
        "scientific_budget": task["max_tool_calls"],
        "reference_tools": tools,
        "answer_leaf_count": len(leaves),
        "answer_text_characters": len(
            json.dumps(reference["expected_answer"], ensure_ascii=False)
        ),
        "answer_max_depth": max(len(path) for path, _ in gold_nodes),
        "answer_prose_leaves": len(strings),
        "required_boolean_unknown_candidates": unknown_booleans,
        "independent_scientific_verification": "not_implied_by_static_checks",
        "live_tool_execution_in_this_audit": False,
        "llm_success_used_as_task_quality_criterion": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "results/reports/full_run_audit_20261018/task_audit.json",
    )
    args = parser.parse_args()
    tasks = load_rows(ROOT / "tasks/questions.jsonl")
    references = {
        row["id"]: row for row in load_rows(ROOT / "evaluation/references.jsonl")
    }
    catalog = json.loads((ROOT / "tools/catalog.json").read_text())
    details = [check_task(task, references[task["id"]], catalog) for task in tasks]
    report = {
        "scope": "all public task records; offline contract, evidence and scoring consistency",
        "count": len(details),
        "checks": {
            key: sum(row["checks"][key] for row in details)
            for key in details[0]["checks"]
        },
        "issue_counts": dict(
            Counter(issue["code"] for row in details for issue in row["issues"])
        ),
        "scientific_truth_certified": False,
        "tasks": details,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {key: value for key, value in report.items() if key != "tasks"},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
