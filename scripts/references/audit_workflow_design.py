"""Inspect draft diversity and distinguish proposed from verified tool coverage.

This report is a design aid, not a scientific review or a reference generator.
Run from the project root with explicit draft public/hidden JSONL sources.
"""

import argparse
from collections import Counter, defaultdict
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from evaluation.integrity.traces import (
    canonical_sha256,
    execution_calls,
    read_trajectory,
)
from evaluation.integrity.reference import validate_workflow_reference
from evaluation.integrity.files import safe_file
from src.utils.io import read_jsonl


def rows(paths):
    result = {}
    for path in paths:
        for row in read_jsonl(path):
            if row["id"] in result:
                raise ValueError(f"Duplicate task ID: {row['id']}")
            result[row["id"]] = row
    return result


def question_shape(text):
    """Numerical substitutions are a review signal, never a uniqueness proof."""
    return re.sub(r"\b\d+(?:\.\d+)?\b", "<number>", text.casefold())


def current_scientific_identity(task, hidden, reference, project_root=ROOT):
    """Match current rules and declared input bytes without rebinding old runs."""
    rules_match = isinstance(hidden.get("evaluation"), dict) and canonical_sha256(
        hidden["evaluation"]
    ) == canonical_sha256(reference.get("evaluation"))
    expected = hidden.get("public_asset_sha256", {})
    declared = [Path(name).name for name in task.get("files", [])]
    if (
        not isinstance(expected, dict)
        or set(declared) != set(expected)
        or len(declared) != len(set(declared))
    ):
        return (
            rules_match,
            False,
            "Current declared files and byte-hash inventory differ",
        )
    provenance = reference.get("native_provenance", {})
    if "generation_manifest" not in provenance:
        return (
            rules_match,
            not expected,
            None if not expected else "No executed input-byte inventory",
        )
    try:
        manifest = provenance["generation_manifest"]
        if not isinstance(manifest, dict) or canonical_sha256(
            manifest
        ) != provenance.get("generation_manifest_sha256"):
            raise ValueError("Generation manifest hash differs")
        inventory = manifest["input_asset_sha256"]
        if not isinstance(inventory, dict):
            raise ValueError("Invalid executed input-byte inventory")
        by_name = {Path(name).name: value for name, value in inventory.items()}
        if len(by_name) != len(inventory):
            raise ValueError("Ambiguous executed input basename inventory")
        return rules_match, by_name == expected, None
    except (KeyError, ValueError, OSError, TypeError) as error:
        return rules_match, False, str(error)


def current_reference_rows(paths, public, hidden=None, project_root=ROOT):
    """Keep historical versions visible without borrowing their public identity.

    Public/hidden task inputs still reject duplicate IDs. Different archived
    reference versions may share an ID; only an exact public hash may enter
    current-draft coverage. Every version is separately checked by the staged
    reference validator, never silently rebound to a revised question.
    """
    selected, versions = {}, []
    for path in paths:
        for identity, reference in rows([path]).items():
            expected = (
                canonical_sha256(public[identity]) if identity in public else None
            )
            actual = (
                reference.get("native_provenance", {})
                .get("task_identity", {})
                .get("current_public_task_sha256")
            )
            public_matches = expected is not None and actual == expected
            rules_match, assets_match, identity_error = None, None, None
            if hidden is not None and identity in public:
                rules_match, assets_match, identity_error = current_scientific_identity(
                    public[identity], hidden.get(identity, {}), reference, project_root
                )
            matches = public_matches and (
                hidden is None or rules_match and assets_match
            )
            versions.append(
                {
                    "task_id": identity,
                    "reference_file": str(path),
                    "reference_public_sha256": actual,
                    "current_public_sha256": expected,
                    "matches_current_public_identity": public_matches,
                    "matches_current_evaluation_identity": rules_match,
                    "matches_current_input_asset_identity": assets_match,
                    "current_identity_error": identity_error,
                    "status": (
                        "eligible_for_current_validation"
                        if matches
                        else "historical_identity_only_not_current_coverage"
                    ),
                }
            )
            if matches:
                if identity in selected:
                    raise ValueError(
                        "Duplicate reference for exact current public identity: "
                        + identity
                    )
                selected[identity] = reference
    return selected, versions


def contains_selector(value, source):
    if isinstance(value, dict):
        return value.get("source") == source or any(
            contains_selector(item, source) for item in value.values()
        )
    if isinstance(value, list):
        return any(contains_selector(item, source) for item in value)
    return False


def has_handoff(node):
    """Both explicit bindings and scoped argument predicates encode handoffs."""
    for container in [node, *node.get("alternatives", [])]:
        if container.get("bindings"):
            return True
        for rule in container.get("input_rules", []):
            if (
                contains_selector(rule, "node")
                or contains_selector(rule, "node_arguments")
            ) and ("path" in rule or contains_selector(rule, "call_arguments")):
                return True
        # An output predicate may jointly verify the actual call arguments,
        # its outputs and a parent observation (for example fused projections).
        # An implicit output path alone is not evidence of an input handoff.
        for rule in container.get("output_rules", []):
            if contains_selector(rule, "call_arguments") and (
                contains_selector(rule, "node")
                or contains_selector(rule, "node_arguments")
            ):
                return True
    return False


