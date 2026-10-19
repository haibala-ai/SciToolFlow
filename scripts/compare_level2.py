"""Reproduce aggregate Level2 comparisons without executing scientific tools.

Use --refresh-upstream to read pinned upstream Git blobs; otherwise use the
metadata-only snapshot. No questions, answers, credentials or biological inputs
are copied into the report. Plots require matplotlib.
"""

import argparse
import ast
from collections import Counter, defaultdict, deque
import hashlib
import json
from pathlib import Path
import statistics
import subprocess

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "ac1cf19fcef84e69f149db6da424afe4e9b2f11f"
DOMAINS = ["Biology", "Chemical", "Material", "MachineLearning", "General"]
GROUPS = {
    "BiologyTools": "Biology",
    "ChemicalTools": "Chemical",
    "MaterialTools": "Material",
    "GeneralTools": "General",
}
KG_TYPES = {
    "Biological Tool": "Biology",
    "Chemical Tool": "Chemical",
    "Material Tool": "Material",
    "General Tool": "General",
}


def digest(value):
    return hashlib.sha256(value).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )


def jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def snapshot(upstream):
    files = {}

    def blob(path):
        data = subprocess.check_output(
            ["git", "show", COMMIT + ":" + path], cwd=upstream
        )
        files[path] = {"sha256": digest(data), "bytes": len(data)}
        return data

    tree = ast.parse(blob("ToolsAgent/ToolsFuns/tools_dict.py").decode())
    mapping = ast.literal_eval(
        next(
            n.value
            for n in tree.body
            if isinstance(n, ast.Assign)
            and any(
                isinstance(t, ast.Name) and t.id == "TOOLS_MAPPING" for t in n.targets
            )
        )
    )
    graph = json.loads(blob("KG/storage_graph_large/graph_store.json"))["graph_dict"]
    kg = {
        name: KG_TYPES[value]
        for name, edges in graph.items()
        for relation, value in edges
        if relation == "is a" and value in KG_TYPES
    }
    questions = [
        json.loads(l)
        for l in blob("SciToolEval/data/level2_question.jsonl").decode().splitlines()
        if l.strip()
    ]
    gold_lines = (
        blob("SciToolEval/data/level2_correct_answer.jsonl").decode().splitlines()
    )
    valid, errors = [], []
    for line, text in enumerate(gold_lines, 1):
        if not text.strip():
            continue
        try:
            valid.append(json.loads(text))
        except json.JSONDecodeError as error:
            errors.append({"line": line, "column": error.colno, "message": error.msg})
    for name in [
        "SciToolEval/README.md",
        "SciToolEval/eval/eval_accuracy.py",
        "SciToolEval/eval/eval_tool_path.py",
    ]:
        blob(name)
    # Retain only aggregate-ready identifiers; never publish question text/inputs.
    tasks = [
        {
            "row": i,
            "tool_path": q["tool_path"],
            "question_sha256": digest(q["question"].strip().encode()),
            "public_fields": sorted(q),
            "has_answer": any(
                k in q for k in ["answer", "final_answer", "expected_answer"]
            ),
        }
        for i, q in enumerate(questions, 1)
    ]
    return {
        "repository": "https://github.com/HICAI-ZJU/SciToolAgent",
        "commit": COMMIT,
        "files": files,
        "registry_groups": mapping,
        "kg_tool_domains": kg,
        "tasks": tasks,
        "gold_file": {
            "nonempty_lines": sum(bool(l.strip()) for l in gold_lines),
            "strict_json_valid_rows": len(valid),
            "parse_errors": errors,
            "fields": dict(Counter(k for r in valid for k in r)),
            "rows_with_answer_field": sum(
                any(k in r for k in ["answer", "final_answer", "expected_answer"])
                for r in valid
            ),
            "valid_questions_matching_question_file": sum(
                digest(r.get("question", "").strip().encode())
                in {t["question_sha256"] for t in tasks}
                for r in valid
            ),
        },
    }


def distribution(values):
    values = sorted(values)

    def percentile(p):
        pos = (len(values) - 1) * p
        lo = int(pos)
        hi = min(lo + 1, len(values) - 1)
        return values[lo] + (values[hi] - values[lo]) * (pos - lo)

    return {
        "count": len(values),
        "total": sum(values),
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
        "p25": percentile(0.25),
        "p75": percentile(0.75),
        "p90": percentile(0.9),
        "p95": percentile(0.95),
        "histogram": dict(sorted(Counter(values).items())),
        "at_least_4": sum(x >= 4 for x in values),
        "at_least_6": sum(x >= 6 for x in values),
        "at_least_10": sum(x >= 10 for x in values),
    }


