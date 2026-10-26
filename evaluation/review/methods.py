"""Quarantine unrecognized proofs without automatically approving their science."""

from evaluation.workflow.constants import resolve


def unresolved_or_correct_answer(raw):
    """Missing a recognized target observation is not evidence of a wrong value."""
    if raw.get("answer_only_credit") == 1:
        return True
    outcomes = raw.get("outcomes", [])
    return bool(outcomes) and not any(
        o.get("required", True)
        and o.get("applicable") is True
        and o.get("correct") is False
        and not o.get("reason")
        for o in outcomes
    )


def exact_programs(reference):
    spec = reference["evaluation"]
    known = set()
    for node in spec["nodes"]:
        for alt in node["alternatives"]:
            if "ExecuteNumericalCode" not in alt["tools"]:
                continue
            for rule in alt.get("input_rules", []):
                left = rule.get("left", {})
                right = rule.get("right", {})
                if left.get("operation") == "reviewed_program_identity":
                    left = left.get("args", [{}])[0]
                    if right.get("operation") == "reviewed_program_identity":
                        right = right.get("args", [{}])[0]
                if (
                    rule.get("op") in {"eq", "one_of"}
                    and left.get("source") == "call_arguments"
                    and left.get("path") == "/code"
                ):
                    try:
                        code = resolve(right, spec.get("constants", {}))
                    except ValueError:
                        continue
                    if isinstance(code, str):
                        known.add(code)
                    elif rule["op"] == "one_of" and isinstance(code, list):
                        known.update(c for c in code if isinstance(c, str))
    return known


def classify(reference, prediction, raw, contracts):
    """Triage only after the outer runner authenticates the complete trajectory.

    Unknown calculations remain unresolved. This does not prove that their
    algorithms are correct, authorize generated code, or authenticate a trace.
    """
    if (
        raw["joint_pass"]
        or raw.get("pending_review")
        or not raw["runtime_pass"]
        or not unresolved_or_correct_answer(raw)
    ):
        return None
    computational = {
        n
        for n, s in contracts.items()
        if s.get("domain", s.get("category")) == "MachineLearning"
    }
    computational.add("ExecuteNumericalCode")
    nodes = {n["id"]: n for n in reference["evaluation"]["nodes"]}
    for state in raw["nodes"]:
        tools = {t for a in nodes[state["id"]]["alternatives"] for t in a["tools"]}
        if (
            state["required"]
            and not state["matched"]
            and not tools.intersection(computational)
        ):
            return None
    matched = {n["observation_id"] for n in raw["nodes"] if n["matched"]}
    known = exact_programs(reference)
    unknown = []
    for call in prediction.get("calls", []):
        if call.get("status") != "success":
            continue
        name = call["tool"]
        output = call.get("output")
        code = call.get("arguments", {}).get("code")
        if name == "ExecuteNumericalCode":
            if (
                isinstance(code, str)
                and code not in known
                and isinstance(output, dict)
                and output.get("code") == code
                and output.get("status") == "success"
                and output.get("execution_status") == "completed"
                and output.get("exit_code") == 0
                and output.get("stdout_truncated") is False
                and output.get("stderr_truncated") is False
            ):
                unknown.append(call["observation_id"])
        elif name in computational and call["observation_id"] not in matched:
            from tools.runtime.contracts import contract_errors

            if not contract_errors(
                call.get("arguments", {}), contracts[name]["input_schema"]
            ) and not contract_errors(output, contracts[name]["output_schema"]):
                unknown.append(call["observation_id"])
    if not unknown:
        return None
    return {
        "kind": "unrecognized_computational_proof",
        "observations": unknown,
        "reason": "Correct final values and recognized required sources, but an unrecognized successful computation. Independently inspect the complete authentic method and update shared criteria; correct stdout or answer-only printing never establishes scientific validity.",
    }
