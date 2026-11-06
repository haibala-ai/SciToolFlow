"""Task-specific certificates of useful work and bounded recovery/exploration."""

from .matching import _branch, _execution_signature, _matches
from .causality import observed_before
from .allocation import allocate_certificates
from .method_cover import select_methods

TRANSIENT_ERRORS = frozenset({
    "Timeout", "TimeoutError", "ConnectionError", "ReadTimeout",
    "UpstreamConnectionError", "UpstreamRateLimit", "RemoteProtocolError",
})
DIAGNOSTIC_ERRORS = frozenset({'InvalidInput'})


def validate_efficiency(policy, node_ids, branches):
    """Validate task-scoped certificates before any call can earn efficiency credit."""
    from .schema import _selectors
    if not isinstance(policy, dict):
        raise ValueError("Efficiency policy must be an object")
    if type(policy.get("single_route_efficiency", False)) is not bool:
        raise ValueError("Single-route efficiency must be boolean")
    for name in ("free_recovery_calls", "free_disambiguation_calls"):
        if type(policy.get(name, 0)) is not int or policy.get(name, 0) < 0:
            raise ValueError("Efficiency allowances must be nonnegative integers")
    if "recovery_error_types" in policy and (
        not isinstance(policy["recovery_error_types"], list)
        or not set(policy["recovery_error_types"]) <= TRANSIENT_ERRORS
    ):
        raise ValueError("Recovery allowances require known transient error types")
    comparisons, identifiers = [], set()
    for category in ("useful_work_rules", "recovery_rules", "disambiguation_rules"):
        rules = policy.get(category, [])
        if not isinstance(rules, list):
            raise ValueError("Efficiency certificate lists must be arrays")
        for rule in rules:
            allowed = {"id", "description", "tools", "statuses", "depends_on",
                       "input_rules", "output_rules", "bindings", "max_calls",
                       "branch", "error_types", "before_nodes"}
            if not isinstance(rule, dict) or set(rule) - allowed:
                raise ValueError("Unknown efficiency certificate fields")
            name = rule.get("id")
            if not isinstance(name, str) or not name or name in identifiers:
                raise ValueError("Efficiency certificate IDs must be unique nonempty strings")
            identifiers.add(name)
            if type(rule.get("max_calls")) is not int or rule["max_calls"] < 1:
                raise ValueError("Efficiency certificates require a positive call bound")
            if (not isinstance(rule.get("tools"), list) or not rule["tools"]
                    or "DescribeTools" in rule["tools"]
                    or any(not isinstance(t, str) or not t for t in rule["tools"])):
                raise ValueError("Efficiency certificates require scientific tools")
            statuses = rule.get("statuses", ["success"])
            if not isinstance(statuses, list) or not statuses or not set(statuses) <= {
                "success", "error", "failed", "timeout", "blocked"
            }:
                raise ValueError("Invalid efficiency certificate status")
            if category == "useful_work_rules" and statuses != ["success"]:
                raise ValueError("Useful scientific calculation requires successful observations")
            if category == 'disambiguation_rules' and set(statuses)-{'success'}:
                if (not set(statuses)<={'success','error','failed'}
                        or not rule.get('error_types')
                        or not set(rule['error_types'])<=DIAGNOSTIC_ERRORS):
                    raise ValueError('Failed input diagnostics require explicit bounded diagnostic error types')
            if "error_types" in rule and (
                not isinstance(rule["error_types"], list) or not rule['error_types']
                or category == 'useful_work_rules'
                or not set(rule["error_types"]) <= (TRANSIENT_ERRORS if category=='recovery_rules' else DIAGNOSTIC_ERRORS)
            ):
                raise ValueError("Only explicit transient recovery or scientific input diagnostics are allowed")
            parents = rule.get("depends_on", [])
            if not isinstance(parents, list) or not set(parents) <= set(node_ids):
                raise ValueError("Efficiency dependencies must refer to capability nodes")
            before = rule.get("before_nodes", [])
            if (not isinstance(before, list) or len(set(before)) != len(before)
                    or not set(before) <= set(node_ids) or set(before) & set(parents)
                    or ("before_nodes" in rule and (not before or category != "disambiguation_rules"))):
                raise ValueError("Exploration-before constraints require distinct known scientific nodes")
            if rule.get("branch") and rule["branch"] not in branches:
                raise ValueError("Unknown efficiency certificate branch")
            inputs, outputs = rule.get("input_rules", []), rule.get("output_rules")
            if not isinstance(inputs, list) or not inputs or not isinstance(outputs, list) or not outputs:
                raise ValueError("Efficiency certificates need explicit input and output evidence rules")
            for selector in _selectors(inputs + outputs):
                if selector["source"] == "answer":
                    raise ValueError("Efficiency certificates cannot depend on submitted answers")
                if selector["source"] in {"node", "node_arguments"} and selector["node"] not in parents:
                    raise ValueError("Efficiency cross-node rules require explicit prerequisites")
            for binding in rule.get("bindings", []):
                if binding.get("source_node") not in parents:
                    raise ValueError("Efficiency data bindings require explicit prerequisites")
                if any(not isinstance(binding.get(k), str)
                       or (binding[k] and not binding[k].startswith("/"))
                       for k in ("argument", "output")):
                    raise ValueError("Efficiency bindings require JSON pointers")
            comparisons.extend(inputs + outputs)
    return comparisons


