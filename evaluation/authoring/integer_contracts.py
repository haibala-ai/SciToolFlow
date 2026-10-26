"""Exact public integer outcomes; continuous scientific quantities keep tolerances."""

import copy


def schema_at(schema, path):
    for token in path.split("/")[1:]:
        token = token.replace("~1", "/").replace("~0", "~")
        if token.isdigit() and schema.get("type") == "array":
            schema = schema.get("items", {})
        else:
            schema = schema.get("properties", {}).get(token, {})
    return schema


def numeric_leaves(value, schema, pointer=""):
    if type(value) in (int, float):
        ty = schema.get("type")
        types = ty if isinstance(ty, list) else [ty]
        yield pointer, "integer" in types
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from numeric_leaves(
                v, schema.get("items", {}), pointer + "/" + str(i)
            )
    elif isinstance(value, dict):
        for key, v in value.items():
            child = schema.get("properties", {}).get(
                key, schema.get("additionalProperties", {})
            )
            if not isinstance(child, dict):
                child = {}
            yield from numeric_leaves(
                v, child, pointer + "/" + key.replace("~", "~0").replace("/", "~1")
            )


def apply(public, hidden):
    decisions = []
    for outcome in hidden["evaluation"]["outcomes"]:
        left = outcome.get("left", {})
        if (
            left.get("source") != "answer"
            or outcome["op"] != "eq"
            or "value" not in outcome
        ):
            continue
        schema = schema_at(public["answer_schema"], left.get("path", ""))
        leaves = list(numeric_leaves(outcome["value"], schema))
        integers = [path for path, is_integer in leaves if is_integer]
        if not integers:
            continue
        if len(integers) != len(leaves):
            decisions.append(
                {
                    "outcome": outcome["id"],
                    "status": "mixed_continuous_and_integer_target_requires_leafwise_review",
                    "integer_paths": integers,
                }
            )
            continue
        changed = bool(outcome.get("atol", 0) or outcome.get("rtol", 0))
        outcome["atol"] = outcome["rtol"] = 0
        decisions.append(
            {
                "outcome": outcome["id"],
                "status": "exact_public_integer_contract",
                "criteria_changed": changed,
                "integer_paths": integers,
                "expected": copy.deepcopy(outcome["value"]),
            }
        )
    return decisions
