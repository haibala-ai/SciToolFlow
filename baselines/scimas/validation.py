"""Structural proofs and explicit runtime obligations for SciMas task graphs."""

import json
import keyword
from graphlib import TopologicalSorter, CycleError
from jsonschema import Draft202012Validator
from tools.runtime.contracts import contract_errors
from tools.runtime.scope import tool_allowed
from .schema import PLAN_SCHEMA, DECOMPOSITION_SCHEMA
from .task_graph import at, bindings, digest, node_dependencies


def output_schema(spec, decoded=False):
    if not decoded:
        return spec["output_schema"]
    encoding = spec.get("output_encoding", {})
    if spec["output_schema"].get("type") != "string":
        raise ValueError(
            "JSON decoding is not needed: this output is already structured. Set decoded=false or omit decoded in bindings AND output checks."
        )
    if encoding.get("decoded_type") not in {"json_object", "json_array"}:
        raise ValueError(
            "JSON decoding is not declared: this tool returns plain text, with no addressable JSON fields."
        )
    return encoding.get("decoded_schema", {})


def path_schema(schema, path, *, allow_wildcards=False):
    """Project a contract path, preserving open JSON and combined constraints.

    A projected schema is a possibility check. Actual field presence, array
    bounds and the complete receiving contract are always checked at runtime.
    """
    if schema is True or schema == {}:
        return {}
    if not isinstance(schema, dict):
        raise ValueError("Path has no declared schema")
    if not path:
        return schema

    def combine(parts, keyword):
        # An unconstrained alternative is genuinely unknown; an unconstrained
        # intersection adds no information. Do not lose a sibling's field type.
        if keyword == "anyOf" and any(part == {} for part in parts):
            return {}
        known = []
        for part in parts:
            if part != {} and part not in known:
                known.append(part)
        return known[0] if len(known) == 1 else {keyword: known} if known else {}

    for family in ("oneOf", "anyOf", "allOf"):
        if family not in schema:
            continue
        base = {key: value for key, value in schema.items() if key != family}
        if family == "allOf":
            return combine([
                path_schema(branch, path, allow_wildcards=allow_wildcards)
                for branch in ([base] if base else []) + schema[family]
            ], "allOf")
        alternatives = []
        for branch in schema[family]:
            try:
                # Constraints alongside oneOf/anyOf also apply to each branch.
                projected = [path_schema(branch, path, allow_wildcards=allow_wildcards)]
                if base:
                    projected.append(path_schema(base, path, allow_wildcards=allow_wildcards))
                alternatives.append(combine(projected, "allOf"))
            except ValueError:
                pass
        if alternatives:
            return combine(alternatives, "anyOf")
        raise ValueError("Output path is not declared: " + repr(path))

    head, *tail = path
    permitted = types(schema)
    permits_object = "object" in permitted or not permitted
    permits_array = "array" in permitted or not permitted
    if isinstance(head, str) and permits_object and head in schema.get("properties", {}):
        return path_schema(schema["properties"][head], tail, allow_wildcards=allow_wildcards)
    if allow_wildcards and head == "*":
        children = []
        if permits_array:
            children.append(schema.get("items", True))
        if permits_object:
            children.append(schema.get("additionalProperties", True)
                            if schema.get("unevaluatedProperties", True) is not False else False)
        alternatives = []
        for child in children:
            try:
                alternatives.append(path_schema(child, tail, allow_wildcards=True))
            except ValueError:
                pass
        if alternatives:
            return combine(alternatives, "anyOf")
    elif isinstance(head, str) and permits_object:
        child = schema.get("additionalProperties", True)
        if schema.get("unevaluatedProperties", True) is False:
            child = False
        if child is True or isinstance(child, dict):
            return path_schema(child, tail, allow_wildcards=allow_wildcards)
    if type(head) is int and head >= 0 and permits_array:
        prefix = schema.get("prefixItems", [])
        child = prefix[head] if head < len(prefix) else schema.get("items", True)
        if isinstance(child, dict) or child is True:
            return path_schema(child, tail, allow_wildcards=allow_wildcards)
    raise ValueError("Output path is not declared: " + repr(path))


def types(schema):
    if "type" in schema:
        value = schema["type"]
        return set(value if isinstance(value, list) else [value])
    for key in ("oneOf", "anyOf"):
        if key in schema:
            return set().union(*(types(s) for s in schema[key]))
    if "allOf" in schema:
        restrictions = [types(branch) for branch in schema["allOf"]]
        restrictions = [value | ({"integer"} if "number" in value else set())
                        for value in restrictions if value]
        return set.intersection(*restrictions) if restrictions else set()
    return set()


