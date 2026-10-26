"""Content-addressed literal deduplication; never evaluate code or read files."""

import hashlib
import json


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def resolve(expression, constants):
    if set(expression) == {"value"}:
        return expression["value"]
    if expression.get("operation") != "literal_constant":
        raise ValueError("Not a declared literal expression")
    args = expression.get("args")
    if not isinstance(args, list) or len(args) != 1 or set(args[0]) != {"value"}:
        raise ValueError("Literal constant needs one explicit content key")
    key = args[0]["value"]
    if not isinstance(key, str) or key not in constants:
        raise ValueError("Unknown literal constant")
    return constants[key]


def validate(constants):
    if not isinstance(constants, dict):
        raise ValueError("Workflow constants must be an object")
    for key, value in constants.items():
        if not isinstance(key, str) or digest(value) != key:
            raise ValueError("Workflow literal constant content hash mismatch")


def compact(spec, threshold=1024):
    """Replace only literal operands, preserving all predicates and data exactly."""
    pool = dict(spec.get("constants", {}))

    def walk(value):
        if isinstance(value, dict):
            if set(value) == {"value"}:
                encoded = json.dumps(
                    value["value"], ensure_ascii=False, allow_nan=False
                )
                if len(encoded) >= threshold:
                    key = digest(value["value"])
                    pool[key] = value["value"]
                    return {"operation": "literal_constant", "args": [{"value": key}]}
                return value
            return {k: walk(v) for k, v in value.items() if k != "constants"}
        if isinstance(value, list):
            return [walk(v) for v in value]
        return value

    result = walk(spec)
    if pool:
        result["constants"] = pool
    return result


def expand(spec):
    pool = spec.get("constants", {})
    validate(pool)

    def walk(value):
        if isinstance(value, dict):
            if value.get("operation") == "literal_constant":
                return {"value": resolve(value, pool)}
            return {k: walk(v) for k, v in value.items() if k != "constants"}
        if isinstance(value, list):
            return [walk(v) for v in value]
        return value

    return walk(spec)
