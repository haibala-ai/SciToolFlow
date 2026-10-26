"""Index related-task review candidates after a shared problem is discovered.

Patterns are review triggers, not verdicts. Exact row order, units, full records,
or one particular scientific method may be appropriate in an individual task.
This index never changes criteria, approves a task, or replaces a native review.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from evaluation.integrity.traces import canonical_sha256

COMPUTED = {
    "add",
    "subtract",
    "multiply",
    "divide",
    "sum",
    "mean",
    "min",
    "max",
    "exponential",
    "natural_log",
    "average_ranks",
}
RECORD_TOOLS = {
    "AggregateRecordGroups",
    "ExtractNumericVector",
    "ExtractNumericMatrix",
    "JoinRecordTables",
    "FilterRecords",
    "SummarizeNumericTable",
}
METHOD_TOOLS = {
    "MatrixMultiply",
    "MatrixSVD",
    "PolynomialLeastSquaresFit",
    "LinearLeastSquares",
    "NormalizeNumericRows",
    "GetStructureInfo",
    "InterpolateLinear",
}
PATTERNS = {
    "numeric_source_choice_with_tolerance": {
        "observed_incident": "FLOW-0205: a nearby number absent from the supplied positive settings could pass as the selected setting under a generic continuous tolerance.",
        "review": "Decide whether the numeric field selects a supplied source setting or estimates a continuous optimum. Preserve exact source identity for a selection, with an explicit public candidate contract; do not force genuinely continuous estimates onto a discrete grid.",
    },
    "selected_label_and_continuous_result_association": {
        "observed_incident": "FLOW-0201: the tolerance around the selected y-axis ratio also admitted the distinct z-axis result under the same y label.",
        "review": "Independently compute scientifically relevant competing label-value pairs and compare their separation with the public reporting accuracy. Test a correct label with another candidate's value. Tighten only justified numerical reporting precision; do not imply unjustified experimental accuracy or reject legitimate atomic-weight conventions.",
    },
    "ratio_and_amount_basis": {
        "observed_incident": "FLOW-0185: a common cell-versus-atom heat-capacity error can cancel in a ratio, concealing the wrong absolute prediction.",
        "review": "Check the scientific target, complete mode/cell/mass/unit basis and absolute quantities when they are part of that target. Explicit common-scale or sign cancellation, as in0205, can be a valid invariant and is not itself a defect. Test consistent coordinate conversion against a one-sided unreconciled conversion; never require an unsupported absolute physical value merely to lengthen the answer.",
    },
    "numeric_tolerance_on_public_integer_answer": {
        "observed_incident": "FLOW-0435: fractional day counts could satisfy a generic numeric tolerance in standalone scientific scoring despite the public integer contract.",
        "review": "Follow the public answer schema to every numeric target leaf. Counts and discrete model identities declared integer must be exact; do not tighten unrelated continuous quantities merely because their current expected value happens to be an integer. This is a contract check, not independent verification of the target count.",
    },
    "short_required_scientific_path": {
        "observed_incident": "FLOW-0421 has a correct source read plus one correlation call, but scientific correctness alone does not establish enough orchestration challenge for the final workflow-focused task mix.",
        "review": "Inspect actual scientific selection, conditional reasoning and data preparation. A source read plus one statistic may be shallow, whereas a raw missing-data table can require substantial valid cohort construction even if preparation wrappers are optional. Do not force useless tool calls or automatically reject by path length.",
    },
    "optional_node_required_by_outcome": {
        "observed_incident": "FLOW-0440: the generic author helper copied optional preparation nodes into every outcome's mandatory evidence list, rejecting sufficient statistics without redundant wrappers.",
        "review": "Inspect each optional node directly required by an outcome. Distinguish optional exploration from genuine necessary evidence, branch-specific evidence and alternative routes. Assign outcome evidence to scientific dependencies; do not simply delete all optional-node links or waive required observations.",
    },
    "named_tool_in_public_question": {
        "observed_incident": "Tool-selection tasks can accidentally prescribe an API name instead of stating a scientific goal.",
        "review": "Read the full task. Distinguish a scientifically specified reproducible protocol from an unnecessary prescribed tool chain. A name match is a review trigger, not proof of leakage or a bad task.",
    },
    "derived_tool_inventory_mismatch": {
        "observed_incident": "Late addition of legitimate equivalent routes left28 stored capability inventories stale.",
        "review": "Derive the inventory from current nodes and distinguish declared alternatives from tools actually executed. Inventory synchronization never proves source validity, tool success or task acceptance.",
    },
    "literal_intermediate_column_name": {
        "observed_incident": "FLOW-0301: correct source-grounded plant changes were rejected because the caller named the derived column change rather than delta.",
        "review": "Distinguish source-defined column identifiers from caller-created intermediate names. For derived columns, bind the argument-selected column to complete source-grounded values and pair/group identities. Never waive source field or identity requirements merely because names are flexible.",
    },
    "computed_equality_without_tolerance": {
        "observed_incident": "FLOW-0388: associated sums for the same evidence mass differed in the last floating-point bit.",
        "review": "Recompute actual equivalent orders and inspect physical scale; retain exact IDs/integers and task-specific scientific tolerances. Never globally loosen every equality.",
    },
    "paired_correlation_coordinate_equivalence": {
        "observed_incident": "FLOW-0425: an earlier control incorrectly rejected a source-equivalent positive rescaling. The same correlation coefficient alone also cannot establish source pairing.",
        "review": "Inspect every related Pearson and Spearman node, including node-level bindings. Preserve complete paired cohorts and exclusions. Test justified coordinate transformations against non-affine or independently shuffled inputs, not just against expected coefficients. Spearman permits monotone transformations beyond Pearson affine invariance; neither property removes provenance requirements.",
    },
    "full_record_input_match": {
        "observed_incident": "FLOW-0389: a valid projection of necessary hull/response columns should not require unrelated geometry fields.",
        "review": "Verify necessary column identity, row multiplicity, missing values and pair/group membership. Extra input fields may be irrelevant; omitted scientifically needed fields are not.",
    },
    "ordered_group_aggregation": {
        "observed_incident": "Several actual valid routes reorder jointly paired rows before a commutative group statistic.",
        "review": "Test a joint row permutation and a separately permuted wrong pairing. Preserve meaningful time/coordinate/sequence order.",
    },
    "single_declared_method": {
        "observed_incident": "FLOW-0388: a source-grounded aligned product computed the same root joint as the formerly mandatory matrix multiplication.",
        "review": "Inspect scientifically sufficient alternatives and reused results. One declared method alone does not prove a defect or mandate adding arbitrary alternatives.",
    },
    "physical_basis_sensitive_stage": {
        "observed_incident": "FLOW-0226: consistent kJ/mol versus eV/cell routes were incorrectly distinguished; one-sided cell normalization remains wrong.",
        "review": "Audit entire unit/cell/mass/frame/sign conventions, source provenance, implicit corrections and invariants. Test consistent transformations and inconsistent one-sided transformations separately.",
    },
    "answer_container_complexity": {
        "observed_incident": "Earlier full runs exposed answer-container/protocol failures unrelated to scientific conclusions.",
        "review": "Review whether the requested scientific output needs its nested structure. Describe format publicly without exposing expected values; preserve scientific difficulty.",
    },
    "paired_rows_representation_scope": {
        "observed_incident": "FLOW-0272: a valid proper fit was rejected because the generic pair expression allowed rows on the left but only scalar targets on the right.",
        "review": "Check both operand representations against actual contracts and observations. Complete scalar vectors and rectangular rows may be paired on either side. Preserve joint identity, multiplicity, finite cells and capacity; reject independent shuffles, ragged or nested containers. Static occurrences identify related criteria, not scientific approval. See reviews/paired_row_representation_scope.json for actual historical replays.",
    },
    "provenance_scope": {
        "observed_incident": "Original examples, controlled models, projected historical observations and empirical claims must not be conflated.",
        "review": "Read actual source and complete exported values. Check source/decoder/asset hashes, missing/unavailable evidence, assumptions and interpretation boundaries; metadata alone is not verification.",
    },
}


def objects(value, pointer=""):
    if isinstance(value, dict):
        yield pointer, value
        for key, child in value.items():
            yield from objects(
                child, pointer + "/" + key.replace("~", "~0").replace("/", "~1")
            )
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from objects(child, pointer + "/" + str(index))


def inspect_task(public, hidden, tool_names=()):
    findings = []

    def add(pattern, node=None, pointer=None, detail=None):
        item = {
            "pattern": pattern,
            "status": "related_candidate_not_a_confirmed_defect",
        }
        item.update(
            {
                k: v
                for k, v in {"node": node, "pointer": pointer, "detail": detail}.items()
                if v is not None
            }
        )
        findings.append(item)

    optional = {
        node["id"]
        for node in hidden["evaluation"]["nodes"]
        if node.get("required", True) is False
    }
    spec = hidden["evaluation"]
    if (
        not spec.get("capability_groups")
        and len([n for n in spec["nodes"] if n.get("required", True)]) <= 2
    ):
        add(
            "short_required_scientific_path",
            detail={
                "required_nodes": [
                    n["id"] for n in spec["nodes"] if n.get("required", True)
                ],
                "judgment": "Scientific depth needs task-specific review; no automatic defect.",
            },
        )
    from evaluation.authoring.integer_contracts import (
        schema_at,
        numeric_leaves,
    )

    for i, outcome in enumerate(spec["outcomes"]):
        left = outcome.get("left", {})
        if (
            left.get("source") == "answer"
            and outcome.get("op") == "eq"
            and "value" in outcome
        ):
            leaves = list(
                numeric_leaves(
                    outcome["value"],
                    schema_at(public.get("answer_schema", {}), left.get("path", "")),
                )
            )
            if any(is_integer for _, is_integer in leaves) and (
                outcome.get("atol", 0) or outcome.get("rtol", 0)
            ):
                add(
                    "numeric_tolerance_on_public_integer_answer",
                    pointer=f"/evaluation/outcomes/{i}",
                    detail={
                        "outcome_id": outcome["id"],
                        "integer_paths": [
                            path for path, is_integer in leaves if is_integer
                        ],
                    },
                )
            path = left.get("path", "").lower()
            if (
                type(outcome["value"]) in (int, float)
                and any(
                    token in path
                    for token in [
                        "selected_",
                        "chosen_",
                        "largest_qualified_",
                        "winning_",
                    ]
                )
                and (outcome.get("atol", 0) or outcome.get("rtol", 0))
            ):
                add(
                    "numeric_source_choice_with_tolerance",
                    pointer=f"/evaluation/outcomes/{i}",
                    detail={"outcome_id": outcome["id"], "answer_path": path},
                )
    label_results = [
        o["id"]
        for o in spec["outcomes"]
        if isinstance(o.get("value"), str)
        and o.get("left", {}).get("source") == "answer"
    ]
    continuous_results = [
        o["id"]
        for o in spec["outcomes"]
        if type(o.get("value")) in (int, float)
        and (o.get("atol", 0) or o.get("rtol", 0))
    ]
    if label_results and continuous_results:
        add(
            "selected_label_and_continuous_result_association",
            detail={
                "label_outcomes": label_results,
                "numeric_outcomes": continuous_results,
            },
        )
    prose = public["question"].lower()
    if "ratio" in prose and any(
        token in prose for token in ["normaliz", "mass basis", "cell", "per-atom"]
    ):
        add("ratio_and_amount_basis")
    for i, outcome in enumerate(hidden["evaluation"]["outcomes"]):
        overlap = sorted(optional & set(outcome.get("evidence_nodes", [])))
        if overlap:
            add(
                "optional_node_required_by_outcome",
                pointer=f"/evaluation/outcomes/{i}/evidence_nodes",
                detail={"outcome_id": outcome["id"], "optional_nodes": overlap},
            )

    names = [name for name in tool_names if name in public["question"]]
    if names:
        add("named_tool_in_public_question", detail=sorted(names))
    declared = hidden.get("capability_coverage")
    current = sorted(
        {
            tool
            for node in hidden["evaluation"]["nodes"]
            for alternative in node["alternatives"]
            for tool in alternative["tools"]
        }
    )
    if declared is not None and declared != current:
        add(
            "derived_tool_inventory_mismatch",
            detail={"declared": declared, "actual": current},
        )

    for ni, node in enumerate(hidden["evaluation"]["nodes"]):
        tools = {tool for alt in node["alternatives"] for tool in alt["tools"]}
        if tools & {"PearsonCorrelation", "SpearmanCorrelation"}:
            add(
                "paired_correlation_coordinate_equivalence",
                node["id"],
                detail=sorted(tools & {"PearsonCorrelation", "SpearmanCorrelation"}),
            )
        if len(tools) == 1 and tools <= METHOD_TOOLS:
            add("single_declared_method", node["id"], detail=sorted(tools))
        for ai, alternative in enumerate(node["alternatives"]):
            for ri, rule in enumerate(alternative.get("input_rules", [])):
                location = f"/evaluation/nodes/{ni}/alternatives/{ai}/input_rules/{ri}"
                if (
                    rule.get("op") in {"eq", "multiset_equal", "set_equal"}
                    and not rule.get("atol", 0)
                    and not rule.get("rtol", 0)
                ):
                    operations = sorted(
                        {
                            v.get("operation")
                            for _, v in objects(rule)
                            if v.get("operation") in COMPUTED
                        }
                    )
                    if operations:
                        add(
                            "computed_equality_without_tolerance",
                            node["id"],
                            location,
                            operations,
                        )
                path = rule.get("path", "")
                if (
                    tools & RECORD_TOOLS
                    and path
                    in {"/value_column", "/column", "/feature_columns", "/columns"}
                    and rule.get("op") in {"eq", "set_equal", "multiset_equal"}
                    and "value" in rule
                ):
                    add(
                        "literal_intermediate_column_name",
                        node["id"],
                        location,
                        {
                            "tool_names": sorted(tools & RECORD_TOOLS),
                            "argument": path,
                            "literal": rule["value"],
                        },
                    )
                if (
                    tools & RECORD_TOOLS
                    and path
                    in {"/records", "/record_table", "/left_records", "/right_records"}
                    and rule.get("op") in {"eq", "multiset_equal"}
                ):
                    add(
                        "full_record_input_match",
                        node["id"],
                        location,
                        sorted(tools & RECORD_TOOLS),
                    )
                    if "AggregateRecordGroups" in tools and rule["op"] == "eq":
                        add("ordered_group_aggregation", node["id"], location)
        text = node["id"].lower()
        if any(
            word in text
            for word in [
                "energy",
                "enthalpy",
                "calor",
                "lattice",
                "volume",
                "mass",
                "density",
                "frame",
                "coordinate",
                "temperature",
                "curvature",
            ]
        ):
            add("physical_basis_sensitive_stage", node["id"])
    schema_nodes = list(objects(public.get("answer_schema", {})))
    depth = max((path.count("/") for path, _ in schema_nodes), default=0)
    containers = sum(
        any(
            t in ("object", "array")
            for t in (
                v.get("type") if isinstance(v.get("type"), list) else [v.get("type")]
            )
        )
        for _, v in schema_nodes
    )
    if depth >= 7 or containers >= 5:
        add(
            "answer_container_complexity",
            detail={"schema_pointer_depth": depth, "containers": containers},
        )
    paired = [
        path for path, value in objects(spec) if value.get("operation") == "paired_rows"
    ]
    if paired:
        add(
            "paired_rows_representation_scope",
            detail={
                "expression_instances": len(paired),
                "scope": "Representations and scientific pairing require actual evidence.",
            },
        )
    add(
        "provenance_scope",
        detail={
            "declared_asset_count": len(public.get("files", [])),
            "check": "Every source requires individual verification; this flag never attests that it has been read.",
        },
    )
    return findings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "results/reports/cross_task_review.json",
    )
    args = parser.parse_args()
    from src.utils.io import read_jsonl, atomic_json
    from tasks.assets import load_agent_input

    public_path = ROOT / "tasks/questions.jsonl"
    private_path = ROOT / "evaluation/data/references.jsonl.gz"
    catalog_path = ROOT / "tools/catalog/catalog.json"
    asset_manifest = ROOT / "tasks/asset_manifest.json"
    raw_files = {
        path: path.read_bytes()
        for path in (
            public_path,
            private_path,
            catalog_path,
            asset_manifest,
        )
    }
    public = read_jsonl(public_path)
    references = read_jsonl(private_path)
    hidden = {row["id"]: row for row in references}
    expected_ids = {f"FLOW-{i:04d}" for i in range(1, 501)}
    if (
        len(public) != 500
        or len(references) != 500
        or {row["id"] for row in public} != expected_ids
        or set(hidden) != expected_ids
    ):
        raise ValueError("Expected 500 aligned unique formal tasks and references")
    tool_names = json.loads(raw_files[catalog_path])["tools"]
    tasks, identities = {}, {}
    for task in public:
        tid = task["id"]
        reference = hidden[tid]
        if (
            task["question"] != reference["question"]
            or task["inputs"] != reference["inputs"]
        ):
            raise ValueError("Public task/reference drift: " + tid)
        resolved = load_agent_input(task, ROOT / "tasks")
        for name in resolved.get("files", []):
            path = Path(name)
            raw_files[path] = path.read_bytes()
            identities[str(path.relative_to(ROOT))] = hashlib.sha256(
                raw_files[path]
            ).hexdigest()
        tasks[tid] = {
            "id": tid,
            "domain": task["domain"],
            "status": "individual_review_required",
            "public_source": str(public_path.relative_to(ROOT)),
            "reference_source": str(private_path.relative_to(ROOT)),
            "public_sha256": canonical_sha256(task),
            "evaluation_sha256": canonical_sha256(reference["evaluation"]),
            "patterns": inspect_task(task, reference, tool_names),
        }
    per_pattern = {}
    for key, definition in PATTERNS.items():
        affected = sorted(
            tid
            for tid, task in tasks.items()
            if any(value["pattern"] == key for value in task["patterns"])
        )
        per_pattern[key] = {
            **definition,
            "candidate_tasks": len(affected),
            "candidate_task_ids": affected,
            "confirmed_defects_from_pattern_alone": 0,
        }
    # Refuse a report assembled across concurrent release edits.
    if any(path.read_bytes() != raw for path, raw in raw_files.items()):
        raise ValueError("Release sources changed while indexing; rerun")
    report = {
        "schema_version": "scitoolflow.cross-task-review.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "review_candidates_not_acceptance",
        "tasks_inspected": len(tasks),
        "categories": per_pattern,
        "asset_sha256": identities,
        "input_sha256": {
            str(path.relative_to(ROOT)): hashlib.sha256(raw).hexdigest()
            for path, raw in raw_files.items()
        },
        "tasks": [tasks[tid] for tid in sorted(tasks)],
        "interpretation": (
            "Patterns identify related tasks for individual scientific review, not confirmed defects. "
            "This report does not approve tasks, replace native review or relax criteria."
        ),
    }
    atomic_json(args.output, report)
    print(
        json.dumps(
            {
                "tasks_inspected": len(tasks),
                "review_candidate_tasks_by_pattern": {
                    key: value["candidate_tasks"] for key, value in per_pattern.items()
                },
                "confirmed_defects_from_pattern_alone": 0,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