def compatible(source, target):
    """Conservative overlap check; not a JSON Schema implication theorem."""
    for key in ("oneOf", "anyOf"):
        if key in source:
            return any(compatible(s, target) for s in source[key])
        if key in target:
            return any(compatible(source, s) for s in target[key])
    a, b = types(source), types(target)
    overlap = a & b or (
        {"integer", "number"} <= a | b
        and bool(a & {"integer", "number"})
        and bool(b & {"integer", "number"})
    )
    if a and b and not overlap:
        return False
    if (
        a == b == {"array"}
        and isinstance(source.get("items"), dict)
        and isinstance(target.get("items"), dict)
    ):
        if not compatible(source["items"], target["items"]):
            return False
    if a == b == {"object"}:
        for key in target.get("required", []):
            if key in source.get("properties", {}):
                if not compatible(
                    source["properties"][key], target.get("properties", {}).get(key, {})
                ):
                    return False
            elif source.get("additionalProperties") is False:
                return False
    if "enum" in source and "enum" in target:
        if not {digest(v) for v in source["enum"]} & {
            digest(v) for v in target["enum"]
        }:
            return False
    return True


def infer(value):
    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, int):
        return {"type": "integer"}
    if isinstance(value, float):
        return {"type": "number"}
    if isinstance(value, str):
        return {"type": "string"}
    if isinstance(value, list):
        return {
            "type": "array",
            "items": {"anyOf": [infer(x) for x in value]} if value else {},
        }
    return {
        "type": "object",
        "properties": {k: infer(v) for k, v in value.items()},
        "required": list(value),
        "additionalProperties": False,
    }


def grounded(evidence, task):
    from .assets import evidence_sources

    return any(evidence in source for source in evidence_sources(task))


def local_schema(schema):
    """Model-provided checks cannot resolve remote schemas or external documents."""
    if isinstance(schema, dict):
        if {"$ref", "$dynamicRef", "$id"} & schema.keys():
            raise ValueError(
                "Output checks must be self-contained schemas without references"
            )
        for value in schema.values():
            local_schema(value)
    elif isinstance(schema, list):
        for value in schema:
            local_schema(value)


