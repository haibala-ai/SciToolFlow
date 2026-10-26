"""Plot the current release against the pinned public SciToolEval Level2 snapshot."""

from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[2]


def main():
    upstream_path = ROOT / "docs/comparison/sources/upstream_metadata.json"
    current_path = ROOT / "docs/benchmark_analysis/statistics.json"
    upstream = json.loads(upstream_path.read_text())
    current = json.loads(current_path.read_text())
    for name, expected in current["source_sha256"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise ValueError("Recompute current benchmark statistics first: " + name)
    paths = [r["tool_path"] for r in upstream["tasks"]]
    registered = set().union(*[set(v) for v in upstream["registry_groups"].values()])
    covered = set().union(*[set(p) for p in paths]) & registered
    domain_map = {
        name: group.removesuffix("Tools")
        for group, names in upstream["registry_groups"].items()
        for name in names
    }
    domain_names = ["Chemical", "Material", "Biology", "MachineLearning", "General"]
    incidence = Counter()
    for path in paths:
        incidence.update({domain_map[name] for name in path if name in domain_map})
    upstream_domains = {
        domain: {
            "registered_tools": sum(d == domain for d in domain_map.values()),
            "covered_tools": sum(domain_map[n] == domain for n in covered),
            "tasks_using_domain": incidence[domain],
        }
        for domain in domain_names
    }
    current_domains = {
        domain: {
            "registered_tools": current["domain_statistics"][domain][
                "registered_scientific_tools"
            ],
            "covered_tools": current["domain_statistics"][domain][
                "observed_successful_tools"
            ],
            "tasks_using_domain": current["domain_statistics"][domain][
                "tasks_using_domain"
            ],
        }
        for domain in domain_names
    }
    lengths = [len(p) for p in paths]
    counts = Counter(lengths)
    report = {
        "release": current["release"],
        "upstream_commit": upstream["commit"],
        "upstream": {
            "tasks": len(paths),
            "scientific_tools": len(registered),
            "reference_calls_mean": statistics.mean(lengths),
            "reference_calls_median": statistics.median(lengths),
            "reference_calls_max": max(lengths),
            "at_least_four_calls": sum(v >= 4 for v in lengths),
            "reference_call_histogram": dict(sorted(counts.items())),
            "covered_registered_tools": len(covered),
            "reference_tool_coverage": len(covered) / len(registered),
            "domain_table": upstream_domains,
        },
        "scitoolflow": {
            "tasks": current["tasks"],
            "scientific_tools": current["scientific_tool_pool"],
            "reference_calls_mean": current["reference_scientific_calls"]["mean"],
            "reference_calls_median": current["reference_scientific_calls"]["median"],
            "reference_calls_max": current["reference_scientific_calls"]["max"],
            "at_least_four_calls": sum(
                v
                for k, v in current["reference_scientific_calls"]["histogram"].items()
                if int(k) >= 4
            ),
            "reference_call_histogram": current["reference_scientific_calls"][
                "histogram"
            ],
            "covered_registered_tools": current["observed_successful_tool_count"],
            "reference_tool_coverage": current["observed_successful_tool_coverage"],
            "domain_table": current_domains,
        },
        "definitions": {
            "upstream_length": "Tool names in supplied public reference paths; not newly executed.",
            "current_length": "Actual primary-reference scientific calls, including failures; DescribeTools excluded.",
            "coverage": "Each side uses its own registered-name pool. Upstream is path occurrence; current is successful execution. Different taxonomies; no one-to-one capability or availability claim.",
        },
        "source_sha256": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [upstream_path, current_path]
        },
    }
    a, b = report["upstream"], report["scitoolflow"]
    report["change"] = {
        "task_increase_percent": 100 * (b["tasks"] / a["tasks"] - 1),
        "reference_mean_ratio": b["reference_calls_mean"] / a["reference_calls_mean"],
        "reference_median_ratio": b["reference_calls_median"]
        / a["reference_calls_median"],
        "four_call_share_increase_pp": 100
        * (
            b["at_least_four_calls"] / b["tasks"]
            - a["at_least_four_calls"] / a["tasks"]
        ),
        "own_registry_coverage_increase_pp": 100
        * (b["reference_tool_coverage"] - a["reference_tool_coverage"]),
    }
    report["definitions"][
        "domains"
    ] = "Multi-label task incidence, using each side's registered tool categories. An absent original MachineLearning group is not a claim that the original algorithms lack numerical capabilities."
    out = ROOT / "docs/comparison"
    (out / "current.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    from scripts.benchmark.figures import plot_release_comparison

    plot_release_comparison(report, out)
    print(json.dumps({k: report[k] for k in ["upstream", "scitoolflow"]}))


if __name__ == "__main__":
    main()
