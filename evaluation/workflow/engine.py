"""Score grounded workflow capabilities and aggregate benchmark metrics."""

from .values import MissingEvidence
from .schema import SCHEMA_VERSION, validate_workflow, _selectors
from .expressions import predicate
from .matching import (
    _rule_set,
    _branch,
    _matches,
    _answer,
    _group_satisfied,
    _grounded,
    _execution_signature,
)


def score_workflow(
    reference, prediction, *, aliases=None, search_limit=100000, tool_contracts=None
):
    """Grade capability DAGs and grounded outcomes without matching a golden route.

    Actual call observations must come from the trusted run, not from answer claims.
    Ambiguous route search is exact within ``search_limit``; exhaustion is reported
    as unresolved and can never produce a failing benchmark verdict by default.
    """
    spec = reference["evaluation"]
    ordered = validate_workflow(spec)
    groups = {group["id"]: group for group in spec.get("capability_groups", [])}
    branch_rules = {branch["id"]: branch["when"] for branch in spec.get("branches", [])}
    aliases = aliases or {}
    prediction = prediction or {}
    calls, discovery = [], 0
    seen_ids = set()
    for index, original in enumerate(prediction.get("calls") or []):
        call = dict(original)
        call.pop("_effective_arguments", None)
        call["tool"] = aliases.get(call.get("tool"), call.get("tool"))
        if call["tool"] == "DescribeTools":
            discovery += 1
            continue
        observation_id = call.get("observation_id")
        if not observation_id or observation_id in seen_ids:
            raise ValueError(
                "Unique harness observation_id is required for every scientific call"
            )
        seen_ids.add(observation_id)
        call["_index"] = index
        # Effective arguments are a grading-only view. Raw evidence remains
        # byte/identity-bound in the outer runner, and explicit null stays null.
        raw_arguments = call.get("arguments")
        if isinstance(raw_arguments, dict) and tool_contracts is not None:
            parameters = tool_contracts.get(call["tool"], {}).get("parameters", [])
            defaults = {
                p["name"]: p.get("default_value", p.get("default"))
                for p in parameters
                if not p.get("required") and ("default_value" in p or "default" in p)
            }
            call["_effective_arguments"] = {**defaults, **raw_arguments}
        calls.append(call)
    answer = _answer(prediction.get("final_answer", prediction.get("answer")))
    context = {
        "inputs": reference.get("inputs", {}),
        "answer": answer,
        "nodes": {},
        "constants": spec.get("constants", {}),
        "_json_sizes": {},
    }
    best, visits, truncated = {}, 0, False
    best_score = (-1, -1, -1, -1)
    full_weight = sum(n.get("weight", 1) for n in ordered)
    full_science = sum(o.get("weight", 1) for o in spec["outcomes"])
    # Match results depend only on this call and its explicitly declared parent
    # observations. Reuse them across assignments of unrelated optional nodes.
    candidates = {
        node["id"]: [
            call
            for call in calls
            if any(
                call["tool"] in alt["tools"]
                and call.get("status") in alt.get("statuses", ["success"])
                for alt in node["alternatives"]
            )
        ]
        for node in ordered
    }
    # Ordering parents need not supply any values to a match predicate. Keep
    # their chronology constraints, but do not treat them as unknown data when
    # filtering a literal program or source identity. Otherwise repeated parent
    # observations make impossible optional methods look possible and force an
    # exponential search just to prove that their literal programs differ.
    match_parents = {}
    for node in ordered:
        referenced = {
            selector["node"]
            for selector in _selectors(node.get("alternatives", []))
            if selector.get("source") in {"node", "node_arguments"}
        }
        for item in [node, *node["alternatives"]]:
            referenced.update(b["source_node"] for b in item.get("bindings", []))
        match_parents[node["id"]] = sorted(referenced)
    match_cache = {}

    def matches(node, call, matched):
        key = (
            node["id"],
            call["_index"],
            tuple(matched[p]["_index"] for p in match_parents[node["id"]]),
        )
        if key not in match_cache:
            match_cache[key] = _matches(node, call, dict(context, nodes=matched))
        return match_cache[key]

    def observation_available(node, call, matched, used):
        if call["_index"] not in used:
            return True
        group = node.get("observation_reuse_group")
        return bool(group) and all(
            other.get("observation_reuse_group") == group
            for other in ordered
            if other["id"] in matched
            and matched[other["id"]]["_index"] == call["_index"]
        )

    def optimistic_quality(position, matched, used):
        """An upper bound only: never infer science or grant missing evidence."""
        possible = set(matched)
        possible_calls = {key: [call] for key, call in matched.items()}
        future_weights, future_calls = [], set()
        reusable_future = False
        local = dict(context, nodes=matched)
        for node in ordered[position:]:
            parents = node.get("depends_on", [])
            if not all(p in possible for p in parents):
                continue
            if _branch(node.get("branch"), spec, local) is False:
                continue
            available = [
                c
                for c in candidates[node["id"]]
                if observation_available(node, c, matched, used)
            ]
            # Propagate possible observation identities forward. Singleton
            # parents already determine the actual arguments/outputs a future
            # node could receive,even before the search commits to that route.
            # Ambiguous parents stay optimistic; no guessed observation enters
            # the final witness or earns evidence credit here.
            minimum = max(
                (min(c["_index"] for c in possible_calls[p]) for p in parents),
                default=-1,
            )
            available = [c for c in available if c["_index"] > minimum]
            data_parents = match_parents[node["id"]]
            if all(len(possible_calls[p]) == 1 for p in data_parents):
                determined = {
                    **matched,
                    **{p: possible_calls[p][0] for p in data_parents},
                }
                available = [c for c in available if matches(node, c, determined)]
            if available:
                possible.add(node["id"])
                possible_calls[node["id"]] = available
                future_weights.append(node.get("weight", 1))
                future_calls.update(c["_index"] for c in available)
                reusable_future |= bool(node.get("observation_reuse_group"))
        graph_possible = all(
            not node.get("required", True)
            or _branch(node.get("branch"), spec, local) is not True
            or node["id"] in possible
            for node in ordered
        ) and all(
            any(all(n in possible for n in route) for route in group["alternatives"])
            for group in groups.values()
            if group.get("required", True)
        )
        # Without explicit reuse, one actual call witnesses at most one node.
        # A declared reuse group can make that capacity bound too small; use
        # all possible node weights as a conservative upper bound in that case.
        # This never grants scientific credit or bypasses a predicate.
        capacity = (
            len(future_weights)
            if reusable_future
            else min(len(future_weights), len(future_calls))
        )
        weight_bound = sum(n.get("weight", 1) for n in ordered if n["id"] in matched)
        weight_bound += sum(sorted(future_weights, reverse=True)[:capacity])
        # A demonstrably wrong answer cannot become correct by assigning more
        # optional calls. Inspect predicates only when every referenced node has
        # one possible actual observation. Ambiguous evidence remains optimistic;
        # this bound neither invents observations nor grants scientific credit.
        determined = {
            key: values[0] for key, values in possible_calls.items() if len(values) == 1
        }
        determined_context = dict(context, nodes=determined)

        def possible_truth(rule):
            if any(
                selector["node"] not in determined
                for selector in _selectors(rule)
                if selector["source"] in {"node", "node_arguments"}
            ):
                return None
            try:
                return predicate(rule, determined_context)
            except (MissingEvidence, TypeError, OverflowError):
                return False

        science_bound, has_required_outcome, required_impossible = 0, False, False
        for outcome in spec["outcomes"]:
            branch = outcome.get("branch")
            active = True if branch is None else possible_truth(branch_rules[branch])
            if active is False:
                continue
            grounded = _grounded(outcome, possible, groups)
            truth = possible_truth(outcome)
            if outcome.get("required", True):
                has_required_outcome = True
                if active is True and (not grounded or truth is False):
                    required_impossible = True
            if grounded and truth is not False:
                science_bound += outcome.get("weight", 1)
        return (
            int(graph_possible and has_required_outcome and not required_impossible),
            int(graph_possible),
            weight_bound,
            science_bound,
        )

    def outcome_weight(matched):
        local = dict(context, nodes=matched)
        total = 0
        for outcome in spec["outcomes"]:
            try:
                if (
                    _branch(outcome.get("branch"), spec, local) is True
                    and _grounded(outcome, matched, groups)
                    and predicate(outcome, local)
                ):
                    total += outcome.get("weight", 1)
            except (MissingEvidence, TypeError, OverflowError):
                pass
        return total

    def assignment_quality(matched):
        local = dict(context, nodes=matched)
        node_states = [
            (node, _branch(node.get("branch"), spec, local)) for node in ordered
        ]
        outcome_states = [
            (outcome, _branch(outcome.get("branch"), spec, local))
            for outcome in spec["outcomes"]
        ]
        unresolved = any(active is None for _, active in node_states + outcome_states)
        required_nodes = [
            node
            for node, active in node_states
            if active is True and node.get("required", True)
        ]
        graph_complete = (
            (
                bool(required_nodes)
                or any(g.get("required", True) for g in groups.values())
            )
            and not unresolved
            and all(node["id"] in matched for node in required_nodes)
            and all(
                _group_satisfied(group, matched)
                for group in groups.values()
                if group.get("required", True)
            )
        )
        required_outcomes = [
            outcome
            for outcome, active in outcome_states
            if active is True and outcome.get("required", True)
        ]
        science_complete = bool(required_outcomes) and not unresolved
        for outcome in required_outcomes:
            try:
                if not _grounded(outcome, matched, groups) or not predicate(
                    outcome, local
                ):
                    science_complete = False
            except (MissingEvidence, TypeError, OverflowError):
                science_complete = False
        weight = sum(node.get("weight", 1) for node in ordered if node["id"] in matched)
        return (
            int(graph_complete and science_complete),
            int(graph_complete),
            weight,
            outcome_weight(matched),
        )

    def walk(position, matched, used):
        nonlocal best, visits, truncated, best_score
        # A first complete witness may consume an observation under a shorter
        # alternative and hide useful downstream work. Continue the bounded
        # search until every potentially matchable call is represented, or the
        # full declared evidence bound is reached. Never require unused routes.
        # Using all calls alone is not a certificate of optimality: different
        # alternative nodes may have different weights or ground other outcomes.
        if best_score[0] == 1 and best_score[2:] == (full_weight, full_science):
            return
        if optimistic_quality(position, matched, used) <= best_score:
            return
        visits += 1
        if visits > search_limit:
            truncated = True
            return
        score = assignment_quality(matched)
        if score > best_score:
            best_score, best = score, dict(matched)
        if position == len(ordered):
            return
        node = ordered[position]
        local = dict(context, nodes=matched)
        active = _branch(node.get("branch"), spec, local)
        parents = node.get("depends_on", [])
        if active is True and all(p in matched for p in parents):
            minimum = max((matched[p]["_index"] for p in parents), default=-1)
            for call in candidates[node["id"]]:
                if (
                    observation_available(node, call, matched, used)
                    and call["_index"] > minimum
                    and matches(node, call, matched)
                ):
                    walk(
                        position + 1,
                        dict(matched, **{node["id"]: call}),
                        used | {call["_index"]},
                    )
                    if truncated:
                        return
        walk(position + 1, matched, used)

    walk(0, {}, set())
    context["nodes"] = best
    node_rows = []
    for node in ordered:
        active = _branch(node.get("branch"), spec, context)
        node_rows.append(
            {
                "id": node["id"],
                "capability": node.get("capability", node["id"]),
                "applicable": active,
                "matched": node["id"] in best,
                "required": node.get("required", True),
                "weight": node.get("weight", 1),
                "observation_id": best.get(node["id"], {}).get("observation_id"),
            }
        )
    outcomes = []
    for outcome in spec["outcomes"]:
        active = _branch(outcome.get("branch"), spec, context)
        grounded = _grounded(outcome, best, groups)
        try:
            correct = predicate(outcome, context) if active is True else None
            reason = None
        except (MissingEvidence, TypeError, OverflowError) as exc:
            correct, reason = False, str(exc)
        outcomes.append(
            {
                "id": outcome["id"],
                "applicable": active,
                "correct": correct,
                "grounded": grounded,
                "passed": correct is True and grounded,
                "required": outcome.get("required", True),
                "weight": outcome.get("weight", 1),
                "reason": reason,
            }
        )
    applicable_nodes = [r for r in node_rows if r["applicable"] is True]
    applicable_outcomes = [r for r in outcomes if r["applicable"] is True]
    unresolved_conditions = []
    branch_by_id = {b["id"]: b for b in spec.get("branches", [])}
    for kind, definitions, rows in (
        ("node", ordered, node_rows),
        ("outcome", spec["outcomes"], outcomes),
    ):
        for definition, row in zip(definitions, rows):
            if row["applicable"] is not None:
                continue
            branch = branch_by_id[definition["branch"]]
            missing_nodes = sorted(
                {
                    selector["node"]
                    for selector in _selectors(branch["when"])
                    if selector["source"] in {"node", "node_arguments"}
                    and selector["node"] not in best
                }
            )
            unresolved_conditions.append(
                {
                    "kind": kind,
                    "id": row["id"],
                    "reason": (
                        "missing_prerequisite_execution"
                        if missing_nodes
                        else "unavailable_condition_value"
                    ),
                    "missing_nodes": missing_nodes,
                }
            )
    # Not executing a required prerequisite is an ordinary model evidence failure,
    # not a changed reference or an independently reviewable source ambiguity.
    pending = truncated or any(
        item["reason"] != "missing_prerequisite_execution"
        for item in unresolved_conditions
    )
    required_nodes = [r for r in applicable_nodes if r["required"]]
    required_outcomes = [r for r in applicable_outcomes if r["required"]]
    group_rows = [
        {
            "id": group["id"],
            "required": group.get("required", True),
            "weight": group.get("weight", 1),
            "matched": _group_satisfied(group, best),
            "matched_routes": [
                route
                for route in group["alternatives"]
                if all(n in best for n in route)
            ],
        }
        for group in groups.values()
    ]
    orchestration_pass = (
        (bool(required_nodes) or any(r["required"] for r in group_rows))
        and all(r["matched"] for r in required_nodes)
        and all(r["matched"] for r in group_rows if r["required"])
        and not pending
        and not unresolved_conditions
    )
    science_pass = (
        bool(required_outcomes)
        and all(r["passed"] for r in required_outcomes)
        and not pending
        and not unresolved_conditions
    )
    fraction = lambda rows, field: (
        sum(r["weight"] for r in rows if r[field]) / sum(r["weight"] for r in rows)
        if rows
        else 0.0
    )
    # A method choice earns one capability's credit, independent of its number
    # of primitive calls. Unused alternative routes cannot lower that credit.
    # Optional diagnostic nodes remain visible and their actual observations can
    # count as useful work. Omitting an optional operation cannot lower the
    # required-capability score, whether or not it belongs to a method group.
    credit_nodes = [r for r in applicable_nodes if r["required"]] + [
        r for r in group_rows if r["required"]
    ]
    used = {c["_index"] for c in best.values()}
    useful_executions = {_execution_signature(c) for c in best.values()}
    policy = spec.get("efficiency", {})
    eligible_recovery = {
        tool
        for node in ordered
        for alt in node["alternatives"]
        for tool in alt["tools"]
    }
    eligible_recovery.update(policy.get("recovery_tools", []))
    eligible_disambiguation = set(policy.get("disambiguation_tools", []))
    # Every repeated execution is charged, including a repeat assigned to an
    # overlapping alternative node. One distinct result earns useful credit once.
    duplicates, signatures, exempt, recovery_used, exploration_used = 0, set(), [], 0, 0
    for call in calls:
        signature = _execution_signature(call)
        duplicate = signature in signatures
        signatures.add(signature)
        if duplicate:
            duplicates += 1
            continue
        # If a later occurrence was selected as the witness, the earlier copy
        # cannot also obtain a recovery/exploration allowance.
        if call["_index"] in used or signature in useful_executions:
            continue
        if (
            call.get("tool") in eligible_recovery
            and call.get("status") != "success"
            and recovery_used < policy.get("free_recovery_calls", 0)
        ):
            recovery_used += 1
            exempt.append(call["observation_id"])
        elif (
            call.get("tool") in eligible_disambiguation
            and call.get("status") == "success"
            and exploration_used < policy.get("free_disambiguation_calls", 0)
        ):
            exploration_used += 1
            exempt.append(call["observation_id"])
    charged = max(0, len(calls) - len(exempt))
    efficiency = len(useful_executions) / charged if charged else 0.0
    has_answer = answer is not None and (
        not isinstance(answer, (str, list, dict)) or bool(answer)
    )
    runtime_pass = (
        prediction.get("completed") is True
        and has_answer
        and not prediction.get("failure_reason")
        and prediction.get("status")
        not in {"failed", "error", "blocked", "timeout", "quarantined"}
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "id": reference.get("id"),
        "runtime_pass": runtime_pass,
        "planning_pass": orchestration_pass,
        "answer_pass": science_pass,
        "joint_pass": runtime_pass and orchestration_pass and science_pass,
        "orchestration_credit": fraction(credit_nodes, "matched"),
        "scientific_credit": fraction(applicable_outcomes, "passed"),
        "answer_only_credit": fraction(applicable_outcomes, "correct"),
        "evidence_coverage": fraction(applicable_outcomes, "grounded"),
        "selection_efficiency": efficiency,
        "raw_selection_efficiency": (
            len(useful_executions) / len(calls) if calls else 0.0
        ),
        "matched_scientific_calls": len(useful_executions),
        "charged_scientific_calls": charged,
        "recovery_exempt_calls": recovery_used,
        "exploration_exempt_calls": exploration_used,
        "scientific_calls": len(calls),
        "discovery_calls": discovery,
        "successful_tool_names": sorted(
            {c["tool"] for c in calls if c.get("status") == "success"}
        ),
        "redundant_calls": duplicates,
        "exempt_observations": exempt,
        "nodes": node_rows,
        "capability_groups": group_rows,
        "outcomes": outcomes,
        "pending_review": pending,
        "unresolved_conditions": unresolved_conditions,
        "pending_review_reasons": (["assignment_search_limit"] if truncated else [])
        + sorted(
            {
                item["reason"]
                for item in unresolved_conditions
                if item["reason"] != "missing_prerequisite_execution"
            }
        ),
        "search_truncated": truncated,
        "runtime_failure": prediction.get("failure_reason"),
        "trusted_trace_required": True,
    }


