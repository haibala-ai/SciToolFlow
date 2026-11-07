"""Public, deliberately restricted planning language; no executable expressions."""


def obj(properties, required=None):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties) if required is None else required,
        "additionalProperties": False,
    }


TEXT = {"type": "string", "minLength": 1}
ID_MAX_LENGTH = 80
ID = {"type": "string", "pattern": rf"^[A-Za-z][A-Za-z0-9_-]{{0,{ID_MAX_LENGTH - 1}}}$"}
PATH = {
    "type": "array",
    "maxItems": 32,
    "items": {"anyOf": [{"type": "string"}, {"type": "integer", "minimum": 0}]},
}
REF = {"$ref": "#/$defs/binding"}
EXPR = {"$ref": "#/$defs/condition"}
SEMANTICS = obj({key: TEXT for key in ("unit", "object_id", "method", "concept")}, [])
BINDING = {
    "oneOf": [
        obj({"kind": {"const": "literal"}, "value": {}}),
        obj({"kind": {"const": "task"}, "path": PATH}),
        obj({"kind": {"const": "item"}, "path": PATH}),
        obj(
            {
                "kind": {"enum": ["node", "collect"]},
                "node": ID,
                "path": PATH,
                "decoded": {"type": "boolean"},
                "expect": SEMANTICS,
            },
            ["kind", "node", "path"],
        ),
        obj(
            {
                "kind": {"const": "list"},
                "items": {"type": "array", "items": REF},
                "provenance": {"type": "array", "items": REF},
            },
            ["kind", "items"],
        ),
        obj({
            "kind": {"const": "python_code"},
            "code": {"type": "string", "minLength": 1, "maxLength": 12000},
            "inputs": {"type": "object", "minProperties": 1, "maxProperties": 16,
                       "propertyNames": {"pattern": "^[A-Za-z][A-Za-z0-9_]{0,63}$"},
                       "additionalProperties": REF},
        }),
    ]
}
CONDITION = {
    "oneOf": [
        obj(
            {
                "op": {"enum": ["all", "any"]},
                "args": {"type": "array", "minItems": 1, "items": EXPR},
            }
        ),
        obj({"op": {"const": "not"}, "arg": EXPR}),
        obj(
            {
                "op": {"enum": ["eq", "ne", "lt", "le", "gt", "ge", "in"]},
                "left": REF,
                "right": REF,
                "evidence": TEXT,
            }
        ),
    ]
}
REQUIREMENT = obj(
    {
        "id": ID,
        "description": TEXT,
        "evidence": TEXT,
        "mode": {"enum": ["complete", "screen"]},
    }
)
NODE = obj(
    {
        "id": ID,
        "tool": TEXT,
        "purpose": TEXT,
        "object": TEXT,
        "arguments": {"type": "object", "additionalProperties": REF},
        "when": EXPR,
        "for_each": REF,
        "checks": {
            "type": "array",
            "items": obj(
                {
                    "path": PATH,
                    "decoded": {"type": "boolean"},
                    "schema": {"type": "object"},
                },
                ["path", "schema"],
            ),
        },
        "semantics": SEMANTICS,
    },
    ["id", "tool", "purpose", "object", "arguments"],
)
DECOMPOSITION_SCHEMA = obj(
    {
        "requirements": {
            "type": "array",
            "minItems": 1,
            "maxItems": 64,
            "items": REQUIREMENT,
        },
        "queries": {"type": "array", "minItems": 1, "maxItems": 24, "items": TEXT},
    }
)
PLAN_SCHEMA = obj(
    {
        "nodes": {"type": "array", "minItems": 1, "maxItems": 256, "items": NODE},
        "deliverables": {
            "type": "array",
            "minItems": 1,
            "items": obj(
                {
                    "requirement": ID,
                    "nodes": {
                        "type": "array",
                        "minItems": 1,
                        "uniqueItems": True,
                        "items": ID,
                    },
                    "description": TEXT,
                }
            ),
        },
    }
)
PLAN_SCHEMA["$defs"] = {"binding": BINDING, "condition": CONDITION}


def decoding_schema(schema):
    """A grammar-compatible superset; the complete schema still validates every reply.

    vLLM's guidance backend does not implement uniqueItems. Removing it only
    from constrained decoding avoids HTTP 400 without accepting duplicates.
    """
    if isinstance(schema, dict):
        return {k: decoding_schema(v) for k, v in schema.items() if k != "uniqueItems"}
    if isinstance(schema, list):
        return [decoding_schema(v) for v in schema]
    return schema
