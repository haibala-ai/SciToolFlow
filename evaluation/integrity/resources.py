"""Versioned experiment resource checks, separate from scientific task criteria."""

import math

VERSION = "task-resources.v1"


def validate_policy(value):
    if not isinstance(value, dict) or value.get("version") != VERSION:
        raise ValueError("Unsupported experiment resource policy")
    if (
        type(value.get("max_model_requests")) is not int
        or value["max_model_requests"] < 1
    ):
        raise ValueError("Invalid experiment model request limit")
    seconds = value.get("task_seconds")
    if (
        isinstance(seconds, bool)
        or not isinstance(seconds, (float, int))
        or not math.isfinite(seconds)
        or seconds <= 0
    ):
        raise ValueError("Invalid experiment time limit")
    for field in [
        "scientific_calls",
        "decisions",
        "discovery_calls",
        "think_steps",
        "consecutive_thinks",
    ]:
        limit = value.get(field)
        if limit is not None and (
            type(limit) is not int
            or limit < (0 if field in {"think_steps", "discovery_calls"} else 1)
        ):
            raise ValueError("Invalid optional experiment limit: " + field)
    return value


def check_resources(row, policy):
    usage, limits = row.get("_resource_usage"), row.get("_execution_limits")
    if not isinstance(usage, dict) or not isinstance(limits, dict):
        raise ValueError(
            "Current resource policy requires an authenticated trace ledger"
        )
    if (
        usage.get("policy_version") != VERSION
        or limits.get("resource_policy") != VERSION
    ):
        raise ValueError("Trace resource policy differs from experiment")
    if (
        usage.get("max_model_requests") != policy["max_model_requests"]
        or usage.get("task_seconds") != policy["task_seconds"]
        or limits.get("model_requests") != policy["max_model_requests"]
        or limits.get("task_seconds") != policy["task_seconds"]
    ):
        raise ValueError("Trace and experiment resource limits differ")
    for key in [
        "scientific_calls",
        "decisions",
        "discovery_calls",
        "think_steps",
        "consecutive_thinks",
    ]:
        if limits.get(key) != policy.get(key):
            raise ValueError("Trace and experiment optional limits differ: " + key)
    requests = usage.get("requests")
    if (
        not isinstance(requests, list)
        or type(usage.get("model_requests")) is not int
        or len(requests) != usage["model_requests"]
    ):
        raise ValueError("Invalid generation request ledger")
    elapsed = usage.get("elapsed_seconds")
    if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0:
        raise ValueError("Invalid task resource duration")
    for i, request in enumerate(requests, 1):
        if (
            not isinstance(request, dict)
            or type(request.get("request")) is not int
            or request["request"] != i
            or not isinstance(request.get("phase"), str)
            or request.get("status") not in {"returned", "error", "pending"}
        ):
            raise ValueError("Invalid generation request event")
    if row.get("completed") and (
        not requests
        or row.get("_model_steps") != len(requests)
        or any(r["status"] == "pending" for r in requests)
    ):
        raise ValueError("Completed model trace has an incomplete request ledger")
    science = sum(c["tool"] != "DescribeTools" for c in row.get("calls", []))
    exceeded = (
        len(requests) > policy["max_model_requests"]
        or elapsed >= policy["task_seconds"]
    )
    if policy.get("scientific_calls") is not None:
        exceeded |= science > policy["scientific_calls"]
    if policy.get("decisions") is not None:
        exceeded |= row.get("_model_steps", 0) > policy["decisions"]
    for field, observed in [
        (
            "discovery_calls",
            sum(c["tool"] == "DescribeTools" for c in row.get("calls", [])),
        ),
        ("think_steps", row.get("_think_steps", 0)),
        ("consecutive_thinks", row.get("_consecutive_thinks", 0)),
    ]:
        if policy.get(field) is not None:
            exceeded |= observed > policy[field]
    prompt = completion = 0
    missing_prompt = missing_completion = missing = 0
    for request in requests:
        detail = request.get("usage") if isinstance(request.get("usage"), dict) else {}
        p, c = detail.get("prompt_tokens"), detail.get("completion_tokens")
        if type(p) is int and p >= 0:
            prompt += p
        else:
            missing_prompt += 1
        if type(c) is int and c >= 0:
            completion += c
        else:
            missing_completion += 1
        if not (type(p) is int and p >= 0 and type(c) is int and c >= 0):
            missing += 1
    return {
        "verified": True,
        "policy_version": VERSION,
        "exceeded": bool(exceeded),
        "model_requests": len(requests),
        "elapsed_seconds": elapsed,
        "prompt_tokens": None if missing_prompt else prompt,
        "completion_tokens": None if missing_completion else completion,
        "observed_prompt_tokens": prompt,
        "observed_completion_tokens": completion,
        "requests_with_incomplete_token_usage": missing,
    }
