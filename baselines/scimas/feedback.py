"""Compact review-to-repair evidence and observable repair effects."""
from copy import deepcopy


def deterministic_review(stage, context, gates):
    """No scientific judgment: expose only checks the runtime already performs."""
    reason = "Scientific Reviewer disabled; deterministic checks only, not scientific approval."
    if stage == "graph" and not context["graph_validation"]["valid"]:
        return {"reject": "Invalid graph: " + str(context["graph_validation"]["errors"])}
    if stage == "result":
        if context["structural_validation"] != "passed":
            return {"reject": str(context["structural_validation"])}
        certificate = context.get("numerical_certificate")
        if certificate and not certificate["passed"]:
            return {"reject": "Deterministic numerical verification failed"}
        return {"accept": {"reason": reason, "semantics": []}}
    # Final format/citation checks happen in finish() before reaching this call.
    return {"approve": {"reason": reason, "gates": gates}}


def review_basis(stage, context):
    """Keep precise checks and evidence IDs; raw outputs remain in observations."""
    keys = ("node", "observation_id", "structural_validation", "numerical_certificate")
    basis = {key: deepcopy(context[key]) for key in keys if context.get(key) is not None}
    provenance = context.get("argument_provenance", {})
    if provenance:
        basis["source_observations"] = deepcopy(provenance.get("source_observations", {}))
        basis["resolution_verified"] = provenance.get("resolution_verified")
    if stage == "graph":
        validation = context.get("graph_validation", {})
        basis["graph_validation"] = {
            key: deepcopy(validation[key]) for key in ("valid", "errors")
            if key in validation
        }
        basis["graph_validation"]["runtime_obligation_count"] = len(validation.get("runtime_obligations", []))
    return basis


def repair_feedback(reviews, request, graph_sha256):
    """Transfer only the review that actually requested this correction."""
    for review in reversed(reviews):
        if review["graph_sha256"] != graph_sha256:
            continue
        decision = review["decision"]
        matches = decision.get("repair") == request
        matches |= (review["stage"] == "graph" and "reject" in decision
                    and request["reason"] == "Initial graph review requested correction: " + decision["reject"])
        if matches:
            return {key: deepcopy(review[key]) for key in ("stage", "node", "decision", "basis")
                    if key in review}
    return None


def plan_change_summary(before, after):
    """A changed description is observable, but is not a changed computation."""
    old = {n["id"]: n for n in before["nodes"]}
    new = {n["id"]: n for n in after["nodes"]}
    fields = {}
    for nid in sorted(old.keys() & new.keys()):
        changed = sorted(k for k in old[nid].keys() | new[nid].keys()
                         if old[nid].get(k) != new[nid].get(k))
        if changed:
            fields[nid] = changed
    added, removed = sorted(new.keys() - old.keys()), sorted(old.keys() - new.keys())
    operational = bool(added or removed or any(
        set(keys) & {"tool", "arguments", "for_each", "when", "checks", "semantics", "object"}
        for keys in fields.values()
    ))
    return {"added_nodes": added, "removed_nodes": removed, "changed_fields": fields,
            "operational_change": operational,
            "deliverables_changed": before["deliverables"] != after["deliverables"]}


def repair_evidence_state(record, graph, results, pruned):
    """Applied/reviewed graphs are not counted as successful tool recovery."""
    affected = set(record["delta"]["invalidate"]) & {n["id"] for n in graph.plan["nodes"]}
    accepted, excluded, pending = [], [], []
    for nid in sorted(affected):
        identity = graph.node_identity(nid)
        if results.get(nid, {}).get("node_sha256") == identity:
            accepted.append(nid)
        elif pruned.get(nid, {}).get("node_sha256") == identity:
            excluded.append(nid)
        else:
            pending.append(nid)
    return {"accepted_nodes": accepted, "excluded_nodes": excluded, "pending_nodes": pending,
            "graph_sha256": graph.identity,
            "status": "pending_execution" if pending else "affected_evidence_available",
            "task_success_proven": False}
