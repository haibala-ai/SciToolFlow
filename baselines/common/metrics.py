"""Per-attempt runtime, dispatcher calls and provider-reported generation tokens."""
from src.utils.timing import interval_seconds, subtract_intervals


def task_metrics(
    usage, calls, *, runtime_seconds=None, pending_calls=(), finished=False,
    communication_wait_seconds=0, infrastructure_failure=None,
    communication_intervals=(),
    runtime_started_monotonic=None,
):
    """Summarize a ledger without treating missing measurements as zero.

    Calls are dispatcher attempts, including discovery and failed/retried calls.
    Pending calls have been dispatched but have no result yet. Tokens cover the
    shared generation ledger; retrieval embeddings keep their separate ledger.
    """
    usage = usage or {}
    if finished and not infrastructure_failure:
        requests = usage.get("requests", [])
        if requests and requests[-1].get("status") == "error":
            infrastructure_failure = requests[-1].get("infrastructure_failure")
    known = type(usage.get("model_requests")) is int
    input_tokens = usage.get("prompt_tokens") if known else None
    output_tokens = usage.get("completion_tokens") if known else None
    measured_calls = None if calls is None else [*calls, *pending_calls]
    discovery = (
        None
        if measured_calls is None
        else sum(c["tool"] == "DescribeTools" for c in measured_calls)
    )
    count = None if measured_calls is None else len(measured_calls)
    wall = runtime_seconds if runtime_seconds is not None else usage.get("elapsed_seconds")
    intervals = [*usage.get("communication_intervals", []), *communication_intervals]
    start = (runtime_started_monotonic if runtime_started_monotonic is not None
             else usage.get("clock_started_monotonic"))
    bounds = (start, start + wall) if start is not None and wall is not None else None
    network_fault = (interval_seconds(intervals, bounds=bounds) if intervals else
                    usage.get("communication_fault_seconds", 0) + communication_wait_seconds)
    work = list(usage.get("model_work_intervals", []))
    origin = usage.get("clock_started_monotonic")
    for call in measured_calls or []:
        if "started_seconds" in call and "finished_seconds" in call and origin is not None:
            work.append([origin + call["started_seconds"], origin + call["finished_seconds"]])
        elif "started" in call and bounds is not None:
            # Pending SciMas calls carry an absolute dispatch timestamp.
            work.append([call["started"], bounds[1]])
    excluded = subtract_intervals(intervals, work, bounds=bounds) if intervals else []
    network_wait = interval_seconds(excluded) if intervals else network_fault
    active = max(0, wall - network_wait) if wall is not None else None
    # An API-aborted attempt is not an efficiency sample. Its partial work and
    # wall time remain auditable; successful request latency still counts.
    reportable = wall is not None and not (finished and infrastructure_failure)
    return {
        "schema_version": "task-metrics.v2",
        "runtime_seconds": active if reportable else None,
        "active_runtime_seconds": active,
        "wall_runtime_seconds": wall,
        "communication_wait_seconds": network_wait,
        "communication_fault_seconds": network_fault,
        "communication_overlap_seconds": max(0, network_fault - network_wait),
        "excluded_communication_intervals": excluded,
        "runtime_reportable": reportable,
        "tool_calls": count,
        "scientific_tool_calls": None if count is None else count - discovery,
        "discovery_tool_calls": discovery,
        "tool_calls_complete": finished and calls is not None and not pending_calls,
        "model_requests": usage.get("model_requests"),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": (
            input_tokens + output_tokens
            if input_tokens is not None and output_tokens is not None
            else None
        ),
        "observed_input_tokens": usage.get("observed_prompt_tokens") if known else None,
        "observed_output_tokens": (
            usage.get("observed_completion_tokens") if known else None
        ),
        "requests_missing_input_usage": (
            usage.get("requests_missing_prompt_usage") if known else None
        ),
        "requests_missing_output_usage": (
            usage.get("requests_missing_completion_usage") if known else None
        ),
        "token_usage_complete": bool(known and usage.get("token_usage_complete")),
    }
