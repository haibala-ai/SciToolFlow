"""Recompute release statistics from actual references; never execute tools/LLMs."""

import argparse, collections, hashlib, json, re, statistics, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.utils.io import read_jsonl
from evaluation.integrity.traces import execution_calls, read_trajectory
from tools.catalog import ToolCatalog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/benchmark_analysis")
    parser.add_argument("--no-plots", action="store_true")
    a = parser.parse_args()
    out = a.output
    out.mkdir(parents=True, exist_ok=True)
    qs = read_jsonl(ROOT / "tasks/questions.jsonl")
    refs = read_jsonl(ROOT / "evaluation/data/references.jsonl.gz")
    byid = {r["id"]: r for r in refs}
    cat = ToolCatalog(ROOT)
    rows = []
    covered = set()
    allowed = set()
    tool_use = collections.Counter()
    policy = set()
    question_shapes = collections.defaultdict(list)
    data_components = {q["id"]: q["id"] for q in qs}
    asset_owner = {}

    def find(x):
        while data_components[x] != x:
            x = data_components[x]
        return x

    def union(x, y):
        data_components[find(x)] = find(y)

    categories = {
        r["id"]: r["category"]
        for r in json.loads((ROOT / "tasks/index.json").read_text())["tasks"]
    }
    for q in qs:
        r = byid[q["id"]]
        trace = read_trajectory(ROOT / r["reference_trace"])
        calls = [c for c in execution_calls(trace) if c["tool"] != "DescribeTools"]
        success = [c for c in calls if c["status"] == "success"]
        names = {c["tool"] for c in success}
        covered |= names
        tool_use.update(names)
        for n in r["evaluation"]["nodes"]:
            for alt in n["alternatives"]:
                allowed.update(alt["tools"])
        policy.add(json.dumps(r["evaluation"]["efficiency"], sort_keys=True))
        shape = re.sub(r"\b\d+(?:\.\d+)?\b", "<number>", q["question"].casefold())
        question_shapes[shape].append(q["id"])
        answer_types = collections.Counter(
            (
                v.get("type", "compound")
                if isinstance(v.get("type", "compound"), str)
                else "nullable"
            )
            for v in q["answer_schema"]["properties"].values()
        )
        for uri in q["files"]:
            name = uri.split("asset://", 1)[-1]
            if name in asset_owner:
                union(q["id"], asset_owner[name])
            else:
                asset_owner[name] = q["id"]
        rows.append(
            {
                "id": q["id"],
                "domain": q["domain"],
                "title": re.split(r"(?<=[.!?])\s", q["question"])[0],
                "scientific_calls": len(calls),
                "successful_scientific_calls": len(success),
                "distinct_successful_tools": len(names),
                "tool_domains": sorted({cat.tools[n]["domain"] for n in names}),
                "has_numerical_program": "ExecuteNumericalCode" in names,
                "source_and_program_only": names
                <= {"ParseJSONDocument", "ExecuteNumericalCode"}
                and "ExecuteNumericalCode" in names,
                "file_count": len(q["files"]),
                "answer_fields": list(q["answer_schema"]["properties"]),
                "answer_types": dict(answer_types),
                "category": categories[q["id"]],
            }
        )

    def dist(values):
        v = sorted(values)
        return {
            "min": min(v),
            "median": statistics.median(v),
            "mean": statistics.mean(v),
            "max": max(v),
            "histogram": {str(k): n for k, n in sorted(collections.Counter(v).items())},
        }

    pool = set(cat.tools) - {"DescribeTools"}
    domains = sorted({s["domain"] for s in cat.tools.values()})
    domain_stats = {
        d: {
            "tasks": sum(q["domain"] == d for q in qs),
            "registered_scientific_tools": sum(
                cat.tools[t]["domain"] == d for t in pool
            ),
            "observed_successful_tools": sum(
                cat.tools[t]["domain"] == d for t in covered
            ),
            "scorer_allowed_tools": sum(cat.tools[t]["domain"] == d for t in allowed),
            "tasks_using_domain": sum(d in x["tool_domains"] for x in rows),
        }
        for d in domains
    }
    source_files = [
        "tasks/questions.jsonl",
        "evaluation/data/references.jsonl.gz",
        "tools/catalog/catalog.json",
    ]
    stats = {
        "release": json.loads((ROOT / "tasks/metadata.json").read_text())["release"],
        "tasks": len(qs),
        "reference_count": len(refs),
        "domain_statistics": domain_stats,
        "scientific_tool_pool": len(pool),
        "observed_successful_tool_count": len(covered),
        "observed_successful_tool_coverage": len(covered) / len(pool),
        "scorer_allowed_tool_count": len(allowed),
        "scorer_allowed_tool_coverage": len(allowed) / len(pool),
        "scorer_allowed_tool_names": sorted(allowed),
        "successful_tool_names": sorted(covered),
        "tool_task_frequencies": dict(tool_use.most_common()),
        "reference_scientific_calls": dist([r["scientific_calls"] for r in rows]),
        "reference_successful_calls": dist(
            [r["successful_scientific_calls"] for r in rows]
        ),
        "distinct_successful_tools_per_task": dist(
            [r["distinct_successful_tools"] for r in rows]
        ),
        "two_call_references": sum(r["scientific_calls"] == 2 for r in rows),
        "source_and_program_only_tasks": sum(
            r["source_and_program_only"] for r in rows
        ),
        "tasks_with_numerical_program": sum(r["has_numerical_program"] for r in rows),
        "cross_tool_domain_tasks": sum(len(r["tool_domains"]) > 1 for r in rows),
        "task_categories": dict(collections.Counter(categories.values())),
        "efficiency_policy_count": len(policy),
        "normalized_exact_question_duplicates": [
            v for v in question_shapes.values() if len(v) > 1
        ],
        "shared_public_asset_components": len({find(q["id"]) for q in qs}),
        "source_sha256": {
            p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in source_files
        },
    }
    (out / "statistics.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2) + "\n"
    )
    (out / "tasks.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n"
    )
    if not a.no_plots:
        from scripts.benchmark.figures import plot_benchmark_overview

        plot_benchmark_overview(stats, rows, out)
    print(
        json.dumps(
            {
                k: v
                for k, v in stats.items()
                if k
                not in {
                    "successful_tool_names",
                    "tool_task_frequencies",
                    "small_values_compatible_with_mathematical_zero",
                    "source_sha256",
                }
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
