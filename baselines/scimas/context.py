"""Lossless, prefix-stable serialization for independent SciMas role requests.

Keep public inputs and the current graph before changing execution state. This
exposes reusable prefixes to a serving backend without sharing conversations,
discarding evidence, or assuming that the provider actually caches any tokens.
"""

import json


def ordered_context(payload):
    stable = ("task", "public_assets", "requirements", "graph", "contracts")
    return {
        **{key: payload[key] for key in stable if key in payload},
        **{key: value for key, value in payload.items() if key not in stable},
    }


def encode_payload(payload):
    return json.dumps(
        payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")
    )


def role_messages(prompt, payload, schema, feedback=None):
    stable_keys = {"task", "public_assets", "requirements", "graph", "contracts"}
    ordered = ordered_context(payload)
    stable = {k: v for k, v in ordered.items() if k in stable_keys}
    dynamic = {k: v for k, v in ordered.items() if k not in stable_keys}
    return [
        {
            "role": "system",
            "content": prompt
            + "\nThe user messages supply complementary context fields for this single decision. Combine them; response_schema defines the reply. No previous conversation is assumed.",
        },
        {"role": "user", "content": encode_payload({"context": stable})},
        {
            "role": "user",
            "content": encode_payload(
                {
                    "response_schema": schema,
                    "context": dynamic,
                    "format_feedback": feedback,
                }
            ),
        },
    ]


def request_payload(messages):
    """Reconstruct the public request for offline tests/analysis, not generation."""
    payload = {}
    for message in messages:
        if message["role"] != "user":
            continue
        part = json.loads(message["content"])
        if "context" in part:
            part["context"] = {**payload.get("context", {}), **part["context"]}
        payload.update(part)
    return payload


def request_diagnostics(messages, previous=None):
    """Character counts are diagnostics, never token usage or cache-hit claims."""
    total = sum(len(m["content"]) for m in messages)
    prefix = 0
    for current, old in zip(messages, previous or []):
        if current["role"] != old["role"]:
            break
        a, b = current["content"], old["content"]
        common = 0
        for x, y in zip(a, b):
            if x != y:
                break
            common += 1
        prefix += common
        if a != b:
            break
    return {"input_chars": total, "same_role_prefix_chars": prefix}
