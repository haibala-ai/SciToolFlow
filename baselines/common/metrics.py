"""Per-attempt runtime, dispatcher calls and provider-reported generation tokens."""


def task_metrics(
    usage, calls, *, runtime_seconds=None, pending_calls=(), finished=False
):
    """Summarize a ledger without treating missing measurements as zero.

    Calls are dispatcher attempts, including discovery and failed/retried calls.
    Pending calls have been dispatched but have no result yet. Tokens cover the
    shared generation ledger; retrieval embeddings keep their separate ledger.
    """
    usage = usage or {}
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
    return {
        "schema_version": "task-metrics.v1",
        "runtime_seconds": (
            runtime_seconds
            if runtime_seconds is not None
            else usage.get("elapsed_seconds")
        ),
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