def score_efficiency(spec, calls, matched, context, *, route_limit=100000):
    policy = spec.get("efficiency", {})
    retained = set(matched)
    selected_routes, semantic_duplicates = {}, []
    route_truncated=False;route_visits=0
    node_specs = {n["id"]: n for n in spec["nodes"]}
    grouped = {n for g in spec.get("capability_groups", []) for route in g["alternatives"] for n in route}
    if policy.get("single_route_efficiency"):
        def closure(nodes):
            result=set(nodes);pending=list(result)
            while pending:
                for parent in node_specs[pending.pop()].get('depends_on',[]):
                    if parent not in result:
                        result.add(parent);pending.append(parent)
            return result
        # An optional preparation/descendant of an unused method must not pull
        # the whole unused method back into efficiency credit. Independent
        # verification is an explicit, task-reviewed scientific exception.
        route_scoped=closure(grouped)
        retained={n for n in matched if node_specs[n].get('required',True)
                  or node_specs[n].get('independent_check',False)}
        primary_scoped=closure({n for g in spec.get('capability_groups',[])if g.get('required',True)
                                for route in g['alternatives']for n in route})
        retained=closure(retained)&set(matched)
        signatures={n:_execution_signature(c)for n,c in matched.items()}
        bits={s:1<<i for i,s in enumerate(sorted(set(signatures.values())))}
        def execution_mask(nodes):
            result=0
            for n in nodes:
                if n in signatures:result|=bits[signatures[n]]
            return result
        def route_nodes(route):return closure(n for n in route if n in matched)&set(matched)
        def expand_observed_roles():
            # The same actual result can already prove several separately
            # matched predicates without constituting another execution.
            mask=execution_mask(retained)
            while True:
                ready={n for n in matched if n not in retained and bits[signatures[n]]&mask
                       and set(node_specs[n].get('depends_on',[]))<=retained}
                if not ready:return
                retained.update(ready)
        for required in [True,False]:
            choices={}
            for group in spec.get('capability_groups',[]):
                if group.get('required',True)!=required or _branch(group.get('branch'),spec,context)is not True:
                    continue
                alternatives=group['alternatives']
                if not required:
                    alternatives=[route for route in alternatives if (route_nodes(route)&primary_scoped)<=retained
                        or any(node_specs[n].get('independent_check',False)for n in route)]
                if not alternatives:continue
                complete=[route for route in alternatives if all(n in matched for n in route)]
                if complete:options=complete
                else:
                    progress=max(sum(n in matched for n in route)/len(route)for route in alternatives)
                    options=[route for route in alternatives if sum(n in matched for n in route)/len(route)==progress]
                choices[group['id']]=[(tuple(route),execution_mask(route_nodes(route)))for route in options]
            chosen,unresolved,visits=select_methods(choices,execution_mask(retained),max(0,route_limit-route_visits))
            route_visits+=visits;route_truncated|=unresolved
            selected_routes.update({name:list(route)for name,route in chosen.items()})
            for route in chosen.values():retained.update(route_nodes(route))
            expand_observed_roles()
        # Preserve actual prerequisites shared by the selected scientific routes.
        retained=closure(retained)&set(matched)
        pending={n for n in matched if n not in route_scoped and n not in retained}
        while pending:
            ready={n for n in pending if set(node_specs[n].get('depends_on',[]))<=retained}
            if not ready:break
            retained.update(ready);pending-=ready
    useful = {_execution_signature(matched[n]) for n in retained}
    support, exempt, exemption_certificates = [], [], []
    groups = {}
    for call in calls:
        groups.setdefault(_execution_signature(call), []).append(call)
    duplicates = len(calls) - len(groups)
    eligible_recovery = {
        tool for node in spec["nodes"] for alt in node["alternatives"]
        for tool in alt["tools"]
    } | set(policy.get("recovery_tools", []))
    categories = ("useful_work_rules", "recovery_rules", "disambiguation_rules")
    quotas = {
        "useful_work_rules": len(groups),
        "recovery_rules": policy.get("free_recovery_calls", 0),
        "disambiguation_rules": policy.get("free_disambiguation_calls", 0),
    }
    capacities = {(category, rule["id"]): rule["max_calls"]
                  for category in categories for rule in policy.get(category, [])}
    candidates = []

    first_read_cache = {}

    def matches(rule, call):
        if _branch(rule.get("branch"), spec, context) is not True:
            return False
        parents = rule.get("depends_on", [])
        if any(parent not in matched for parent in parents):
            return False
        if policy.get("single_route_efficiency") and any(p not in retained for p in parents):
            return False
        if any(not observed_before(matched[parent], call) for parent in parents):
            return False
        if rule.get("before_nodes"):
            # Inspecting an unknown source format can be justified only before
            # it has been exposed. Examine every matching actual receipt, not
            # merely the one eventually assigned to a capability: otherwise a
            # later duplicate reader could launder an informed failed probe.
            key = tuple(rule["before_nodes"])
            if key not in first_read_cache:
                first_read_cache[key] = [
                    receipt for receipt in calls if receipt.get("status") == "success"
                    and any(_matches(node_specs[nid], receipt, context) for nid in key)
                ]
            readers = first_read_cache[key]
            if not readers or not all(observed_before(call, receipt) for receipt in readers):
                return False
        if "error_types" in rule and call.get("error_type") not in rule["error_types"]:
            return False
        node = {"bindings": rule.get("bindings", []), "alternatives": [rule]}
        return _matches(node, call, context)

    for signature, observations in groups.items():
        if signature in useful:
            continue
        for call in observations:
            if policy.get("single_route_efficiency") and call.get("status") == "success":
                duplicate_work = False
                for nid in grouped:
                    node = node_specs[nid]
                    parents = node.get("depends_on", [])
                    if any(p not in matched or not observed_before(matched[p], call) for p in parents):
                        continue
                    if _matches(node, call, context):
                        duplicate_work = True
                        break
                if duplicate_work:
                    semantic_duplicates.append(call["observation_id"])
                    continue
            for category in categories:
                if not quotas[category]:
                    continue
                if category == "recovery_rules":
                    if call.get("status") == "success":
                        continue
                    if category in policy:
                        allowed = set(policy.get("recovery_error_types", TRANSIENT_ERRORS))
                        if call.get("error_type") not in allowed:
                            continue
                elif category == 'useful_work_rules' and call.get("status") != "success":
                    continue
                for rule in policy.get(category, []):
                    if matches(rule, call):
                        candidates.append((signature, category, rule["id"], call["observation_id"]))
                # Preserve historical Full policies; revised Mini policies use
                # explicit certificates, even when their allowed list is empty.
                if category not in policy and not policy.get("single_route_efficiency"):
                    legacy = ((category == "recovery_rules" and call.get("tool") in eligible_recovery)
                              or (category == "disambiguation_rules" and call.get("tool") in policy.get("disambiguation_tools", [])))
                    if legacy:
                        capacities[(category, "legacy")] = quotas[category]
                        candidates.append((signature, category, "legacy", call["observation_id"]))
    recovery = exploration = 0
    for signature, category, rule, observation in allocate_certificates(candidates, capacities, quotas):
        if category == "useful_work_rules":
            useful.add(signature)
            support.append({"observation_id": observation, "rule": rule})
        else:
            exempt.append(observation)
            exemption_certificates.append({'observation_id':observation,'rule':rule,'category':category})
            recovery += category == "recovery_rules"
            exploration += category == "disambiguation_rules"
    charged = len(calls) - len(exempt)
    return {
        "selection_efficiency": len(useful) / charged if charged else 0.0,
        "raw_selection_efficiency": len(useful) / len(calls) if calls else 0.0,
        "matched_scientific_calls": len(useful),
        "charged_scientific_calls": charged,
        "recovery_exempt_calls": recovery,
        "exploration_exempt_calls": exploration,
        "redundant_calls": duplicates,
        "exempt_observations": exempt,
        "exemption_certificates": exemption_certificates,
        "supporting_work_observations": support,
        "selected_efficiency_routes": selected_routes,
        "efficiency_evidence_nodes": sorted(retained),
        "efficiency_search_truncated":route_truncated,
        "efficiency_search_visits":route_visits,
        "redundant_semantic_observations": semantic_duplicates,
    }


def orchestration_score(completion, efficiency):
    """A 2:1 weighted harmonic mean; compute per task before macro averaging."""
    if not 0 <= completion <= 1 or not 0 <= efficiency <= 1:
        raise ValueError("Orchestration components must be within [0,1]")
    return 3 * completion * efficiency / (2 * efficiency + completion) if completion and efficiency else 0.0