def staged_reference_diagnostics(reference_paths, catalog, project_root=ROOT):
    """Report authentic candidate runs separately from current-draft coverage.

    A staged public task has portable asset URIs and a public answer-format
    contract. Later source edits can also change its identity. Do not bypass
    exact provenance validation or silently count it as the current release.
    """
    accepted, issues, tool_tasks = {}, [], defaultdict(set)
    for path in reference_paths:
        public_path = path.parent.parent / "tasks/questions.jsonl"
        if not public_path.exists():
            issues.append(
                {"reference_file": str(path), "issue": "no_staged_public_tasks"}
            )
            continue
        public = rows([public_path])
        for identity, reference in rows([path]).items():
            try:
                validate_workflow_reference(
                    project_root, public[identity], reference, catalog["tools"], catalog
                )
                trace = read_trajectory(project_root / reference["reference_trace"])
                actual = execution_calls(trace)
                accepted.setdefault(identity, []).append(str(path))
                for call in actual:
                    if call["status"] == "success":
                        if call["tool"] not in catalog["tools"]:
                            raise KeyError(call["tool"])
                        if call["tool"] != "DescribeTools":
                            tool_tasks[call["tool"]].add(identity)
            except (KeyError, ValueError, OSError, TypeError) as exc:
                issues.append(
                    {
                        "task_id": identity,
                        "reference_file": str(path),
                        "issue": str(exc),
                    }
                )
    return {
        "scope": (
            "Independently reviewed native candidates validated against their own "
            "staged public identity; these are not current-draft or final-release coverage. "
            "No provenance mismatch is waived."
        ),
        "distinct_task_count": len(accepted),
        "validated_reference_versions": sum(len(paths) for paths in accepted.values()),
        "tasks": accepted,
        "successful_scientific_tool_tasks": {
            k: sorted(v) for k, v in sorted(tool_tasks.items())
        },
        "validation_issues": issues,
    }


