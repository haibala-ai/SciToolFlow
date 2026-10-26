"""Complete JSON Schema validation for public tool input and output contracts."""

from functools import lru_cache
import json
import math
from jsonschema import Draft202012Validator


@lru_cache(maxsize=512)
def _validator(encoded):
    schema = json.loads(encoded)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _json_errors(value, path="$", depth=0):
    if depth > 64:
        return [path + ": JSON nesting exceeds64 levels"]
    if value is None or type(value) in (str, bool, int):
        return []
    if type(value) is float:
        return [] if math.isfinite(value) else [path + ": number must be finite"]
    if isinstance(value, list):
        return [
            e
            for i, v in enumerate(value)
            for e in _json_errors(v, path + "[" + str(i) + "]", depth + 1)
        ]
    if isinstance(value, dict) and all(isinstance(k, str) for k in value):
        return [
            e
            for k, v in value.items()
            for e in _json_errors(v, path + "." + k, depth + 1)
        ]
    return [path + ": require a JSON value with string object keys"]


def contract_errors(value, schema):
    """Check finite JSON values and all declared JSON Schema keywords."""
    errors = _json_errors(value)
    if errors:
        return errors[:8]
    validator = _validator(json.dumps(schema, sort_keys=True, ensure_ascii=False))
    found = sorted(
        validator.iter_errors(value), key=lambda e: str(list(e.absolute_path))
    )
    return [
        (
            "$"
            + "".join(
                "[" + str(p) + "]" if isinstance(p, int) else "." + p
                for p in error.absolute_path
            )
            + ": "
            + error.message
        )
        for error in found[:8]
    ]