def evaluate_workflows(references, predictions, *, aliases=None, catalog_tools=None):
    """Separate batch adapter; callers dispatch by schema without changing old scores."""
    references, predictions = list(references), list(predictions)
    ids = [r["id"] for r in references]
    if not ids or len(set(ids)) != len(ids):
        raise ValueError("References must have unique nonempty task IDs")
    indexed = {}
    for prediction in predictions:
        if prediction["id"] in indexed or prediction["id"] not in ids:
            raise ValueError("Unknown or duplicate prediction task ID")
        indexed[prediction["id"]] = prediction
    rows = []
    for reference in references:
        row = score_workflow(
            reference,
            indexed.get(reference["id"]),
            aliases=aliases,
            tool_contracts=catalog_tools if isinstance(catalog_tools, dict) else None,
        )
        row.update(
            supplied=reference["id"] in indexed,
            completed=row["runtime_pass"],
            completion_pass=row["runtime_pass"],
        )
        rows.append(row)
    mean = lambda field: sum(float(r[field]) for r in rows) / len(rows)
    summary = {
        "scoring_protocol": SCHEMA_VERSION,
        "total_reference_tasks": len(rows),
        "supplied_predictions": len(indexed),
        "missing_predictions": len(rows) - len(indexed),
        "pass_rate": mean("runtime_pass"),
        "tool_planning_accuracy": mean("planning_pass"),
        "final_answer_accuracy": mean("answer_pass"),
        "joint_pass_rate": mean("joint_pass"),
        "mean_orchestration_credit": mean("orchestration_credit"),
        "mean_scientific_credit": mean("scientific_credit"),
        "mean_evidence_coverage": mean("evidence_coverage"),
        "mean_selection_efficiency": mean("selection_efficiency"),
        "mean_raw_selection_efficiency": mean("raw_selection_efficiency"),
        "pending_reviews": sum(r["pending_review"] for r in rows),
        "joint_accuracy_lower_bound": mean("joint_pass"),
        "joint_accuracy_upper_bound": sum(
            r["joint_pass"] or (r["runtime_pass"] and r["pending_review"]) for r in rows
        )
        / len(rows),
        "describe_tools_excluded_from_planning_and_call_budget": True,
        "llm_judge_used": False,
        "trust_boundary": "Input calls must be authenticated harness observations; this scorer does not authenticate traces.",
    }
    capabilities = {
        node["capability"]
        for row in rows
        for node in row["nodes"]
        if node["applicable"] is True
    }
    matched = {
        node["capability"] for row in rows for node in row["nodes"] if node["matched"]
    }
    tools = {tool for row in rows for tool in row["successful_tool_names"]}
    diagnostics = {
        "applicable_capability_labels": sorted(capabilities),
        "matched_capability_labels": sorted(matched),
        "applicable_capability_instances": sum(
            node["applicable"] is True for row in rows for node in row["nodes"]
        ),
        "matched_capability_instances": sum(
            node["matched"] for row in rows for node in row["nodes"]
        ),
        "successful_tool_names": sorted(tools),
        "successful_distinct_tools": len(tools),
        "coverage_affects_scientific_score": False,
        "note": "Capability labels need a shared reviewed taxonomy for cross-task aggregation. Tool-name coverage counts actual successful calls, never reference alternatives or discovery.",
    }
    if catalog_tools is not None:
        universe = (
            {aliases.get(t, t) for t in catalog_tools}
            if aliases
            else set(catalog_tools)
        )
        universe.discard("DescribeTools")
        diagnostics.update(
            catalog_scientific_tools=len(universe),
            catalog_tool_coverage=(
                len(tools & universe) / len(universe) if universe else None
            ),
            unknown_successful_tools=sorted(tools - universe),
        )
    return {"summary": summary, "results": rows, "coverage_diagnostics": diagnostics}