def validate_graph(graph, catalog, *, allowed=None):
    errors, pending = [], []
    report = {
        "valid": False,
        "errors": errors,
        "runtime_obligations": pending,
        "data_edges": [],
        "control_edges": [],
        "topological_order": [],
        "scientific_correctness": "requires_review_and_execution",
    }
    errors.extend(contract_errors(graph.plan, PLAN_SCHEMA))
    errors.extend(
        contract_errors(
            {"requirements": graph.requirements, "queries": ["validation"]},
            DECOMPOSITION_SCHEMA,
        )
    )
    if errors:
        return report
    nodes = {n["id"]: n for n in graph.plan["nodes"]}
    if len(nodes) != len(graph.plan["nodes"]):
        errors.append("Duplicate node IDs")
    requirements = {r["id"]: r for r in graph.requirements}
    if len(requirements) != len(graph.requirements):
        errors.append("Duplicate requirement IDs")
    for req in graph.requirements:
        if not grounded(req["evidence"], graph.task):
            errors.append(
                "Requirement evidence is not in the public task: " + req["id"]
            )
    allowed = allowed or tool_allowed
    for nid, node in nodes.items():
        name = node["tool"]
        if name not in catalog.tools or not allowed(name):
            errors.append(nid + ": unknown, retired, alias or excluded tool " + name)
        elif graph.contracts.get(name) != digest(catalog.tools[name]):
            errors.append(nid + ": stale tool contract")
    if errors:
        return report

    def schema_for(binding, current=None):
        kind = binding["kind"]
        if kind == "literal":
            return infer(binding["value"])
        if kind == "task":
            return infer(at(graph.task, binding["path"]))
        if kind == "python_code":
            for name, source in binding["inputs"].items():
                if not name.isidentifier() or keyword.iskeyword(name) or name.startswith("_"):
                    raise ValueError("Invalid numerical-code input name")
                schema_for(source, current)
            return {"type": "string"}
        if kind == "list":
            for evidence in binding.get("provenance", []):
                schema_for(evidence, current)
            return {
                "type": "array",
                "items": (
                    {"anyOf": [schema_for(b, current) for b in binding["items"]]}
                    if binding["items"]
                    else {}
                ),
            }
        if kind == "item":
            if current is None or "for_each" not in current:
                raise ValueError("item binding outside a template")
            iterable = schema_for(current["for_each"])
            if types(iterable) and "array" not in types(iterable):
                raise ValueError("for_each must select a declared array")
            return path_schema(iterable, [0] + binding["path"])
        source = nodes[binding["node"]]
        if kind == "collect" and "for_each" not in source:
            raise ValueError("collect must reference an unexpanded template")
        if kind == "node" and "for_each" in source:
            raise ValueError("Use collect to reference template outputs")
        schema = output_schema(
            catalog.tools[source["tool"]], binding.get("decoded", False)
        )
        result = path_schema(schema, binding["path"])
        return {"type": "array", "items": result} if kind == "collect" else result

    def binding_check(binding, current, target=None):
        schema = schema_for(binding, current)
        if target is not None and not compatible(schema, target):
            raise ValueError("Incompatible source and parameter types")
        if binding["kind"] in {"literal", "task"} and target is not None:
            value = (
                binding["value"]
                if binding["kind"] == "literal"
                else at(graph.task, binding["path"])
            )
            problem = contract_errors(value, target)
            if problem:
                raise ValueError("; ".join(problem))
        for b in bindings(binding):
            if b["kind"] in {"node", "collect"}:
                pending.append(
                    {
                        "node": current["id"],
                        "source": b["node"],
                        "check": "actual_field_presence_and_full_parameter_contract",
                    }
                )
                if b.get("expect"):
                    pending.append(
                        {
                            "node": current["id"],
                            "source": b["node"],
                            "check": "reviewer_confirmed_semantics",
                            "expected": b["expect"],
                        }
                    )
        return schema

    def condition_check(expr, node):
        op = expr["op"]
        if op in {"all", "any"}:
            for e in expr["args"]:
                condition_check(e, node)
        elif op == "not":
            condition_check(expr["arg"], node)
        else:
            a = binding_check(expr["left"], node)
            b = binding_check(expr["right"], node)
            if not grounded(expr["evidence"], graph.task):
                raise ValueError("Condition evidence is not in the public task")
            if op in {"lt", "le", "gt", "ge"} and any(
                types(s) and not types(s) & {"number", "integer"} for s in (a, b)
            ):
                raise ValueError("Ordered scientific comparison requires numbers")
            if op == "in" and types(b) and "array" not in types(b):
                raise ValueError("Membership comparison requires an array")

    deps = {}
    for nid, node in nodes.items():
        data, control = node_dependencies(node)
        deps[nid] = data | control
        report["data_edges"].extend([[source, nid] for source in sorted(data)])
        report["control_edges"].extend([[source, nid] for source in sorted(control)])
        if (data | control) - nodes.keys():
            errors.append(nid + ": dangling node reference")
        spec = catalog.tools[node["tool"]]
        properties = spec["input_schema"].get("properties", {})
        if set(spec["input_schema"].get("required", [])) - node["arguments"].keys():
            errors.append(nid + ": missing required tool arguments")
        if set(node["arguments"]) - properties.keys():
            errors.append(nid + ": unknown tool arguments")
        try:
            if "for_each" in node:
                if node["for_each"]["kind"] not in {"node", "task", "collect", "list"}:
                    raise ValueError("for_each must bind to a task/node array, collected template outputs or a list of bindings")
                iterable = binding_check(node["for_each"], node)
                if types(iterable) and "array" not in types(iterable):
                    raise ValueError("for_each source is not a declared array")
                pending.append(
                    {"node": nid, "check": "actual_array_and_bounded_map_expansion"}
                )
            for key, binding in node["arguments"].items():
                if any(b["kind"] == "python_code" for b in bindings(binding)) and (
                    node["tool"] != "ExecuteNumericalCode" or key != "code"
                    or binding["kind"] != "python_code"
                ):
                    raise ValueError("python_code is only an ExecuteNumericalCode.code binding")
                binding_check(binding, node, properties.get(key, {}))
            for check in node.get("checks", []):
                local_schema(check["schema"])
                Draft202012Validator.check_schema(check["schema"])
                declared = path_schema(
                    output_schema(spec, check.get("decoded", False)), check["path"]
                )
                if not compatible(declared, check["schema"]):
                    raise ValueError("Output check conflicts with the declared output")
            if "when" in node:
                condition_check(node["when"], node)
                pending.append(
                    {
                        "node": nid,
                        "check": "reviewer_approval_of_gate_against_original_task",
                    }
                )
            if node.get("semantics"):
                pending.append(
                    {
                        "node": nid,
                        "check": "planned_semantics_are_not_verified_result_metadata",
                    }
                )
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            errors.append(nid + ": " + str(exc))
        except Exception as exc:
            # jsonschema's schema errors must become actionable feedback too.
            from jsonschema.exceptions import SchemaError

            if not isinstance(exc, SchemaError):
                raise
            errors.append(nid + ": invalid output-check schema")
    try:
        report["topological_order"] = list(TopologicalSorter(deps).static_order())
    except CycleError:
        errors.append("Data and control dependencies jointly contain a cycle")
    delivered = {d["requirement"] for d in graph.plan["deliverables"]}
    if delivered != set(requirements):
        errors.append("Deliverables must cover exactly the declared requirements")
    used = set()
    for delivery in graph.plan["deliverables"]:
        todo = list(delivery["nodes"])
        closure = set()
        while todo:
            nid = todo.pop()
            if nid not in nodes:
                errors.append("Unknown deliverable node: " + nid)
                continue
            if nid not in closure:
                closure.add(nid)
                todo.extend(deps[nid])
        used |= closure
        if requirements.get(delivery["requirement"], {}).get("mode") == "complete":
            if any("when" in nodes[nid] for nid in closure):
                errors.append(
                    "Complete-report requirement depends on a screened branch: "
                    + delivery["requirement"]
                )
    if set(nodes) - used:
        errors.append(
            "Calls unrelated to any declared deliverable: "
            + ", ".join(sorted(set(nodes) - used))
        )
    report["valid"] = not errors
    return report
