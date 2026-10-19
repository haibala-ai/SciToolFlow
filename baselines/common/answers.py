"""Explain public answer structure without consulting reference values or traces."""

import json


class AnswerFormatError(ValueError):
    pass


def answer_format(schema):
    """Build an illustrative tree from required keys/types, never examples/defaults."""

    def template(node, depth=0):
        if not isinstance(node, dict) or depth > 30:
            return "<FILL:value from evidence>"
        kind = node.get("type")
        if kind == "object" or "properties" in node:
            return {
                name: template(node.get("properties", {}).get(name, {}), depth + 1)
                for name in node.get("required", [])
            }
        if kind == "array":
            return [template(node.get("items", {}), depth + 1)]
        label = "|".join(kind) if isinstance(kind, list) else (kind or "value")
        return "<FILL:" + label + " from evidence>"

    layout = []

    def object_layout(node, path="/finish", depth=0):
        if not isinstance(node, dict) or depth > 4 or len(layout) >= 16:
            return
        required = node.get("required", [])
        if len(required) > 1:
            layout.append({"object_path": path, "sibling_keys": list(required)})
        for name in required:
            object_layout(
                node.get("properties", {}).get(name, {}), path + "/" + name, depth + 1
            )
        if node.get("type") == "array":
            object_layout(node.get("items", {}), path + "/*", depth + 1)

    object_layout(schema)
    return {
        "finish_template": {"finish": template(schema)},
        "object_layout": layout,
        "instructions": [
            "This is a STRUCTURE TEMPLATE, not an answer. Replace every <FILL:...> placeholder with a correctly typed value supported by the task inputs or actual observations.",
            "Preserve the exact object nesting. Siblings shown under results must stay directly under results, not inside another sibling object.",
            "An illustrative array item shows item structure only; determine the actual array length from evidence, not this template.",
            "Do not submit literal placeholders. Do not invent values, use zero as missing data, or insert null unless the public schema allows it.",
            "Put all answer content inside finish. If required evidence is unavailable, use stop with a reason. The full public answer_schema remains authoritative.",
        ],
        "source": "public answer_schema required keys and types only",
    }


def render_answer_format(guide):
    return (
        "FINAL ANSWER FORMAT — structure only, no answer values\n"
        + json.dumps(guide["finish_template"], ensure_ascii=False, indent=2)
        + "\nOBJECT NESTING — keys on each line are siblings, not containers for each other:\n"
        + "\n".join(
            row["object_path"] + ": " + ", ".join(row["sibling_keys"])
            for row in guide.get("object_layout", [])
        )
        + "\n"
        + "\n".join(guide["instructions"])
    )


def contains_placeholder(value):
    if isinstance(value, str):
        return value.startswith("<FILL:") and value.endswith(">")
    if isinstance(value, dict):
        return any(contains_placeholder(v) for v in value.values())
    if isinstance(value, list):
        return any(contains_placeholder(v) for v in value)
    return False


def correction_decision_schema(schema, *, max_actions=8):
    """Constrain structure after a bad finish; keep every decision available.

    Only public keys/types/required nesting are copied. Scientific literals,
    descriptions, examples, bounds, enums and array lengths are not exported.
    Citations remain legal at every answer node and are verified at execution.
    """
    citation = {
        "type": "object",
        "properties": {
            "$observation": {"type": "string"},
            "field": {
                "type": "array",
                "items": {"anyOf": [{"type": "string"}, {"type": "integer"}]},
            },
            "decode": {"type": "string", "enum": ["json_array"]},
        },
        "required": ["$observation"],
        "additionalProperties": False,
    }

    def shape(node):
        if not isinstance(node, dict):
            return {}
        result = {}
        if "type" in node:
            result["type"] = node["type"]
        for union in ["anyOf", "oneOf"]:
            if union in node:
                result["anyOf"] = [shape(branch) for branch in node[union]]
        if "properties" in node:
            result.update(
                type="object",
                properties={k: shape(v) for k, v in node["properties"].items()},
            )
            if "required" in node:
                result["required"] = list(node["required"])
            if "additionalProperties" in node:
                additional = node["additionalProperties"]
                result["additionalProperties"] = (
                    shape(additional) if isinstance(additional, dict) else additional
                )
        if "items" in node:
            result["items"] = shape(node["items"])
        return {"anyOf": [result, citation]} if result else {}

    def operation(name, value):
        return {
            "type": "object",
            "properties": {name: value, "intent": {"type": "string"}},
            "required": [name],
            "additionalProperties": False,
        }

    action = {
        "type": "object",
        "properties": {"tool": {"type": "string"}, "arguments": {"type": "object"}},
        "required": ["tool", "arguments"],
        "additionalProperties": False,
    }
    inspect = {
        "type": "object",
        "properties": {
            "observation_id": {"type": "string"},
            "field": citation["properties"]["field"],
            "part": {"type": "string", "enum": ["output", "arguments"]},
            "offset": {"type": "integer", "minimum": 0},
        },
        "required": ["observation_id"],
        "additionalProperties": False,
    }
    return {
        "anyOf": [
            operation(
                "actions",
                {
                    "type": "array",
                    "items": action,
                    "minItems": 1,
                    "maxItems": max_actions,
                },
            ),
            operation("think", {"type": "string"}),
            operation("inspect", inspect),
            operation("finish", shape(schema)),
            operation(
                "stop",
                {
                    "type": "object",
                    "properties": {"reason": {"type": "string"}},
                    "required": ["reason"],
                    "additionalProperties": False,
                },
            ),
        ]
    }


def protocol_decision_schema(
    tool_names,
    *,
    max_actions=8,
    answer_schema=None,
    known_inputs=None,
    allow_think=True
):
    """Public wire syntax plus input types already revealed by discovery/feedback.

    Unqueried scientific tools keep unconstrained argument objects. No reference
    values, inferred scientific defaults or unseen tool contracts are exported.
    """
    result = correction_decision_schema(
        answer_schema or {"type": "object"}, max_actions=max(1, max_actions)
    )
    if not tool_names or max_actions <= 0:
        result["anyOf"] = result["anyOf"][1:]
    else:
        action = result["anyOf"][0]["properties"]["actions"]["items"]
        names = sorted(set(tool_names))
        known_inputs = known_inputs or {}
        choices = []
        for name in names:
            if name not in known_inputs:
                continue
            arguments = correction_decision_schema(known_inputs[name])["anyOf"][3][
                "properties"
            ]["finish"]
            choices.append(
                {
                    "type": "object",
                    "properties": {
                        "tool": {"type": "string", "enum": [name]},
                        "arguments": arguments,
                    },
                    "required": ["tool", "arguments"],
                    "additionalProperties": False,
                }
            )
        unknown = [name for name in names if name not in known_inputs]
        if unknown:
            action["properties"]["tool"]["enum"] = unknown
            choices.append(action)
        result["anyOf"][0]["properties"]["actions"]["items"] = (
            choices[0] if len(choices) == 1 else {"anyOf": choices}
        )
    if not allow_think:
        result["anyOf"] = [
            option for option in result["anyOf"] if "think" not in option["properties"]
        ]
    return result
