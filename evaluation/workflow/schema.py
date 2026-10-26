"""Validate workflow specifications, selectors and declared expression operations."""

import json
import re
from pathlib import Path
from functools import lru_cache
from .values import _number

SCHEMA_VERSION = "workflow.v1"


@lru_cache(maxsize=1)
def _operand_operations():
    """Use the shipped schema as the operation-name registry."""
    schema = json.loads(Path(__file__).with_name("schema.json").read_text())
    return frozenset(
        operation
        for variant in schema["$defs"]["operand"]["oneOf"]
        for operation in variant.get("properties", {})
        .get("operation", {})
        .get("enum", [])
    )


def _selectors(value):
    if isinstance(value, dict):
        if "source" in value:
            yield value
        for key, child in value.items():
            if key not in {"value", "constants"}:
                yield from _selectors(child)
    elif isinstance(value, list):
        for child in value:
            yield from _selectors(child)


def validate_workflow(spec):
    """Fail closed on invalid/empty graphs, undeclared evidence or cyclic dependencies."""
    if spec.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported workflow evaluation schema")
    from .constants import validate as validate_constants

    validate_constants(spec.get("constants", {}))
    nodes, outcomes = spec.get("nodes"), spec.get("outcomes")
    if (
        not isinstance(nodes, list)
        or not nodes
        or not isinstance(outcomes, list)
        or not outcomes
    ):
        raise ValueError(
            "Nonempty nodes and independently checkable outcomes are required"
        )
    ids = [n["id"] for n in nodes]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate capability node")
    parents = {}
    for node in nodes:
        parents[node["id"]] = set(node.get("depends_on", []))
        if not parents[node["id"]] <= set(ids) or node["id"] in parents[node["id"]]:
            raise ValueError("Unknown or self dependency")
        if not _number(node.get("weight", 1)) or node.get("weight", 1) <= 0:
            raise ValueError("Node weights must be positive finite numbers")
        if "observation_reuse_group" in node and (
            not isinstance(node["observation_reuse_group"], str)
            or not 1 <= len(node["observation_reuse_group"]) <= 128
        ):
            raise ValueError(
                "Observation reuse groups must be nonempty strings of at most128characters"
            )
        if not node.get("alternatives"):
            raise ValueError("Each node needs a capability alternative")
        for alt in node["alternatives"]:
            if (
                not alt.get("tools")
                or "DescribeTools" in alt["tools"]
                or not alt.get("output_rules")
            ):
                raise ValueError(
                    "Each alternative needs scientific tools and nonempty output checks"
                )
        bindings = list(node.get("bindings", [])) + [
            b for alt in node["alternatives"] for b in alt.get("bindings", [])
        ]
        for binding in bindings:
            if binding["source_node"] not in parents[node["id"]]:
                raise ValueError("Data bindings require an explicit dependency")
            for field in ("argument", "output"):
                path = binding.get(field)
                if (
                    not isinstance(path, str)
                    or (path != "" and not path.startswith("/"))
                    or re.search(r"~(?:[^01]|$)", path)
                ):
                    raise ValueError("Data bindings require valid JSON pointers")
            if any(
                not _number(binding.get(k, 0)) or binding.get(k, 0) < 0
                for k in ("atol", "rtol")
            ):
                raise ValueError(
                    "Data binding tolerances must be nonnegative finite numbers"
                )
    ready, ordered = set(), []
    while len(ordered) < len(nodes):
        available = [
            n for n in nodes if n["id"] not in ready and parents[n["id"]] <= ready
        ]
        if not available:
            raise ValueError("Capability dependencies contain a cycle")
        for node in available:
            ready.add(node["id"])
            ordered.append(node)
    branches = {b["id"]: b for b in spec.get("branches", [])}
    if len(branches) != len(spec.get("branches", [])):
        raise ValueError("Duplicate branch")
    for branch in branches.values():
        sources = list(_selectors(branch["when"]))
        if not sources or any(
            s["source"] not in {"inputs", "node", "node_arguments"} for s in sources
        ):
            raise ValueError("Branches must derive from public inputs or observed data")
        if any(
            s["source"] in {"node", "node_arguments"} and s["node"] not in ids
            for s in sources
        ):
            raise ValueError("Unknown branch evidence node")
    for node in nodes:
        if node.get("branch") and node["branch"] not in branches:
            raise ValueError("Unknown branch")
        if node.get("branch"):
            sources = list(_selectors(branches[node["branch"]]["when"]))
            if any(
                s["source"] in {"node", "node_arguments"}
                and s["node"] not in parents[node["id"]]
                for s in sources
            ):
                raise ValueError(
                    "Conditional nodes must depend on the observed branch selector"
                )
    if len({o["id"] for o in outcomes}) != len(outcomes):
        raise ValueError("Duplicate outcome")
    groups = {g["id"]: g for g in spec.get("capability_groups", [])}
    if len(groups) != len(spec.get("capability_groups", [])):
        raise ValueError("Duplicate capability group")
    if set(groups) & set(ids):
        raise ValueError("Capability group and node identities must differ")
    for group in groups.values():
        if not group.get("alternatives") or any(
            not route or not set(route) <= set(ids) or len(set(route)) != len(route)
            for route in group["alternatives"]
        ):
            raise ValueError(
                "Capability groups require nonempty routes of known distinct nodes"
            )
        if not _number(group.get("weight", 1)) or group.get("weight", 1) <= 0:
            raise ValueError("Capability group weights must be positive finite numbers")
    for outcome in outcomes:
        if "scientific_domains" in outcome:
            domains = outcome["scientific_domains"]
            answer_paths = [s.get("path", "") for s in _selectors(outcome)
                            if s.get("source") == "answer"]
            if not isinstance(domains, list) or not 1 <= len(domains) <= 1000:
                raise ValueError("Scientific domains require a bounded nonempty list")
            for domain in domains:
                if (not isinstance(domain, dict)
                    or not set(domain) <= {"path", "minimum", "maximum"}
                    or not isinstance(domain.get("path"), str)
                    or not domain["path"].startswith("/")
                    or re.search(r"~(?:[^01]|$)", domain["path"])
                    or not {"minimum", "maximum"}.intersection(domain)
                    or any(not _number(domain[k]) for k in ("minimum", "maximum") if k in domain)
                    or not any(domain["path"] == p or domain["path"].startswith(p + "/") for p in answer_paths)
                    or ("minimum" in domain and "maximum" in domain
                        and domain["minimum"] > domain["maximum"])):
                    raise ValueError("Scientific domains must bound a numeric leaf of this outcome")
        if not (
            outcome.get("evidence_nodes") or outcome.get("evidence_groups")
        ) or not set(outcome.get("evidence_nodes", [])) <= set(ids):
            raise ValueError("Each outcome requires declared actual tool evidence")
        if not set(outcome.get("evidence_groups", [])) <= set(groups):
            raise ValueError("Unknown outcome capability group")
        selectors = list(_selectors(outcome))
        if not any(s["source"] == "answer" for s in selectors):
            raise ValueError("Outcomes must test a submitted answer field")
        if any(s["source"] == "answer" for s in _selectors(outcome.get("right", {}))):
            raise ValueError("Answer fields cannot define their own target")
        if outcome.get("branch") and outcome["branch"] not in branches:
            raise ValueError("Unknown outcome branch")
        if not _number(outcome.get("weight", 1)) or outcome.get("weight", 1) <= 0:
            raise ValueError("Outcome weights must be positive finite numbers")
        if outcome["op"] in {"exists", "type", "finite"}:
            raise ValueError(
                "Scientific outcomes require a substantive comparison, not just shape"
            )
    sources = {
        "inputs",
        "answer",
        "node",
        "node_arguments",
        "call_arguments",
        "call_output",
        "call_error",
    }
    for selector in _selectors(spec):
        if (
            selector["source"] not in sources
            or selector.get("source") in {"node", "node_arguments"}
            and selector.get("node") not in ids
        ):
            raise ValueError("Unknown evidence selector")
        if selector.get("path", "") and not selector["path"].startswith("/"):
            raise ValueError("Selectors require JSON pointers")
    for node in nodes:
        for alt in node["alternatives"]:
            for rule in alt.get("input_rules", []) + alt["output_rules"]:
                for selector in _selectors(rule):
                    if selector["source"] == "answer":
                        raise ValueError(
                            "Capability matches cannot depend on submitted answers"
                        )
                    if (
                        selector["source"] in {"node", "node_arguments"}
                        and selector["node"] not in parents[node["id"]]
                    ):
                        raise ValueError(
                            "Cross-node rules require explicit prerequisites"
                        )
    rules = [
        rule
        for node in nodes
        for alt in node["alternatives"]
        for rule in alt.get("input_rules", []) + alt["output_rules"]
    ]
    rules += outcomes + [b["when"] for b in branches.values()]
    supported_ops = {
        "eq",
        "ne",
        "lt",
        "le",
        "gt",
        "ge",
        "one_of",
        "set_equal",
        "multiset_equal",
        "subset",
        "exists",
        "finite",
        "type",
        "curve_equivalent",
    }
    for rule in rules:
        if rule.get("op") not in supported_ops:
            raise ValueError("Unknown comparison operator")
        if rule["op"] == "type" and (
            not isinstance(rule.get("value"), str)
            or rule["value"]
            not in {"number", "integer", "string", "array", "object", "boolean", "null"}
        ):
            raise ValueError("Type comparisons require a known explicit type")
        if (
            rule["op"] not in {"exists", "finite"}
            and "right" not in rule
            and "value" not in rule
        ):
            raise ValueError("Comparison requires an explicit target")
        for tolerance in ("atol", "rtol", "x_atol", "x_rtol"):
            if not _number(rule.get(tolerance, 0)) or rule.get(tolerance, 0) < 0:
                raise ValueError("Tolerances must be nonnegative finite numbers")
    fixed_arity = {
        "reviewed_program_identity": 1,
        "literal_constant": 1,
        "object_member_or_null": 2,
        "record_values_by_path": 4,
        "select_if_text_equal": 4,
        "molecular_formula_counts": 1,
        "ordered_integer_intersection": 2,
        "inchi_identifier": 1,
        "source_file_labels": 3,
        "public_asset_paths": 3,
        "coalesce_number": 2,
        "abs": 1,
        "natural_log": 1,
        "exponential": 1,
        "add": 2,
        "subtract": 2,
        "multiply": 2,
        "divide": 2,
        "average_ranks": 1,
        "integer_translation_span": 1,
        "argmin": 1,
        "argmax": 1,
        "record_value": 4,
        "json_value": 2,
        "common_interval": 2,
        "curve_spec": 4,
        "record_field_presence": 2,
        "zero_pad_numeric_matrix": 3,
        "normalize_protein_strings": 1,
        "count_occurrences": 2,
        "interval_union": 2,
        "join": 2,
        "text_between": 3,
        "numeric_matrix": 1,
        "closed_numeric_expression": 1,
        "records_matching": 2,
        "complete_record_rows": 1,
        "value_at_pointer": 2,
        "named_numeric_port": 2,
        "records_nonnull": 2,
        "matrix_axis_profile": 1,
        "records_columns": 2,
        "column": 2,
        "column_affine": 3,
        "paired_rows": 2,
        "partition_profile": 2,
        "slice": 3,
        "numeric_value_for_row": 3,
        "linear_projection_values": 5,
        "coordinate_set_for_id": 3,
        "matrix_value_by_ids": 4,
        "python_literal_value": 2,
        "python_literal_assignments": 1,
        "sum": 1,
        "mean": 1,
        "min": 1,
        "max": 1,
        "length": 1,
    }

    def check_expressions(value):
        if isinstance(value, list):
            for child in value:
                check_expressions(child)
        elif isinstance(value, dict):
            name = value.get("operation")
            if "operation" in value and (
                not isinstance(name, str) or name not in _operand_operations()
            ):
                raise ValueError("Unknown operand operation: " + str(name))
            if name in fixed_arity and (
                not isinstance(value.get("args"), list)
                or len(value["args"]) != fixed_arity[name]
            ):
                raise ValueError("Invalid operand argument count: " + name)
            if name == "literal_constant":
                from .constants import resolve

                resolve(value, spec.get("constants", {}))
            if name in {"array", "scalar_array", "numeric_rows"} and (
                not isinstance(value.get("args"), list)
                or not 1 <= len(value["args"]) <= 10000
            ):
                raise ValueError("Invalid operand argument count: " + name)
            for key, child in value.items():
                if key not in {
                    "value",
                    "constants",
                }:  # Literal data is not expression syntax.
                    check_expressions(child)
            if name in {"array", "scalar_array"}:
                # These constructors take scalars. A nested vector/matrix is
                # guaranteed to fail at runtime; authors must use numeric_rows
                # for numeric matrices. Do not infer the type of an observed
                # selector or dynamically decoded JSON from its field name.
                container_results = {
                    "array",
                    "scalar_array",
                    "numeric_rows",
                    "column",
                    "slice",
                    "average_ranks",
                    "integer_translation_span",
                    "numeric_matrix",
                    "records_columns",
                    "records_matching",
                    "records_nonnull",
                    "paired_rows",
                    "partition_profile",
                    "coordinate_set_for_id",
                    "python_literal_assignments",
                    "common_interval",
                    "interval_union",
                    "curve_spec",
                    "zero_pad_numeric_matrix",
                    "column_affine",
                    "argmin",
                    "argmax",
                    "normalize_protein_strings",
                    "matrix_axis_profile",
                    "linear_projection_values",
                }
                for child in value["args"]:
                    if not isinstance(child, dict):
                        continue  # Normal operand validation handles syntax.
                    if child.get("operation") in container_results:
                        raise ValueError("Scalar operand required by " + name)
                    if "value" in child:
                        scalar = child["value"]
                        valid = (
                            _number(scalar)
                            if name == "array"
                            else (
                                scalar is None
                                or type(scalar) in (str, bool)
                                or _number(scalar)
                            )
                        )
                        if not valid:
                            raise ValueError("Scalar operand required by " + name)

    check_expressions(rules)
    policy = spec.get("efficiency", {})
    for key in ("free_recovery_calls", "free_disambiguation_calls"):
        if type(policy.get(key, 0)) is not int or policy.get(key, 0) < 0:
            raise ValueError("Efficiency allowances must be nonnegative integers")
    return ordered
