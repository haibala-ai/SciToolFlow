"""Scientific call budgets and dependency-aware plan comparison."""

from collections import Counter
import json, math, re


def arguments_match(tool, expected, actual, optional=frozenset()):
    """Exact match, or the reference keys plus explicitly optional extra arguments.

    Passing an optional parameter explicitly (a chain selector, a threshold, a timeout)
    must not break an otherwise identical path, so extra actual keys are tolerated when
    the tool declares them optional and every reference key is still present.
    """
    from .comparison import arguments_equal

    if arguments_equal(tool, expected, actual):
        return True
    if not isinstance(actual, dict) or not isinstance(expected, dict):
        return False

    # The pool mixes PDB_id/PDB_name/pdb_id for the same concept, so a name that differs
    # only in case or separators identifies the same argument and must not fail the path.
    def normalise(key):
        return re.sub(r"[^a-z0-9]", "", str(key).lower())

    if {normalise(k) for k in actual} == {normalise(k) for k in expected}:
        renamed = {
            next(k for k in expected if normalise(k) == normalise(key)): value
            for key, value in actual.items()
        }
        if arguments_equal(tool, expected, renamed):
            return True
    extra = set(actual) - set(expected)
    if not extra or not extra <= set(optional) or not set(expected) <= set(actual):
        return False
    if not isinstance(optional, dict) or any(
        not arguments_equal(tool, {k: optional[k]}, {k: actual[k]}) for k in extra
    ):
        return False
    narrowed = {key: actual[key] for key in expected}
    return arguments_equal(tool, expected, narrowed)


def score_plan(reference, calls, aliases, optional=None):
    """Topological reference matching; order-free between independent branches.

    Returns the strict result plus the recall that drives partial credit.  Calls with
    equal arguments to the same tool (for example one molecule per call) match in any
    order, which is what concurrent execution produces.
    """
    from .comparison import arguments_equal

    if "DescribeTools" in reference.get("tool_path", []):
        raise ValueError("DescribeTools cannot be a reference scientific tool")
    calls = [
        c for c in calls if aliases.get(c.get("tool"), c.get("tool")) != "DescribeTools"
    ]
    required = list(reference.get("necessary_observation_ids") or [])
    parents = {
        step: {
            edge["from"]
            for edge in reference.get("dependency_graph", {}).get("edges", [])
            if edge["to"] == step
        }
        for step in required
    }
    expected = {
        step: event for step, event in zip(required, _reference_events(reference))
    }
    # A trace may open with an export-provenance record, which is not a tool call: it names no
    # tool. Requiring a tool name keeps that header out of the call counts.
    successful = [
        c
        for c in calls
        if isinstance(c, dict)
        and c.get("tool")
        and c.get("status", "success") == "success"
    ]
    positions, matched = {}, []
    for index, call in enumerate(successful):
        tool = aliases.get(call.get("tool"), call.get("tool"))
        for step in required:
            if step in positions or expected[step]["tool"] != tool:
                continue
            if not parents[step] <= set(positions):
                continue
            arguments = call.get("arguments", call.get("input"))
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except ValueError:
                    continue
            if arguments_match(
                tool,
                expected[step]["arguments"],
                arguments,
                (optional or {}).get(tool, frozenset()),
            ):
                positions[step] = index
                matched.append(step)
                break
    recall = len(matched) / len(required) if required else 1.0
    counts = Counter(aliases.get(c.get("tool"), c.get("tool")) for c in successful)
    wanted = Counter(reference.get("tool_path", []))
    tool_recall = (
        (sum(min(counts[t], n) for t, n in wanted.items()) / sum(wanted.values()))
        if wanted
        else 1.0
    )
    return {
        "dataflow_pass": len(matched) == len(required),
        "matched_steps": matched,
        "unmatched_steps": [s for s in required if s not in positions],
        "step_recall": recall,
        "tool_occurrence_recall": tool_recall,
        "successful_calls": len(successful),
        "extra_calls": max(0, len(successful) - len(positions)),
    }


def _reference_events(reference):
    """Resolved expected tool+arguments per necessary observation, from the reference trace."""
    events = reference.get("_resolved_events")
    if events:
        return [events[step] for step in reference["necessary_observation_ids"]]
    return [
        {
            "tool": (
                reference["tool_path"][index]
                if index < len(reference["tool_path"])
                else None
            ),
            "arguments": {},
        }
        for index, _ in enumerate(reference["necessary_observation_ids"])
    ]


def budget_for(reference, minimum=32, factor=1.5, extra=5, cap=128):
    """Per-task call budget from the reference length, so long tasks keep retry room."""
    return min(
        cap,
        max(
            minimum,
            int(math.ceil(len(reference.get("tool_path", [])) * factor)) + extra,
        ),
    )


def reference_events(reference, trace_root):
    """Resolved reference tool_result events keyed by observation id."""
    if reference.get("_resolved_events"):
        return reference["_resolved_events"]
    from pathlib import Path

    path = Path(trace_root) / reference["reference_trace"]
    events = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        kind = event.get("event")
        if kind == "finish" or "observation_id" not in event:
            continue
        if kind in (None, "tool_result"):
            events[event["observation_id"]] = {
                "tool": event.get("tool"),
                "arguments": event.get("arguments") or event.get("input") or {},
                "status": event.get("status", "success"),
            }
    reference["_resolved_events"] = events
    return events