def summarize(tasks, registry, domain_map):
    paths = [t["tool_path"] for t in tasks]
    used = set().union(*(set(p) for p in paths))
    covered = used & registry
    table = {}
    for domain in DOMAINS:
        pool = {n for n in registry if domain_map.get(n) == domain}
        hit = covered & pool
        count = sum(any(domain_map.get(n) == domain for n in p) for p in paths)
        table[domain] = {
            "registered_tools": len(pool),
            "covered_tools": len(hit),
            "tool_coverage_pct": 100 * len(hit) / len(pool) if pool else None,
            "tasks_using_domain": count,
            "task_incidence_pct": 100 * count / len(tasks),
            "reference_calls": sum(
                sum(domain_map.get(n) == domain for n in p) for p in paths
            ),
        }
    cross = sum(len({domain_map[n] for n in p if n in domain_map}) >= 2 for p in paths)
    path_counts = Counter(tuple(p) for p in paths)
    primary = Counter()
    ties = 0
    for p in paths:
        counts = Counter(domain_map[n] for n in p if n in domain_map)
        if counts:
            top = max(counts.values())
            winners = {d for d, c in counts.items() if c == top}
            ties += len(winners) > 1
            primary[next(domain_map[n] for n in p if domain_map.get(n) in winners)] += 1
        else:
            primary["Unknown"] += 1
    return {
        "tasks": len(tasks),
        "registered_tools": len(registry),
        "distinct_reference_names": len(used),
        "covered_registered_tools": len(covered),
        "tool_coverage_pct": 100 * len(covered) / len(registry),
        "reference_names_missing_from_registry": sorted(used - registry),
        "call_length": distribution([len(p) for p in paths]),
        "distinct_tools_per_task": distribution([len(set(p)) for p in paths]),
        "unique_ordered_paths": len(path_counts),
        "unique_tool_sets": len({tuple(sorted(set(p))) for p in paths}),
        "largest_identical_path_group": max(path_counts.values()),
        "top10_identical_path_task_count": sum(
            c for _, c in path_counts.most_common(10)
        ),
        "tasks_repeating_a_tool": sum(len(p) != len(set(p)) for p in paths),
        "cross_domain_tasks": cross,
        "cross_domain_task_pct": 100 * cross / len(tasks),
        "domains_with_registered_tools": sum(
            v["registered_tools"] > 0 for v in table.values()
        ),
        "domains_with_task_coverage": sum(
            v["tasks_using_domain"] > 0 for v in table.values()
        ),
        "domain_table": table,
        "inferred_primary_domain": dict(primary),
        "primary_domain_ties": ties,
    }


