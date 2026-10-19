"""Public answer contracts and standard-library validation; no reference values in schemas."""

import math
import re

OPTIONAL_METADATA = {
    "evidence",
    "observations",
    "observation",
    "observation_id",
    "provenance",
    "task",
    "task_id",
    "failures_worked_around",
}
DYNAMIC_KEY = re.compile(r"^(?:mp-\d+|o\d+|\d+|[A-Z0-9]{12,})$")


def answer_schema(value):
    if isinstance(value, dict):
        if value and all(DYNAMIC_KEY.fullmatch(str(k)) for k in value):
            options = []
            for v in value.values():
                s = answer_schema(v)
                if s not in options:
                    options.append(s)
            return {
                "type": "object",
                "additionalProperties": (
                    options[0] if len(options) == 1 else {"anyOf": options}
                ),
                "minProperties": 1,
            }
        properties = {k: answer_schema(v) for k, v in value.items()}
        return {
            "type": "object",
            "properties": properties,
            "required": [k for k in properties if k not in OPTIONAL_METADATA],
            "additionalProperties": True,
        }
    if isinstance(value, list):
        options = []
        for v in value:
            schema = answer_schema(v)
            if schema not in options:
                options.append(schema)
        return {
            "type": "array",
            "items": (
                options[0]
                if len(options) == 1
                else ({"anyOf": options} if options else {})
            ),
        }
    if isinstance(value, bool):
        return {"type": "boolean"}
    if value is None:
        return {"type": ["null", "string", "number", "boolean", "object", "array"]}
    if isinstance(value, (int, float)):
        return {"type": "number"}
    return {"type": "string"}


def validation_errors(value, schema, path="$"):
    """Validate the generated schema subset without optional scientific dependencies."""
    if not isinstance(schema, dict):
        return [path + ": schema must be an object"]

    def same_literal(left, right):
        if isinstance(left, bool) or isinstance(right, bool):
            return type(left) is type(right) and left == right
        return left == right

    if "enum" in schema and not any(
        same_literal(value, item) for item in schema["enum"]
    ):
        return [path + ": value outside allowed categories"]
    if "const" in schema and not same_literal(value, schema["const"]):
        return [path + ": value differs from required literal"]
    if "anyOf" in schema:
        return (
            []
            if any(not validation_errors(value, s, path) for s in schema["anyOf"])
            else [path + ": no allowed type matches"]
        )
    types = schema.get("type", [])
    types = [types] if isinstance(types, str) else types
    predicates = {
        "object": lambda: isinstance(value, dict),
        "array": lambda: isinstance(value, list),
        "string": lambda: isinstance(value, str),
        "boolean": lambda: type(value) is bool,
        "null": lambda: value is None,
        "number": lambda: type(value) in (int, float) and math.isfinite(value),
        "integer": lambda: type(value) is int,
    }
    if types and not any(predicates[t]() for t in types):
        return [path + ": wrong value type"]
    errors = []
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        errors.extend(
            path + "." + k + ": required field missing"
            for k in schema.get("required", [])
            if k not in value
        )
        if len(value) < schema.get("minProperties", 0):
            errors.append(path + ": empty object")
        for key, child in value.items():
            if key in properties:
                errors.extend(
                    validation_errors(child, properties[key], path + "." + key)
                )
            elif isinstance(schema.get("additionalProperties"), dict):
                errors.extend(
                    validation_errors(
                        child, schema["additionalProperties"], path + "." + key
                    )
                )
            elif schema.get("additionalProperties") is False:
                errors.append(path + "." + key + ": unknown field")
    if isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(
                validation_errors(child, schema.get("items", {}), path + f"[{index}]")
            )
    return errors