def analyze(public, hidden, catalog, references=None, project_root=ROOT):
    proposed = defaultdict(set)
    verified = defaultdict(set)
    families = defaultdict(list)
    issues = []
    reference_issues = []
    verified_tasks = {}
    tools = catalog["tools"]
    scientific = {n: s for n, s in tools.items() if n != "DescribeTools"}
    for task_id, task in public.items():
        spec = hidden.get(task_id)
        if not spec:
            issues.append({"task_id": task_id, "issue": "missing_hidden_design"})
            continue
        families[spec.get("family_id", "unannotated")].append(task_id)
        nodes = spec.get("evaluation", {}).get("nodes", [])
        declared = spec.get("capability_coverage")
        actual_tools = sorted(
            {
                name
                for node in nodes
                for option in node.get("alternatives", [])
                for name in option.get("tools", [])
            }
        )
        if declared is not None and declared != actual_tools:
            issues.append(
                {
                    "task_id": task_id,
                    "issue": "stale_derived_tool_inventory",
                    "declared": declared,
                    "current_workflow_tools": actual_tools,
                }
            )
        for node in nodes:
            for option in node.get("alternatives", []):
                for name in option["tools"]:
                    if name not in scientific:
                        issues.append(
                            {
                                "task_id": task_id,
                                "issue": "unregistered_or_discovery_alternative",
                                "tool": name,
                            }
                        )
                    proposed[name].add(task_id)
        if not any(has_handoff(node) for node in nodes):
            issues.append(
                {
                    "task_id": task_id,
                    "issue": "no_declared_observation_to_argument_handoff",
                }
            )
        if len(nodes) < 2:
            issues.append(
                {"task_id": task_id, "issue": "single_stage_workflow_requires_review"}
            )
        if not spec.get("strategy_difference"):
            issues.append(
                {"task_id": task_id, "issue": "missing_specific_strategy_difference"}
            )
        leaked = [
            n
            for n in tools
            if re.search(
                r"(?<![A-Za-z0-9_])" + re.escape(n) + r"(?![A-Za-z0-9_])",
                task["question"],
            )
        ]
        if leaked:
            issues.append(
                {
                    "task_id": task_id,
                    "issue": "question_names_registered_tools",
                    "tools": leaked,
                }
            )
    duplicate_signals = []
    for family, ids in families.items():
        for index, left in enumerate(ids):
            for right in ids[index + 1 :]:
                a = question_shape(public[left]["question"])
                b = question_shape(public[right]["question"])
                ratio = SequenceMatcher(None, a, b, autojunk=False).ratio()
                if ratio >= 0.92:
                    duplicate_signals.append(
                        {
                            "family_id": family,
                            "tasks": [left, right],
                            "question_shape_similarity": round(ratio, 4),
                            "status": "requires_semantic_review_not_automatic_rejection",
                        }
                    )
    for task_id, ref in (references or {}).items():
        try:
            if task_id not in public:
                raise ValueError("Reference has no corresponding public task")
            rules_match, assets_match, error = current_scientific_identity(
                public[task_id], hidden[task_id], ref, project_root
            )
            if not rules_match or not assets_match:
                raise ValueError(
                    "Reference differs from current rules/input bytes: " + str(error)
                )
            validate_workflow_reference(
                project_root, public[task_id], ref, tools, catalog
            )
            trace = read_trajectory(project_root / ref["reference_trace"])
            actual_calls = execution_calls(trace)
            verified_tasks[task_id] = {
                "scientific_calls": sum(c["tool"] in scientific for c in actual_calls),
                "successful_tools": sorted(
                    {
                        c["tool"]
                        for c in actual_calls
                        if c["status"] == "success" and c["tool"] in scientific
                    }
                ),
            }
            for call in actual_calls:
                if call["status"] == "success" and call["tool"] in scientific:
                    verified[call["tool"]].add(task_id)
        except (KeyError, ValueError, OSError, TypeError) as exc:
            reference_issues.append({"task_id": task_id, "issue": str(exc)})
    domains = sorted({s["domain"] for s in scientific.values()})
    coverage = {}
    for domain in domains:
        registered = {n for n, s in scientific.items() if s["domain"] == domain}
        actual = registered & verified.keys()
        possible = registered & proposed.keys()
        coverage[domain] = {
            "registered_scientific_tools": len(registered),
            "proposed_alternative_tools": len(possible),
            "verified_native_reference_tools": len(actual),
            "verified_coverage_fraction": (
                len(actual) / len(registered) if registered else 0
            ),
        }
    per_tool = {}
    for name, spec in sorted(scientific.items()):
        per_tool[name] = {
            "domain": spec["domain"],
            "proposed_task_ids": sorted(proposed[name]),
            "verified_reference_task_ids": sorted(verified[name]),
            "status": (
                "verified_reference_use"
                if verified[name]
                else (
                    "proposed_not_verified"
                    if proposed[name]
                    else "not_covered_by_current_draft"
                )
            ),
            "uncovered_reason": (
                None
                if verified[name]
                else (
                    "Awaiting accepted native reference; an alternative in a design is not evidence of execution."
                    if proposed[name]
                    else "No reviewed scientific use in the current draft. Domain eligibility/exclusion has not yet been individually assessed."
                )
            ),
        }
    cross_domain = defaultdict(Counter)
    for task_id, evidence in verified_tasks.items():
        for name in evidence["successful_tools"]:
            cross_domain[public[task_id]["domain"]][scientific[name]["domain"]] += 1
    return {
        "schema_version": "scitoolflow.design-audit.v1",
        "status": "draft_diagnostics_not_release_acceptance",
        "target_tasks": 500,
        "public_tasks": len(public),
        "hidden_designs": len(hidden),
        "task_shortfall": max(0, 500 - len(public)),
        "tasks_by_domain": dict(Counter(r["domain"] for r in public.values())),
        "families": {k: v for k, v in sorted(families.items())},
        "coverage_by_tool_discipline": coverage,
        "verified_reference_tasks": len(verified_tasks),
        "verified_task_scientific_call_distribution": dict(
            sorted(
                Counter(t["scientific_calls"] for t in verified_tasks.values()).items()
            )
        ),
        "verified_task_unique_tool_distribution": dict(
            sorted(
                Counter(
                    len(t["successful_tools"]) for t in verified_tasks.values()
                ).items()
            )
        ),
        "verified_cross_discipline_tool_task_incidences": {
            k: dict(v) for k, v in sorted(cross_domain.items())
        },
        "coverage_definition": "Unique registered scientific tool names; DescribeTools excluded. Proposed alternatives are separate from successful calls in references passing native provenance, second review and self-scoring validation. Coverage is diagnostic and grants no task score.",
        "design_issues": issues,
        "potential_duplicate_pairs": duplicate_signals,
        "reference_validation_issues": reference_issues,
        "tools": per_tool,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public", nargs="+", type=Path, required=True)
    parser.add_argument("--hidden", nargs="+", type=Path, required=True)
    parser.add_argument("--references", nargs="*", type=Path, default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    catalog = json.loads((ROOT / "tools/catalog/catalog.json").read_text())
    public = rows(args.public)
    hidden = rows(args.hidden)
    current_references, identity_versions = current_reference_rows(
        args.references, public, hidden
    )
    report = analyze(public, hidden, catalog, current_references)
    report["reference_identity_versions"] = identity_versions
    report["reviewed_staged_candidates"] = staged_reference_diagnostics(
        args.references, catalog
    )
    report["input_sha256"] = {
        str(p): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in args.public + args.hidden + args.references
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: report[k]
                for k in [
                    "public_tasks",
                    "task_shortfall",
                    "tasks_by_domain",
                    "coverage_by_tool_discipline",
                ]
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