def dag_stats(reference):
    nodes = set(reference["dependency_graph"]["necessary_nodes"])
    adjacency = defaultdict(set)
    indegrees = {n: 0 for n in nodes}
    for e in reference["dependency_graph"]["edges"]:
        if (
            e["from"] in nodes
            and e["to"] in nodes
            and e["to"] not in adjacency[e["from"]]
        ):
            adjacency[e["from"]].add(e["to"])
            indegrees[e["to"]] += 1
    levels = {n: 1 for n in nodes}
    queue = deque(n for n, d in indegrees.items() if d == 0)
    seen = 0
    roots = len(queue)
    edges = sum(map(len, adjacency.values()))
    while queue:
        n = queue.popleft()
        seen += 1
        for target in adjacency[n]:
            levels[target] = max(levels[target], levels[n] + 1)
            indegrees[target] -= 1
            if indegrees[target] == 0:
                queue.append(target)
    if seen != len(nodes):
        raise ValueError("Cycle in " + reference["id"])
    return {
        "depth": max(levels.values()),
        "edges": edges,
        "roots": roots,
        "max_layer_width": max(Counter(levels.values()).values()),
        "has_fanout": any(len(v) > 1 for v in adjacency.values()),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, default=ROOT.parent / "SciToolAgent")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/comparison")
    parser.add_argument("--refresh-upstream", action="store_true")
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    source = out / "sources/upstream_metadata.json"
    if args.refresh_upstream:
        save(source, snapshot(args.upstream))
    upstream = json.loads(source.read_text())
    if upstream["commit"] != COMMIT:
        raise ValueError("Upstream snapshot commit mismatch")
    catalog = json.loads((ROOT / "tools/catalog.json").read_text())
    aliases = catalog["aliases"]
    current = {
        n: t["domain"] for n, t in catalog["tools"].items() if t["kind"] == "scientific"
    }
    old_groups = upstream["registry_groups"]
    old = {n: GROUPS[group] for group, ns in old_groups.items() for n in ns}
    old_domain = {**upstream["kg_tool_domains"], **old}
    old_summary = summarize(upstream["tasks"], set(old), old_domain)
    normalized = [
        {**t, "tool_path": [aliases.get(n, n) for n in t["tool_path"]]}
        for t in upstream["tasks"]
    ]
    common_summary = summarize(normalized, set(current), current)
    refs = jsonl(ROOT / "evaluation/references.jsonl")
    questions = jsonl(ROOT / "tasks/questions.jsonl")
    if len(refs) != 500 or {r["id"] for r in refs} != {q["id"] for q in questions}:
        raise ValueError("Task/reference IDs mismatch")
    ours = summarize(refs, set(current), current)
    old_normalized = {aliases.get(n, n) for n in old}
    retained = set(current) & old_normalized
    added = set(current) - old_normalized
    renamed = {n: aliases[n] for n in old if n in aliases and aliases[n] != n}
    delta = {
        "raw_upstream_unique_registry": len(old),
        "upstream_registry_slots": sum(map(len, old_groups.values())),
        "duplicate_registry_slots": sum(map(len, old_groups.values())) - len(old),
        "upstream_kg_tool_nodes": len(upstream["kg_tool_domains"]),
        "upstream_registry_without_kg_node": sorted(
            set(old) - upstream["kg_tool_domains"].keys()
        ),
        "upstream_kg_without_registry_entry": sorted(
            upstream["kg_tool_domains"].keys() - old.keys()
        ),
        "current_scientific_tools": len(current),
        "net_new_scientific_tools": len(current) - len(old),
        "net_growth_pct": 100 * (len(current) - len(old)) / len(old),
        "new_canonical_names": len(added),
        "added_by_domain": dict(Counter(current[n] for n in added)),
        "added_names_by_domain": {
            d: sorted(n for n in added if current[n] == d) for d in DOMAINS
        },
        "retained_or_alias_mapped": len(retained),
        "renamed_upstream_registry_names": renamed,
        "removed_without_current_mapping": sorted(
            n for n in old if aliases.get(n, n) not in current
        ),
    }
    trace_counts = Counter()
    need_counts = Counter()
    successful_names = set()
    all_output_fields = 0
    for r in refs:
        if "DescribeTools" in r["tool_path"]:
            raise ValueError("Discovery in reference path")
        events = {}
        for e in jsonl(ROOT / r["reference_trace"]):
            if e.get("event") != "tool_result":
                continue
            trace_counts[e.get("status", "missing")] += 1
            all_output_fields += "output" in e
            if e.get("status") == "success":
                successful_names.add(aliases.get(e["tool"], e["tool"]))
            events[e["observation_id"]] = e
        for oid in r["necessary_observation_ids"]:
            need_counts[events.get(oid, {}).get("status", "missing")] += 1
    dags = [dag_stats(r) for r in refs]
    groups = Counter(r["split_group_id"] for r in refs)
    preflight = json.loads((ROOT / "results/reports/tool_preflight.json").read_text())
    ours["quality"] = {
        "all_public_tasks_have_schema": all(
            bool(q.get("answer_schema")) for q in questions
        ),
        "public_tasks_expose_reference_path": sum("tool_path" in q for q in questions),
        "all_references_have_structured_expected_answer": all(
            isinstance(r["expected_answer"], dict) for r in refs
        ),
        "reference_review_kind": dict(Counter(r["review"]["kind"] for r in refs)),
        "reference_review_status": dict(Counter(r["review"]["status"] for r in refs)),
        "reference_trace_scopes": dict(
            Counter(r.get("reference_trace_scope", "unknown") for r in refs)
        ),
        "references_with_expert_review_records": sum(
            bool(r["review"].get("expert_review_records")) for r in refs
        ),
        "input_kinds": dict(Counter(r["input_kind"] for r in refs)),
        "reference_tool_result_status": dict(trace_counts),
        "inline_output_fields": all_output_fields,
        "necessary_result_status": dict(need_counts),
        "historically_successful_tool_names": len(successful_names & set(current)),
        "dependency_depth": distribution([d["depth"] for d in dags]),
        "dependency_edges": distribution([d["edges"] for d in dags]),
        "max_dependency_layer_width": distribution(
            [d["max_layer_width"] for d in dags]
        ),
        "tasks_with_fanout": sum(d["has_fanout"] for d in dags),
        "primary_domain_declared": dict(Counter(q["domain"] for q in questions)),
        "workflow_entity_groups": len(groups),
        "largest_workflow_entity_group": max(groups.values()),
        "top5_workflow_entity_group_tasks": sum(c for _, c in groups.most_common(5)),
        "group_size_distribution": dict(sorted(Counter(groups.values()).items())),
        "unique_workflow_family_hashes": len({r["workflow_group"] for r in refs}),
        "split": "none; groups are diagnostic, not held-out partitions",
    }
    old_summary["quality"] = {
        "public_tasks_expose_reference_path": sum(
            "tool_path" in t["public_fields"] for t in upstream["tasks"]
        ),
        "exact_duplicate_question_count": len(upstream["tasks"])
        - len({t["question_sha256"] for t in upstream["tasks"]}),
        "gold_file": upstream["gold_file"],
        "executed_trajectory_length": None,
        "raw_reference_observations": "not present in the compared Level2 JSONL files; no whole-repository absence claim",
    }
    evidence = {k: v for k, v in preflight.items() if k != "tools_detail"}
    graph_report = json.loads((ROOT / "tools/graph/build_report.json").read_text())
    inputs = {
        str(p.relative_to(ROOT)): {
            "sha256": digest(p.read_bytes()),
            "bytes": p.stat().st_size,
        }
        for p in [
            ROOT / "tools/catalog.json",
            ROOT / "tasks/questions.jsonl",
            ROOT / "evaluation/references.jsonl",
            ROOT / "tasks/metadata.json",
            ROOT / "results/reports/tool_preflight.json",
            ROOT / "tools/graph/build_report.json",
        ]
    }
    report = {
        "schema_version": 1,
        "upstream_commit": COMMIT,
        "definitions": {
            "scientific_tools": "Distinct advertised registry names, excluding DescribeTools; original dispatch list duplicates deduplicated. Original runtime callability is not measured.",
            "reference_length": "Number of scientific tools in supplied reference tool_path, not model turns or actual executed length.",
            "domain_coverage": "Covered registered tool names / all registered names in that domain.",
            "task_incidence": "Task contains at least one reference tool from domain; multi-label, percentages can sum above 100.",
            "native_taxonomy": "Original dispatcher groups vs current catalog domains; labels need not represent identical boundaries.",
            "common_taxonomy": "Original reference aliases resolved into current 546-tool catalog, enabling matched domain/denominator comparison.",
            "coverage_not_live_availability": "Reference occurrence is not a new live invocation; static preflight is not all-tool live acceptance.",
        },
        "inputs": inputs,
        "tool_delta": delta,
        "original_level2_native_taxonomy": old_summary,
        "original_level2_current_catalog_taxonomy": common_summary,
        "scitoolflow": ours,
        "current_preflight_evidence": evidence,
        "current_graph_evidence": {
            k: graph_report[k]
            for k in [
                "public_tool_nodes",
                "scientific_tools",
                "discovery_tools",
                "nodes",
                "directed_edges",
                "relation_types",
                "all_public_contracts_linked",
            ]
            if k in graph_report
        },
    }
    save(out / "statistics.json", report)
    save(out / "tool_delta.json", delta)
    plot(report, out)
    print(
        json.dumps(
            {
                "original": {
                    k: old_summary[k]
                    for k in [
                        "tasks",
                        "registered_tools",
                        "covered_registered_tools",
                        "tool_coverage_pct",
                        "unique_ordered_paths",
                        "cross_domain_tasks",
                    ]
                },
                "current": {
                    k: ours[k]
                    for k in [
                        "tasks",
                        "registered_tools",
                        "covered_registered_tools",
                        "tool_coverage_pct",
                        "unique_ordered_paths",
                        "cross_domain_tasks",
                    ]
                },
                "mean_calls": [
                    old_summary["call_length"]["mean"],
                    ours["call_length"]["mean"],
                ],
                "outputs": str(out),
            },
            ensure_ascii=False,
        )
    )


