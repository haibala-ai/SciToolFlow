"""Aggregate completion, planning, answer and joint metrics; keep pending review explicit."""

import copy, hashlib, json
from pathlib import Path
from .answer import score_answer, field_paths
from .planning import score_plan, budget_for, reference_events


def defaulted(value, pending):
    """Map an unresolved judgement to the stated default while keeping the flag."""
    if value is None:
        return (False, True) if pending else (False, False)
    return value, False


def evaluate_v2(
    references,
    predictions,
    output,
    *,
    registry,
    trace_root,
    normalize_value=None,
    semantic=None,
    strict_only=False
):
    """Score every reference; always return defined metrics plus pending-review flags.

    ``strict_only`` reproduces the v0.1 behaviour (unresolved becomes ``None`` and the
    aggregate becomes ``null``) and is kept only for comparison with earlier runs.
    ``semantic`` may be a callable ``(request) -> bool | None`` that resolves a pending
    judgement without an external API (for example the local Qwen judge).
    """
    from pathlib import Path

    normalize_value = normalize_value or (lambda value: value)
    aliases = registry.get("aliases", {})
    optional_args = {
        name: {
            item["name"]: item.get("default_value", item.get("default"))
            for item in (spec.get("parameters") or [])
            if not item.get("required")
        }
        for name, spec in (registry.get("tools") or {}).items()
    }
    refs = copy.deepcopy(list(references))
    indexed = {}
    for row in predictions:
        if row["id"] in indexed:
            raise ValueError("Duplicate prediction IDs")
        indexed[row["id"]] = row
    unknown = set(indexed) - {r["id"] for r in refs}
    if unknown:
        raise ValueError("Unknown prediction IDs: " + ", ".join(sorted(unknown)))

    results, review_requests = [], []
    for reference in refs:
        if any(
            aliases.get(t, t) == "DescribeTools" for t in reference.get("tool_path", [])
        ):
            raise ValueError("DescribeTools cannot occur in a reference tool_path")
        identifier = reference["id"]
        trace = reference_events(reference, trace_root)
        reference = normalize_value(reference)
        reference["_resolved_events"] = normalize_value(trace)
        prediction = normalize_value(copy.deepcopy(indexed.get(identifier)))
        row = {
            "id": identifier,
            "budget_calls": budget_for(reference),
            "reference_calls": len(reference.get("tool_path", [])),
        }
        if reference.get("evaluation_status") == "quarantined":
            row.update(
                supplied=prediction is not None,
                eligible=False,
                completed=False,
                completion_pass=False,
                planning_pass=False,
                answer_pass=False,
                joint_pass=False,
                planning_pending=False,
                answer_pending=False,
                reason="quarantined_reference",
                reference_issue=reference.get("reference_issue"),
            )
            results.append(row)
            continue
        if prediction is None:
            row.update(
                supplied=False,
                completed=False,
                completion_pass=False,
                planning_pass=False,
                answer_pass=False,
                joint_pass=False,
                reason="missing_prediction",
                planning_pending=False,
                answer_pending=False,
                answer_fields_matched=0,
                answer_fields_total=len(field_paths(reference)),
            )
            results.append(row)
            continue
        calls = prediction.get("calls") or []
        if not isinstance(calls, list) or any(not isinstance(c, dict) for c in calls):
            raise ValueError("calls must be a list of tool call objects")
        scientific_calls = [
            c
            for c in calls
            if c.get("tool") and aliases.get(c["tool"], c["tool"]) != "DescribeTools"
        ]
        discovery_calls = [
            c
            for c in calls
            if aliases.get(c.get("tool"), c.get("tool")) == "DescribeTools"
        ]
        charged_calls = len(scientific_calls)
        budget_exceeded = charged_calls > budget_for(reference)
        plan = score_plan(reference, scientific_calls, aliases, optional_args)
        answer_text = prediction.get("final_answer", prediction.get("answer"))
        if isinstance(answer_text, dict):
            from scitoolflow.protocol import expand_citations

            observations = {
                c["observation_id"]: c
                for c in calls
                if isinstance(c, dict) and c.get("observation_id")
            }
            try:
                answer_text = expand_citations(answer_text, observations)
            except (ValueError, KeyError, TypeError):
                answer_text = None
        from .evidence import condition_reference

        reference, conditioning = condition_reference(reference, calls, answer_text)
        answer = score_answer(reference, answer_text)
        if conditioning:
            row["evidence_conditioning"] = conditioning
            if conditioning["status"] == "missing_actual_evidence":
                answer["status"] = "failed"
                answer.setdefault("contract_errors", []).append(conditioning["error"])
        from .source_drift import selector_drift

        drift = selector_drift(reference, scientific_calls, trace_root, aliases)
        if (
            drift
            and not answer.get("contract_errors")
            and not (
                conditioning and conditioning["status"] == "missing_actual_evidence"
            )
        ):
            row["source_drift"] = drift
            # An outdated selector gold is neither a model error nor proof that
            # the new answer is correct. Full current evidence needs independent review.
            answer["status"] = "needs_review"
        completed = prediction.get("completed")
        if completed is not None and type(completed) is not bool:
            raise ValueError("completed must be a boolean")
        has_answer = answer_text is not None and (
            not isinstance(answer_text, (str, list, dict)) or bool(answer_text)
        )
        if isinstance(answer_text, str):
            has_answer = bool(answer_text.strip())
        failed = (
            bool(prediction.get("failure_reason"))
            or prediction.get("status")
            in {"quarantined", "error", "blocked", "failed", "timeout"}
            or prediction.get("budget_exceeded") is True
            or budget_exceeded
        )
        completion = (
            bool(completed if completed is not None else has_answer)
            and has_answer
            and not failed
        )

        planning_pending = (not plan["dataflow_pass"]) and plan["successful_calls"] > 0
        answer_pending = answer["status"] == "needs_review"
        planning_strict = (
            True
            if plan["dataflow_pass"]
            else (None if plan["successful_calls"] else False)
        )
        answer_strict = (
            True
            if answer["status"] == "passed"
            else (None if answer_pending else False)
        )
        if strict_only:
            planning_value, planning_flag = planning_strict, planning_pending
            answer_value, answer_flag = answer_strict, answer_pending
        else:
            planning_value, planning_flag = defaulted(planning_strict, planning_pending)
            answer_value, answer_flag = defaulted(answer_strict, answer_pending)
        if not completion:
            planning_value = answer_value = False
            planning_flag = answer_flag = False
        request = None
        if planning_flag or answer_flag:
            request = {
                "id": identifier,
                "planning_pass": planning_strict,
                "answer_pass": answer_strict,
                "question": reference["question"] if "question" in reference else "",
                "inputs": reference.get("inputs", {}),
                "reference_answer": reference.get("expected_answer"),
                "predicted_answer": answer_text,
                "actual_calls": calls,
                "reference_calls": reference["_resolved_events"],
                "dependency_graph": reference.get("dependency_graph", {}),
                "reference_sha256": hashlib.sha256(
                    json.dumps(reference, sort_keys=True, ensure_ascii=False).encode()
                ).hexdigest(),
                "prediction_sha256": hashlib.sha256(
                    json.dumps(prediction, sort_keys=True, ensure_ascii=False).encode()
                ).hexdigest(),
                "predicted_path": [
                    aliases.get(c.get("tool"), c.get("tool"))
                    for c in scientific_calls
                    if isinstance(c, dict)
                ],
                "answer_excerpt": (
                    (
                        answer_text
                        if isinstance(answer_text, str)
                        else json.dumps(answer_text, ensure_ascii=False)
                    )[:6000]
                    if answer_text is not None
                    else ""
                ),
                "field_outcomes": [
                    f for f in answer["fields"] if f["outcome"] != "match"
                ][:40],
                "step_recall": plan["step_recall"],
                "tool_occurrence_recall": plan["tool_occurrence_recall"],
                "reason": "Alternative path or wording; English string/schema inequality is not an automatic failure.",
            }
            if drift and answer["status"] == "needs_review":
                request["source_drift"] = drift
                request["requires_independent_review"] = True
                request["reason"] = (
                    "Same selector and exact input returned a changed ordered object set. Recheck the current science against actual observations; do not accept an answer merely because data changed."
                )
        if semantic and request:
            verdict = semantic(request)
            if isinstance(verdict, dict):
                if isinstance(verdict.get("planning_pass"), bool) and planning_flag:
                    planning_value, planning_flag = verdict["planning_pass"], False
                if isinstance(verdict.get("answer_pass"), bool) and answer_flag:
                    answer_value, answer_flag = verdict["answer_pass"], False
                request = {**request, "semantic_verdict": verdict}
        if request:
            review_requests.append(request)
        row.update(
            supplied=True,
            answer_representation_normalizations=answer.get(
                "representation_normalizations", []
            ),
            completed=completion,
            charged_calls=charged_calls,
            budget_exceeded=budget_exceeded,
            scientific_calls=charged_calls,
            discovery_calls=len(discovery_calls),
            completion_origin=(
                "explicit_completed_flag"
                if completed is not None
                else "legacy_inferred"
            ),
            completion_pass=completion,
            planning_pass=planning_value,
            planning_strict=planning_strict if completion else False,
            reference_path_match=plan["dataflow_pass"],
            planning_pending=planning_flag,
            answer_pass=answer_value,
            answer_strict=answer_strict if completion else False,
            answer_pending=answer_flag,
            joint_pass=bool(completion and planning_value and answer_value),
            joint_strict=(
                False
                if not completion
                else (
                    None
                    if (planning_strict is None or answer_strict is None)
                    else bool(completion and planning_strict and answer_strict)
                )
            ),
            answer_status=(
                "passed_by_review"
                if answer["status"] == "needs_review" and answer_value is True
                else (
                    "failed_by_review"
                    if completion
                    and answer["status"] == "needs_review"
                    and answer_value is False
                    and not answer_flag
                    else answer["status"]
                )
            ),
            answer_status_strict=answer["status"],
            answer_fields_matched=answer["matched"],
            answer_fields_total=answer["total"],
            answer_leaves_matched=answer.get("leaves_matched", 0),
            answer_leaves_total=answer.get("leaves_total", 0),
            step_recall=round(plan["step_recall"], 6),
            tool_occurrence_recall=round(plan["tool_occurrence_recall"], 6),
            extra_calls=plan["extra_calls"],
            successful_calls=plan["successful_calls"],
        )
        results.append(row)

    total = len(results)
    eligible = [r for r in results if r.get("eligible", True)]
    supplied = [r for r in eligible if r["supplied"]]
    summary = {
        "total_reference_tasks": total,
        "eligible_reference_tasks": sum(r.get("eligible", True) for r in results),
        "quarantined_reference_tasks": sum(
            not r.get("eligible", True) for r in results
        ),
        "supplied_predictions": sum(1 for r in results if r["supplied"]),
        "missing_predictions": sum(1 for r in results if not r["supplied"]),
        "pass_rate": _rate(results, "completion_pass"),
        "pass_rate_definition": "Runtime completion with a nonempty result and no reported failure or budget overrun.",
        "tool_planning_accuracy": _rate(results, "planning_pass"),
        "tool_planning_accuracy_strict": _rate(results, "planning_strict"),
        "reference_path_match_rate": _rate(results, "reference_path_match"),
        "final_answer_accuracy": _rate(results, "answer_pass"),
        "final_answer_accuracy_strict": _rate(results, "answer_strict"),
        "joint_pass_rate": _rate(results, "joint_pass"),
        "joint_pass_rate_strict": _rate(results, "joint_strict"),
        "mean_answer_field_credit_supplied": round(
            sum(r.get("answer_fields_matched", 0) for r in supplied)
            / max(1, sum(r.get("answer_fields_total", 0) for r in supplied)),
            6,
        ),
        "mean_answer_leaf_credit_supplied": round(
            sum(r.get("answer_leaves_matched", 0) for r in supplied)
            / max(1, sum(r.get("answer_leaves_total", 0) for r in supplied)),
            6,
        ),
        "mean_step_recall_supplied": round(
            sum(r.get("step_recall", 0.0) for r in supplied) / max(1, len(supplied)), 6
        ),
        "mean_tool_occurrence_recall_supplied": round(
            sum(r.get("tool_occurrence_recall", 0.0) for r in supplied)
            / max(1, len(supplied)),
            6,
        ),
        "pending_semantic_review": sum(
            bool(r.get("planning_pending") or r.get("answer_pending")) for r in results
        ),
        "pending_planning_reviews": sum(
            bool(r.get("planning_pending")) for r in results
        ),
        "pending_answer_reviews": sum(bool(r.get("answer_pending")) for r in results),
        "joint_accuracy_lower_bound": _rate(results, "joint_pass"),
        "joint_accuracy_upper_bound": (
            round(
                sum(
                    bool(
                        r["completed"]
                        and (r.get("planning_pass") or r.get("planning_pending"))
                        and (r.get("answer_pass") or r.get("answer_pending"))
                    )
                    for r in eligible
                )
                / len(eligible),
                6,
            )
            if eligible
            else None
        ),
        "scoring_mode": (
            "strict_only" if strict_only else "default_incorrect_with_review_flag"
        ),
        "unresolved_default": "An unresolved field/path counts as incorrect and is reported for review; it is never dropped from the denominator.",
        "semantic_review_used": bool(semantic)
        and any("semantic_verdict" in r for r in review_requests),
        "llm_judge_used": any(
            r.get("semantic_verdict", {}).get("reviewer_kind") == "llm"
            for r in review_requests
        ),
        "formal_benchmark_accuracy": False,
    }
    Path(output).write_text(
        json.dumps(
            {"summary": summary, "results": results}, ensure_ascii=False, indent=2
        )
        + "\n"
    )
    Path(output).with_name(Path(output).stem + "_review_requests.json").write_text(
        json.dumps(
            {"tasks": review_requests, "separate_api_calls": 0},
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    return {"summary": summary, "results": results}


def _rate(results, field):
    values = [r.get(field) for r in results if r.get("eligible", True)]
    if not values:
        return None
    return sum(1 for v in values if v) / len(values)
