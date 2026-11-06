"""Match actual tool observations and capability dependencies without editing evidence."""

import json
import math
from .values import MissingEvidence, pointer, _equal
from .expressions import predicate


def _rule_set(rules, value, context):
    try:
        return all(
            predicate(rule, context, pointer(value, rule.get("path", "")))
            for rule in rules
        )
    except (MissingEvidence, TypeError, OverflowError):
        return False


def _branch(identifier, spec, context):
    if identifier is None:
        return True
    branch = next(b for b in spec.get("branches", []) if b["id"] == identifier)
    try:
        return predicate(branch["when"], context)
    except MissingEvidence:
        return None


def _matches(node, call, context):
    arguments = call.get("_effective_arguments", call.get("arguments"))
    for alt in node["alternatives"]:
        if call["tool"] not in alt["tools"] or call.get("status") not in alt.get(
            "statuses", ["success"]
        ):
            continue
        local = dict(
            context,
            call_arguments=arguments,
            call_output=call.get("output"),
            call_error=call.get("error"),
        )
        if not _rule_set(alt.get("input_rules", []), arguments, local):
            continue
        if not _rule_set(alt["output_rules"], call.get("output"), local):
            continue
        try:
            if all(
                _equal(
                    pointer(arguments, b["argument"]),
                    pointer(
                        context["nodes"][b["source_node"]].get("output"), b["output"]
                    ),
                    b.get("atol", 0),
                    b.get("rtol", 0),
                )
                for b in node.get("bindings", []) + alt.get("bindings", [])
            ):
                return True
        except (MissingEvidence, KeyError):
            continue
    return False


def _answer(value):
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("```json") and text.endswith("```"):
            text = text[7:-3].strip()
        try:
            return json.loads(text)
        except ValueError:
            return None
    return value


def _group_satisfied(group, matched):
    """A route is an AND of executed nodes; route alternatives form an OR."""
    return any(
        all(node in matched for node in route) for route in group["alternatives"]
    )


def _grounded(outcome, matched, groups):
    return all(node in matched for node in outcome.get("evidence_nodes", [])) and all(
        _group_satisfied(groups[identifier], matched)
        for identifier in outcome.get("evidence_groups", [])
    )


def _execution_signature(call):
    """Identify an actual repeated result without merging changed observations.

    The same query may legitimately return new data or recover from a failure.
    Identical tool, arguments and scientific feedback carry no extra information
    merely because overlapping capability routes can match another observation ID.
    """
    feedback = {
        key: call.get(key)
        for key in ("tool", "arguments", "status", "output", "error_type", "error")
    }
    # The engine supplies this view only from trusted tool contracts and drops
    # any caller-provided internal field first. Spelling out a default does not
    # turn the same operation into new scientific work; explicit null is kept.
    feedback["arguments"] = call.get("_effective_arguments", call.get("arguments"))
    output = feedback["output"]
    if call.get("tool") == "ExecuteNumericalCode" and isinstance(output, dict):
        from .program_identity import reviewed_program_identity
        def code_identity(value):
            try:
                return {"reviewed_python_ast_sha256":reviewed_program_identity(value)}
            except MissingEvidence:
                return value
        arguments=feedback["arguments"]
        if isinstance(arguments,dict)and isinstance(arguments.get("code"),str):
            feedback["arguments"]={**arguments,"code":code_identity(arguments["code"])}
        output=dict(output)
        if isinstance(output.get("code"),str):
            output["code"]=code_identity(output["code"])
        feedback["output"]=output
        # A fresh restricted worker creates a UUID output directory even for
        # identical deterministic calculations. Its location is not new science.
        # Preserve every other feedback field, and only relativize plots actually
        # inside that worker directory. Never mutate authenticated observations.
        directory = output.get("artifact_directory")
        if isinstance(directory, str) and directory:
            output = dict(output)
            output.pop("artifact_directory")
            plots = output.get("plots")
            if isinstance(plots, list):
                prefix = directory.rstrip("/") + "/"
                output["plots"] = [
                    (
                        plot[len(prefix) :]
                        if isinstance(plot, str) and plot.startswith(prefix)
                        else plot
                    )
                    for plot in plots
                ]
            feedback["output"] = output
    def numeric_identity(value):
        # JSON numbers 1 and 1.0 denote the same numeric parameter/receipt.
        # Booleans, strings and genuinely different numeric values stay distinct.
        if type(value) is float and math.isfinite(value) and value.is_integer():
            return int(value)
        if isinstance(value, list):
            return [numeric_identity(item) for item in value]
        if isinstance(value, dict):
            return {key:numeric_identity(item) for key,item in value.items()}
        return value

    return json.dumps(
        numeric_identity(feedback),
        sort_keys=True,
        ensure_ascii=False,
    )