def plot(report, out):
    """Two focused, shareable figures; all values come from statistics.json."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    plt.rcParams.update(
        {
            "font.size": 11,
            "font.family": "DejaVu Sans",
            "svg.fonttype": "none",
            "svg.hashsalt": "scitoolflow-comparison-v2",
            "axes.titleweight": "bold",
        }
    )
    old = report["original_level2_current_catalog_taxonomy"]
    ours = report["scitoolflow"]
    gray, teal, ink = "#a2afbf", "#087f8c", "#172b4d"

    def clean(ax):
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.spines["bottom"].set_color("#dce3e9")
        ax.tick_params(length=0, pad=7)
        ax.grid(axis="y", color="#edf0f3")
        ax.set_axisbelow(True)

    def export(fig, name):
        fig.savefig(
            out / (name + ".svg"),
            bbox_inches="tight",
            facecolor="white",
            metadata={"Date": None},
        )
        fig.savefig(
            out / (name + ".png"), bbox_inches="tight", facecolor="white", dpi=180
        )
        plt.close(fig)

    fig = plt.figure(figsize=(12, 5.5))
    fig.suptitle(
        "SciToolFlow  |  More coverage. Longer tool workflows.",
        x=0.06,
        y=0.99,
        ha="left",
        color=ink,
        fontsize=20,
        weight="bold",
    )
    metrics = [
        ("500", "tasks  ·  379 in Level2"),
        ("6.58", "calls / task  ·  2.47 in Level2"),
        ("58.97%", "tool coverage  ·  20.88% in Level2"),
    ]
    for i, (value, label) in enumerate(metrics):
        ax = fig.add_axes([0.065 + 0.315 * i, 0.71, 0.29, 0.19])
        ax.axis("off")
        ax.text(0, 0.55, value, fontsize=31, color=teal, weight="bold")
        ax.text(0, 0.10, label, fontsize=11, color="#53647a")
    ax = fig.add_axes([0.065, 0.17, 0.90, 0.46])
    x = np.arange(2, 21)
    width = 0.4
    for vals, offset, label, color in [
        (old, -0.2, "SciToolEval Level2", gray),
        (ours, 0.2, "SciToolFlow", teal),
    ]:
        hist = vals["call_length"]["histogram"]
        y = [
            100 * hist.get(str(int(n)), hist.get(int(n), 0)) / vals["tasks"] for n in x
        ]
        ax.bar(x + offset, y, width, color=color, label=label)
    clean(ax)
    ax.set(
        xlabel="Scientific calls in the reference path",
        ylabel="Tasks (%)",
        xticks=x,
        ylim=(0, 82),
    )
    ax.legend(frameon=False, loc="upper right", ncol=2)
    fig.text(
        0.065,
        0.025,
        "Reference-path statistics, not model accuracy or serial reasoning depth. Coverage uses the same 546-tool catalog.",
        fontsize=10,
        color="#53647a",
    )
    export(fig, "overview")

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), layout="constrained")
    names = ["Biology", "Chemical", "Material", "MachineLearning", "General"]
    labels = ["Biology", "Chemistry", "Materials", "ML / Math", "General"]
    y = np.arange(len(names))
    for ax, metric, title in [
        (axes[0], "tool_coverage_pct", "Tool coverage by discipline"),
        (axes[1], "task_incidence_pct", "Tasks using each discipline"),
    ]:
        for vals, off, label, color in [
            (old, -0.18, "SciToolEval Level2", gray),
            (ours, 0.18, "SciToolFlow", teal),
        ]:
            numbers = [vals["domain_table"][d][metric] for d in names]
            ax.barh(y + off, numbers, 0.32, color=color, label=label)
            for pos, value in zip(y + off, numbers):
                ax.text(
                    value + 1.2,
                    pos,
                    f"{value:.1f}%",
                    va="center",
                    fontsize=10,
                    color=ink,
                )
        ax.set(
            yticks=y,
            yticklabels=labels,
            xlim=(0, 117),
            xticks=[0, 25, 50, 75, 100],
            xlabel="Percent (%)",
            title=title,
        )
        ax.invert_yaxis()
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.spines["bottom"].set_color("#dce3e9")
        ax.tick_params(length=0)
        ax.grid(axis="x", color="#edf0f3")
        ax.set_axisbelow(True)
    axes[0].legend(frameon=False, loc="lower right", fontsize=9)
    fig.suptitle("Broader scientific reach", fontsize=19, weight="bold", color=ink)
    fig.supxlabel(
        "Same catalog and taxonomy. Task incidence is multi-label; one task can use several disciplines.",
        fontsize=10,
        color="#53647a",
    )
    export(fig, "coverage")
    for name in ["comparison.svg", "comparison.png"]:
        (out / name).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
