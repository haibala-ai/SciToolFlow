"""Static workflow selectors checked against current closed tool contracts.

This check does not approve scientific shapes, units or values. It is promoted
from the immutable fine-review helper so current tests and migration audits do
not depend on a moved historical directory.
"""

from .schema import _selectors, validate_workflow


def invalid_argument_roots(h, catalog):
    findings = []
    for node in h["evaluation"]["nodes"]:
        for index, alternative in enumerate(node["alternatives"]):
            paths = {
                v["argument"]
                for v in node.get("bindings", []) + alternative.get("bindings", [])
            }
            for rule in alternative.get("input_rules", []):
                if rule.get("path"):
                    paths.add(rule["path"])
                paths.update(
                    v.get("path", "")
                    for v in _selectors(rule)
                    if v["source"] == "call_arguments"
                )
            for rule in alternative.get("output_rules", []):
                paths.update(
                    v.get("path", "")
                    for v in _selectors(rule)
                    if v["source"] == "call_arguments"
                )
            for name in alternative["tools"]:
                schema = catalog[name].get("input_schema", {})
                if schema.get("additionalProperties") is not False:
                    continue
                properties = schema.get("properties", {})
                for path in sorted(paths):
                    root = (
                        path[1:].split("/")[0].replace("~1", "/").replace("~0", "~")
                        if path
                        else None
                    )
                    if path and root not in properties:
                        findings.append(
                            {
                                "task_id": h["id"],
                                "node": node["id"],
                                "alternative": index,
                                "tool": name,
                                "invalid_path": path,
                                "declared_arguments": list(properties),
                            }
                        )
    return findings


def invalid_output_roots(h, catalog):
    findings = []
    for node in h["evaluation"]["nodes"]:
        for index, alternative in enumerate(node["alternatives"]):
            paths = {
                rule["path"]
                for rule in alternative.get("output_rules", [])
                if rule.get("path")
            }
            for rule in alternative.get("input_rules", []) + alternative.get(
                "output_rules", []
            ):
                paths.update(
                    v.get("path", "")
                    for v in _selectors(rule)
                    if v["source"] == "call_output"
                )
            for name in alternative["tools"]:
                schema = catalog[name].get("output_schema", {})
                if (
                    schema.get("type") != "object"
                    or schema.get("additionalProperties") is not False
                ):
                    continue
                properties = schema.get("properties", {})
                for path in sorted(paths):
                    root = (
                        path[1:].split("/")[0].replace("~1", "/").replace("~0", "~")
                        if path
                        else None
                    )
                    if path and root not in properties:
                        findings.append(
                            {
                                "task_id": h["id"],
                                "node": node["id"],
                                "alternative": index,
                                "tool": name,
                                "invalid_path": path,
                                "declared_fields": list(properties),
                            }
                        )
    return findings


def public_answer_contract(reference):
    """Expose only format/comparison semantics; never hidden targets or tool routes.

    Task authors still publish a concise answer schema themselves. This helper is a
    supplement, not a schema inferred from gold values or an answer-solving hint.
    """
    spec = reference["evaluation"]
    validate_workflow(spec)
    result = []
    for outcome in spec["outcomes"]:
        paths = [
            s.get("path", "") for s in _selectors(outcome) if s["source"] == "answer"
        ]
        result.append(
            {
                "fields": paths,
                "comparison": outcome["op"],
                "atol": outcome.get("atol", 0),
                "rtol": outcome.get("rtol", 0),
                "case_insensitive": outcome.get("casefold", False),
                "required": outcome.get("required", True),
                "conditional": bool(outcome.get("branch")),
            }
        )
        if outcome.get("scientific_domains"):
            import copy
            result[-1]["scientific_domains"] = copy.deepcopy(outcome["scientific_domains"])
    return result
