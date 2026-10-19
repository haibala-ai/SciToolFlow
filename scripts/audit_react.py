"""Offline aggregate review of ReAct traces; never dispatch tools or send task data."""

import argparse
from collections import Counter
import json
from pathlib import Path
import statistics


def distribution(values):
    values = sorted(values)
    if not values:
        return {}
    return {
        "count": len(values),
        "min": values[0],
        "median": statistics.median(values),
        "p90": values[min(len(values) - 1, int((len(values) - 1) * 0.9))],
        "max": values[-1],
        "total": sum(values),
    }


def error_kind(message):
    for prefix, label in [
        ("First query these tool contracts", "mandatory_discovery"),
        ("Thinking limit reached", "think_limit"),
        ("Answer schema:", "answer_schema"),
        ("Identical tool inputs", "repeated_failed_call"),
        ("Return exactly one complete JSON", "invalid_json"),
        ("Unknown tool", "unknown_tool"),
        ("Choose exactly one", "decision_format"),
        ("Citation is not", "invalid_citation"),
        ("actions must contain", "batch_size"),
    ]:
        if message.startswith(prefix):
            return label
    if " input: " in message or "arguments must be" in message:
        return "tool_arguments"
    return "other"


def summarize(traces):
    categories, failures, statuses, error_types, counts = [Counter() for _ in range(5)]
    cases = []
    for t in traces:
        stats = t.get("stats", {})
        steps = t.get("steps", [])
        statuses[t["status"]] += 1
        if t.get("failure_reason"):
            failures[t["failure_reason"].split(":")[0]] += 1
        failed_calls = Counter()
        seen_calls = Counter()
        repeats = 0
        kinds = Counter()
        step_errors = Counter()
        consecutive = 0
        max_consecutive = 0
        truncated = 0
        for s in steps:
            counts[s["type"]] += 1
            truncated += bool(s.get("model", {}).get("truncated"))
            if s["type"] == "error":
                key = error_kind(s.get("error", {}).get("message", ""))
                categories[key] += 1
                step_errors[key] += 1
                error_types[s.get("error", {}).get("type")] += 1
                consecutive += 1
                max_consecutive = max(max_consecutive, consecutive)
            else:
                consecutive = 0
            for c in s.get("calls", []):
                kinds[c["kind"]] += 1
                if c["kind"] == "scientific":
                    key = json.dumps([c["tool"], c["arguments"]], sort_keys=True)
                    if seen_calls[key]:
                        repeats += 1
                    seen_calls[key] += 1
                    if c["status"] != "success":
                        failed_calls[c.get("error_type") or c["status"]] += 1
        cases.append(
            {
                "id": t["task_id"],
                "status": t["status"],
                "failure_reason": t.get("failure_reason"),
                "stats": stats,
                "limits": t["limits"],
                "duration_seconds": t.get("duration_seconds"),
                "error_categories": dict(step_errors),
                "max_consecutive_errors": max_consecutive,
                "truncated_responses": truncated,
                "failed_scientific_calls": dict(failed_calls),
                "repeated_scientific_inputs": repeats,
                "step_count": len(steps),
                "call_counts": dict(kinds),
            }
        )
    return {
        "traces": len(traces),
        "statuses": dict(statuses),
        "failure_reasons": dict(failures),
        "protocol_error_categories": dict(categories),
        "error_types": dict(error_types),
        "step_types": dict(counts),
        "stat_distributions": {
            k: distribution([c["stats"].get(k, 0) for c in cases])
            for k in [
                "model_turns",
                "scientific_calls",
                "discovery_calls",
                "think_steps",
                "inspection_steps",
                "protocol_errors",
                "prompt_tokens",
                "completion_tokens",
                "context_compactions",
            ]
        },
        "duration_seconds": distribution(
            [c["duration_seconds"] for c in cases if c["duration_seconds"] is not None]
        ),
        "tasks_with_errors": sum(bool(c["error_categories"]) for c in cases),
        "tasks_with_truncation": sum(bool(c["truncated_responses"]) for c in cases),
        "repeated_scientific_inputs": sum(
            c["repeated_scientific_inputs"] for c in cases
        ),
        "failed_scientific_calls": dict(
            sum((Counter(c["failed_scientific_calls"]) for c in cases), Counter())
        ),
        "cases": cases,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("experiment", type=Path)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    traces = [
        json.loads(f.read_text())
        for f in sorted((a.experiment / "trajectories").glob("*/trajectory.json"))
    ]
    questions = [
        json.loads(s)
        for s in (root / "tasks/questions.jsonl").read_text().splitlines()
        if s.strip()
    ]
    refs = [
        json.loads(s)
        for s in (root / "evaluation/references.jsonl").read_text().splitlines()
        if s.strip()
    ]
    qmap = {q["id"]: q for q in questions}
    ref_lengths = {r["id"]: len(r["tool_path"]) for r in refs}
    result = {
        "experiment": str(a.experiment),
        "review_scope": "Aggregate protocol and budgets only; no scientific tools executed.",
        "first_251": summarize(traces[:251]),
        "all_at_stop": summarize(traces),
        "public_scientific_budgets": dict(
            Counter(q["max_tool_calls"] for q in questions)
        ),
        "reference_call_lengths": distribution(list(ref_lengths.values())),
        "long_reference_tasks": [
            {
                "id": i,
                "reference_calls": n,
                "public_scientific_budget": qmap[i]["max_tool_calls"],
            }
            for i, n in ref_lengths.items()
            if n > 15
        ],
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    compact = {
        k: {kk: vv for kk, vv in result[k].items() if kk != "cases"}
        for k in ["first_251", "all_at_stop"]
    }
    compact.update(
        {
            k: result[k]
            for k in [
                "public_scientific_budgets",
                "reference_call_lengths",
                "long_reference_tasks",
            ]
        }
    )
    print(json.dumps(compact, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
