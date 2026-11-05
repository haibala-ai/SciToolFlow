"""SciMas: reviewed DAG planning, event-driven execution and local scientific repair."""

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time
import uuid

from baselines.common.answers import (
    answer_format,
    contains_placeholder,
    correction_decision_schema,
)
from baselines.common.protocol import expand_citations
from baselines.common.resources import TaskResources, ResourceLimit
from src.utils.io import atomic_json
from tools.runtime.contracts import contract_errors
from .schema import TEXT, ID, PATH, obj
from .task_graph import TaskGraph, at, digest, descendants, node_dependencies
from .knowledge import ToolKnowledge
from .planner import Planner, ACTION_SCHEMA
from .runner import asset_previews
from .roles import Roles, RecordedClient
from .executor import Executor
from .experience import Experience

IDS = {"type": "array", "items": ID, "uniqueItems": True}
REPAIR = obj({"nodes": IDS, "reason": TEXT})
INSPECT = obj(
    {
        "observation_id": TEXT,
        "path": PATH,
        "decoded": {"type": "boolean"},
        "offset": {"type": "integer", "minimum": 0},
        "limit": {"type": "integer", "minimum": 1, "maximum": 12000},
    },
    ["observation_id", "path", "decoded"],
)
EXTRA = [
    obj({"inspect": INSPECT}),
    obj({"think": TEXT}),
    obj({"repair": REPAIR}),
    obj({"stop": TEXT}),
]
EXECUTOR_SCHEMA = {"oneOf": [obj({"dispatch": dict(IDS, minItems=1)})] + EXTRA}
REVIEW_SCHEMA = {
    "oneOf": [
        obj({"approve": obj({"reason": TEXT, "gates": IDS})}),
        obj(
            {
                "accept": obj(
                    {
                        "reason": TEXT,
                        "semantics": {
                            "type": "array",
                            "items": obj(
                                {
                                    "key": {
                                        "enum": [
                                            "unit",
                                            "object_id",
                                            "method",
                                            "concept",
                                        ]
                                    },
                                    "value": TEXT,
                                    "path": PATH,
                                    "decoded": {"type": "boolean"},
                                }
                            ),
                        },
                    }
                )
            }
        ),
        obj({"repair": REPAIR}),
        obj({"inspect": INSPECT}),
        obj({"reject": TEXT}),
        obj({"revise_answer": TEXT}),
    ]
}


def run_scimas(
    question,
    *,
    catalog,
    client,
    invoke,
    trace_dir,
    case_id=None,
    dataset="full",
    inputs=None,
    files=None,
    answer_schema=None,
    max_model_requests=400,
    task_timeout=7200,
    tool_timeout=180,
    max_iterations=None,
    max_calls=None,
    max_discovery_calls=None,
    max_reasoning_turns=None,
    max_consecutive_thinks=None,
    max_context_chars=180000,
    max_output_tokens=8192,
    max_protocol_errors=3,
    max_actions=4,
    answer_schema_guard=True,
    protocol_schema_guard=True,
    knowledge=None,
    config=None,
    max_identical_tool_steps=10,
    max_failures_per_action=3,
    **unused,
):
    """Same public task/trace interface as ReAct; never reads evaluator data."""
    case_id = case_id or "custom"
    if not re.fullmatch(r"[A-Za-z0-9_-]+", case_id):
        raise ValueError("Unsafe task ID")
    root = catalog.root
    settings = json.loads((Path(__file__).parent / "config.json").read_text())
    if config:
        if set(config) - set(settings):
            raise ValueError("Unknown SciMas configuration")
        settings.update(config)
    if any(
        type(v) is not int
        or v < (0 if k in {"transient_retries", "local_repairs"} else 1)
        for k, v in settings.items()
    ):
        raise ValueError("SciMas configuration requires positive integer bounds")
    run_id = uuid.uuid4().hex[:12]
    folder = Path(trace_dir).resolve() / (case_id + "-" + run_id)
    folder.mkdir(parents=True, exist_ok=False)
    path = folder / "trajectory.json"
    task = {
        "id": case_id,
        "question": question,
        "inputs": inputs or {},
        "files": files or [],
        "answer_schema": answer_schema or {"type": "object"},
    }
    resources = TaskResources(max_model_requests, task_timeout)
    trace = {
        "schema_version": "scitoolflow.trajectory.v1",
        "baseline": "scimas",
        "run_id": run_id,
        "task_id": case_id,
        "dataset": dataset,
        "model": getattr(client, "model", "injected"),
        "backend": getattr(client, "backend", "injected"),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "running",
        "steps": [],
        "graphs": [],
        "reviews": [],
        "repairs": [],
        "retrievals": [],
        "limits": {
            "resource_policy": "task-resources.v1",
            "model_requests": max_model_requests,
            "task_seconds": task_timeout,
            "scientific_calls": max_calls,
            "decisions": max_iterations,
            "discovery_calls": max_discovery_calls,
            "think_steps": max_reasoning_turns,
            "consecutive_thinks": max_consecutive_thinks,
            "tool_seconds": tool_timeout,
            "answer_schema_guard": answer_schema_guard,
            "protocol_schema_guard": protocol_schema_guard,
            **settings,
        },
    }
    memory = Experience(settings["experience_capacity"], settings["experience_matches"])
    calls, results, observations, pruned, retries = [], {}, {}, {}, {}
    stats = dict.fromkeys(
        [
            "model_turns",
            "scientific_calls",
            "discovery_calls",
            "think_steps",
            "inspection_steps",
            "protocol_errors",
            "answer_format_errors",
        ],
        0,
    )
    graph, gates, repairs, think_streak = None, {}, 0, 0
    executor = Executor(invoke, folder / "calls", settings["tool_concurrency"])
    failures = {}
    assets = []

    def save():
        trace.update(
            resource_usage=resources.snapshot(),
            stats=dict(stats),
            experiences=deepcopy(memory.entries),
            results=deepcopy(results),
            pruned=deepcopy(pruned),
        )
        atomic_json(path, trace)

    def recorded(role):
        return RecordedClient(client, resources, role, trace, save, max_iterations)

    def protocol_error(errors):
        stats["protocol_errors"] += 1
        trace["steps"][-1]["protocol_errors"] = list(errors)
        save()

    roles = Roles(
        recorded,
        max_tokens=max_output_tokens,
        max_chars=max_context_chars,
        retries=min(
            settings["protocol_retries"],
            max_protocol_errors or settings["protocol_retries"],
        ),
        schema_guard=protocol_schema_guard,
        on_protocol_error=protocol_error,
    )

    def evidence():
        preview = {}
        for oid, call in observations.items():
            if call["kind"] == "discovery":
                continue
            text = json.dumps(call["output"], ensure_ascii=False)
            preview[oid] = {
                "tool": call["tool"],
                "status": call["status"],
                "node": call["node"],
                "node_sha256": call["node_sha256"],
                "stale": call.get("stale", False)
                or call["node"] not in {n["id"] for n in graph.plan["nodes"]}
                or call["node_sha256"] != graph.node_identity(call["node"]),
                "accepted_for_current_graph": results.get(call["node"], {}).get(
                    "observation_id"
                )
                == oid
                and call["node"] not in pruned
                and results[call["node"]]["node_sha256"]
                == graph.node_identity(call["node"]),
                "output": (
                    call["output"]
                    if len(text) <= settings["observation_preview_chars"]
                    else None
                ),
                "preview": (
                    text[: settings["observation_preview_chars"]]
                    if len(text) > settings["observation_preview_chars"]
                    else None
                ),
                "truncated": len(text) > settings["observation_preview_chars"],
            }
        return preview

    def context(role, **extra):
        return {
            "task": task,
            "public_assets": assets,
            "requirements": graph.requirements,
            "graph": graph.document(),
            "valid_nodes": list(results),
            "accepted_observations": {
                nid: value["observation_id"] for nid, value in results.items()
            },
            "pruned": pruned,
            "observations": evidence(),
            "experience": memory.match(role, graph.contracts),
            **extra,
        }

    def inspect(request):
        call = observations[request["observation_id"]]
        value = call["output"]
        if request["decoded"]:
            spec = catalog.tools[call["tool"]]
            if spec.get("output_encoding", {}).get("decoded_type") not in {
                "json_object",
                "json_array",
            }:
                raise ValueError("Observation has no declared JSON encoding")
            value = json.loads(value)
        selected = at(value, request["path"])
        if isinstance(selected, str):
            offset, limit = request.get("offset", 0), request.get("limit", 6000)
            selected = {
                "text": selected[offset : offset + limit],
                "offset": offset,
                "total_chars": len(selected),
                "next_offset": (
                    offset + limit if offset + limit < len(selected) else None
                ),
            }
        if len(json.dumps(selected, ensure_ascii=False)) > max_context_chars // 3:
            raise ValueError(
                "Inspection too large: select a smaller JSON field or array element"
            )
        stats["inspection_steps"] += 1
        trace["steps"].append(
            {"type": "inspect", "request": request, "value": selected}
        )
        return selected

    def ask(role, payload, schema):
        nonlocal think_streak
        feedback = []
        while True:
            decision = roles.ask(role, {**payload, "feedback": feedback}, schema)
            if "inspect" in decision:
                try:
                    value = inspect(decision["inspect"])
                    feedback.append({"inspection": decision["inspect"], "value": value})
                except (ValueError, KeyError, IndexError, TypeError) as error:
                    feedback.append({"inspection_error": str(error)})
            elif "think" in decision:
                stats["think_steps"] += 1
                think_streak += 1
                trace["steps"][-1]["type"] = "think"
                if (
                    max_reasoning_turns is not None
                    and stats["think_steps"] > max_reasoning_turns
                ) or (
                    max_consecutive_thinks is not None
                    and think_streak > max_consecutive_thinks
                ):
                    raise ResourceLimit("ThinkBudget")
                feedback.append({"previous_thought": decision["think"]})
            else:
                think_streak = 0
                return decision
            save()

    def review(stage, **extra):
        allowed = {
            "graph": {"approve", "repair", "reject", "inspect"},
            "result": {"accept", "repair", "reject", "inspect"},
            "final": {"approve", "repair", "reject", "revise_answer", "inspect"},
        }[stage]
        schema = {
            "oneOf": [
                branch
                for branch in REVIEW_SCHEMA["oneOf"]
                if set(branch["properties"]) <= allowed
            ]
        }
        schema = deepcopy(schema)
        expected_gates = (
            [n["id"] for n in graph.plan["nodes"] if "when" in n]
            if stage == "graph"
            else []
        )
        for branch in schema["oneOf"]:
            if "approve" in branch["properties"]:
                branch["properties"]["approve"]["properties"]["gates"] = {
                    "type": "array",
                    "items": {"enum": expected_gates} if expected_gates else ID,
                    "minItems": len(expected_gates),
                    "maxItems": len(expected_gates),
                    "uniqueItems": True,
                }
        decision = ask(
            "reviewer",
            context("reviewer", stage=stage, conditional_nodes=expected_gates, **extra),
            schema,
        )
        trace["reviews"].append(
            {
                "stage": stage,
                "graph_sha256": graph.identity,
                "node": extra.get("node"),
                "decision": deepcopy(decision),
            }
        )
        save()
        return decision

    def approve_graph():
        nonlocal gates
        decision = review(
            "graph", contracts=knowledge.planning_view(sorted(graph.contracts))
        )
        if "repair" in decision:
            return decision["repair"]
        if "approve" not in decision:
            raise ValueError("Graph scientifically rejected: " + str(decision))
        expected = {n["id"] for n in graph.plan["nodes"] if "when" in n}
        if set(decision["approve"]["gates"]) != expected:
            raise ValueError(
                "Reviewer must explicitly approve exactly the current scientific gates"
            )
        gates = {nid: graph.node_identity(nid) for nid in expected}
        return None

    def repair(request):
        nonlocal graph, repairs, gates
        while True:
            if repairs >= settings["local_repairs"]:
                raise ValueError("LocalRepairLimit: " + request["reason"])
            repairs += 1
            old = graph
            ids = {n["id"] for n in old.plan["nodes"]}
            if not request["nodes"] or not set(request["nodes"]) <= ids:
                raise ValueError("Repair must identify existing affected nodes")
            allowed = descendants(old.plan, set(request["nodes"]))
            contracts = knowledge.planning_view(sorted(old.contracts))
            feedback = []
            while True:
                action = roles.ask(
                    "repair",
                    context(
                        "planner",
                        request=request,
                        allowed_changes=sorted(allowed),
                        contracts=contracts,
                        feedback=feedback,
                    ),
                    ACTION_SCHEMA,
                )
                if "stop" in action:
                    raise ValueError("RepairPlannerStopped: " + action["stop"])
                if "describe_tools" in action:
                    discovery(action["describe_tools"])
                    contracts.update(knowledge.planning_view(action["describe_tools"]))
                    continue
                if "queries" in action:
                    found = knowledge.search(action["queries"], resources.deadline)
                    trace["retrievals"].append(found)
                    contracts.update(found["tools"])
                    continue
                try:
                    new, delta = old.revise(action["plan"], catalog)
                    if set(delta["changed"]) & (ids - allowed):
                        raise ValueError("Repair modifies unaffected nodes")
                    if not delta["changed"]:
                        raise ValueError("Repair must change the defective branch")
                    break
                except (ValueError, KeyError) as error:
                    feedback = [{"rejected_plan": action["plan"], "error": str(error)}]
            executor.invalidate(delta["invalidate"])
            for call in observations.values():
                if call["node"] in delta["invalidate"]:
                    call["stale"] = True
            for nid in delta["invalidate"]:
                results.pop(nid, None)
                pruned.pop(nid, None)
            graph, gates = new, {}
            trace["graphs"].append(graph.document())
            trace["repairs"].append(
                {
                    "request": request,
                    "delta": delta,
                    "parent": old.identity,
                    "graph_sha256": graph.identity,
                    "retained": sorted(results),
                }
            )
            save()
            request = approve_graph()
            if request is None:
                return

    def log_call(record, response):
        status = response.get("status", "error")
        if status not in {"success", "error", "failed", "timeout", "blocked"}:
            status = "blocked"
        call = {
            "observation_id": "o%04d" % (len(calls) + 1),
            "tool": record["tool"],
            "arguments": record["arguments"],
            "status": status,
            "output": response.get("output"),
            "node": record["node"],
            "node_sha256": record["node_sha256"],
            "kind": "discovery" if record["tool"] == "DescribeTools" else "scientific",
            "duration_seconds": record.get("finished", time.monotonic())
            - record["started"],
            "directory": record["directory"],
            "stale": record["stale"],
            "started_seconds": record["started"] - resources.started,
            "finished_seconds": record.get("finished", time.monotonic())
            - resources.started,
        }
        for key in [
            "error",
            "error_type",
            "environment",
            "logical_environment",
            "missing_resources",
        ]:
            if key in response:
                call[key] = response[key]
        calls.append(call)
        observations[call["observation_id"]] = call
        trace["steps"].append({"type": "tools", "role": "executor", "calls": [call]})
        stats[
            "discovery_calls" if call["kind"] == "discovery" else "scientific_calls"
        ] += 1
        save()
        return call

    def discovery(names):
        if (
            max_discovery_calls is not None
            and stats["discovery_calls"] >= max_discovery_calls
        ):
            raise ResourceLimit("DiscoveryBudget")
        resources.check_deadline()
        started = time.monotonic()
        response = invoke(
            "DescribeTools",
            {"tools": names},
            timeout=min(tool_timeout, resources.deadline - time.monotonic()),
        )
        record = {
            "node": "discovery",
            "tool": "DescribeTools",
            "arguments": {"tools": names},
            "node_sha256": digest(catalog.tools["DescribeTools"]),
            "started": started,
            "finished": time.monotonic(),
            "directory": str(folder),
            "stale": False,
        }
        log_call(record, response)
        if response.get("status") != "success":
            raise ValueError(
                "Tool contract discovery failed: " + str(response.get("error"))
            )

    def consume(record, response):
        nid = record["node"]
        call = log_call(record, response)
        if (
            record["stale"]
            or nid not in {n["id"] for n in graph.plan["nodes"]}
            or record["node_sha256"] != graph.node_identity(nid)
        ):
            call["stale"] = True
            return
        structural = None
        try:
            accepted = graph.accept_result(
                nid, response, catalog, environment=response.get("environment")
            )
        except (ValueError, TypeError, KeyError, IndexError) as error:
            structural = str(error)
            accepted = None
        signature = digest({"tool": record["tool"], "arguments": record["arguments"]})
        if accepted is None:
            failures[signature] = failures.get(signature, 0) + 1
            if (
                max_failures_per_action is not None
                and failures[signature] >= max_failures_per_action
            ):
                raise ResourceLimit("RepeatedActionFailure")
            transient = response.get("error_type") in {
                "Timeout",
                "TimeoutError",
                "ConnectionError",
                "ReadTimeout",
                "UpstreamConnectionError",
                "UpstreamRateLimit",
            }
            key = record["node_sha256"]
            if transient and retries.get(key, 0) < settings["transient_retries"]:
                retries[key] = retries.get(key, 0) + 1
                trace["steps"].append(
                    {
                        "type": "retry",
                        "node": nid,
                        "evidence": call["observation_id"],
                        "attempt": retries[key],
                    }
                )
                return
            if not transient:
                memory.invalidate(record["tool"], graph.contracts[record["tool"]])
        feedback = []
        for attempt in range(settings["protocol_retries"]):
            decision = review(
                "result",
                node=nid,
                arguments=record["arguments"],
                observation_id=call["observation_id"],
                structural_validation=structural or "passed",
                contract=knowledge.planning_view([record["tool"]]),
                semantic_feedback=feedback,
            )
            if "repair" in decision:
                repair(decision["repair"])
                if (
                    nid in {n["id"] for n in graph.plan["nodes"]}
                    and graph.node_identity(nid) == record["node_sha256"]
                    and attempt + 1 < settings["protocol_retries"]
                ):
                    feedback = [
                        {
                            "instruction": "The other branch was repaired; review this unchanged observation."
                        }
                    ]
                    continue
                return
            if "accept" not in decision or accepted is None:
                raise ValueError(
                    "ResultRejected: " + str(decision) + "; " + str(structural)
                )
            semantics = {}
            try:
                for assertion in decision["accept"]["semantics"]:
                    raw = response["output"]
                    if assertion["decoded"]:
                        if catalog.tools[record["tool"]].get("output_encoding", {}).get(
                            "decoded_type"
                        ) not in {"json_object", "json_array"}:
                            raise ValueError(
                                "Output is native JSON: use decoded=false; do not invent semantic fields"
                            )
                        raw = json.loads(raw)
                    if digest(at(raw, assertion["path"])) != digest(assertion["value"]):
                        raise ValueError(
                            "Semantic assertion is not grounded in the raw output"
                        )
                    if assertion["key"] in semantics:
                        raise ValueError("Duplicate semantic assertion")
                    semantics[assertion["key"]] = assertion["value"]
                break
            except (ValueError, KeyError, IndexError, TypeError) as error:
                if attempt + 1 == settings["protocol_retries"]:
                    raise ValueError(
                        "Unverified result semantics: " + str(error)
                    ) from error
                feedback = [
                    {
                        "rejected_assertions": decision["accept"]["semantics"],
                        "error": str(error),
                        "instruction": "Use only actual metadata fields. Return semantics=[] when no metadata fields exist.",
                    }
                ]
        accepted.update(semantics=semantics, observation_id=call["observation_id"])
        results[nid] = accepted
        name, contract = record["tool"], graph.contracts[record["tool"]]
        memory.confirm(
            "executor",
            name,
            contract,
            {
                "validated_parameters": sorted(record["arguments"]),
                "binding_kinds": {
                    k: b["kind"] for k, b in graph.node(nid)["arguments"].items()
                },
            },
            [call["observation_id"]],
        )
        memory.confirm(
            "reviewer",
            name,
            contract,
            {
                "output_access": knowledge.tools.get(name, {})
                .get("planning", {})
                .get("output_access"),
                "check": "public_output_contract_and_node_checks",
            },
            [call["observation_id"]],
        )
        parents = set.union(*node_dependencies(graph.node(nid)))
        for parent in parents:
            if parent in results:
                pname = graph.node(parent)["tool"]
                memory.confirm(
                    "planner",
                    pname,
                    graph.contracts[pname],
                    {
                        "consumed_by": name,
                        "bindings": {
                            k: b
                            for k, b in graph.node(nid)["arguments"].items()
                            if b.get("kind") == "node" and b.get("node") == parent
                        },
                    },
                    [results[parent]["observation_id"], call["observation_id"]],
                )
        save()

    def available_files():
        # Only original attachments and files named by accepted outputs inside this
        # run are authorized. An arbitrary path in a tool response gains no access.
        found = set(files or [])

        def walk(value):
            if isinstance(value, dict):
                for item in value.values():
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)
            elif isinstance(value, str) and len(value) < 4096:
                try:
                    candidate = Path(value).resolve()
                    if (
                        candidate.is_relative_to(folder / "calls")
                        and candidate.is_file()
                    ):
                        found.add(str(candidate))
                except (OSError, ValueError):
                    pass

        for result in results.values():
            walk(result["output"])
            if isinstance(result["output"], str):
                try:
                    walk(json.loads(result["output"]))
                except (ValueError, TypeError):
                    pass
        return sorted(found)

    def finish():
        schema = {"oneOf": [obj({"finish": {"type": "object"}})] + EXTRA}
        feedback = []
        while True:
            action = ask(
                "summary",
                context(
                    "executor",
                    answer_format=answer_format(task["answer_schema"]),
                    feedback=feedback,
                ),
                schema,
            )
            if "repair" in action:
                repair(action["repair"])
                return False
            if "stop" in action:
                raise ValueError(action["stop"])
            answer = action["finish"]
            active_observations = {
                value["observation_id"]: observations[value["observation_id"]]
                for nid, value in results.items()
                if nid not in pruned
                and value["node_sha256"] == graph.node_identity(nid)
            }
            try:
                answer = expand_citations(answer, active_observations)
                errors = contract_errors(answer, task["answer_schema"])
            except (ValueError, KeyError, IndexError, TypeError) as error:
                errors = ["Invalid final evidence citation: " + str(error)]
            if contains_placeholder(answer):
                errors.append(
                    "Replace structural placeholders with supported scientific values"
                )
            if errors:
                stats["answer_format_errors"] += 1
                if answer_schema_guard:
                    schema["oneOf"][0] = obj(
                        {
                            "finish": correction_decision_schema(task["answer_schema"])[
                                "anyOf"
                            ][3]["properties"]["finish"]
                        }
                    )
                feedback = [{"previous_answer": answer, "format_errors": errors}]
                continue
            decision = review("final", proposed_answer=answer)
            if "revise_answer" in decision:
                feedback = [
                    {
                        "previous_answer": answer,
                        "scientific_review": decision["revise_answer"],
                    }
                ]
                continue
            if "repair" in decision:
                repair(decision["repair"])
                return False
            if "approve" not in decision:
                raise ValueError("Final scientific review rejected: " + str(decision))
            resources.complete()
            trace.update(status="completed", final_answer=answer, failure_reason=None)
            trace["steps"].append({"type": "finish", "answer": answer})
            return True

    save()
    try:
        knowledge = knowledge or ToolKnowledge(catalog=catalog)
        assets = asset_previews(task, root / "tasks/full") if files else []
        planning = Planner(
            knowledge,
            recorded("planner"),
            max_requests=settings["planning_requests"],
            max_output_tokens=max_output_tokens,
            max_context_chars=max_context_chars,
            timeout=max(0.01, resources.deadline - time.monotonic()),
            describe=discovery,
            schema_guard=protocol_schema_guard,
        ).plan(task, dataset=dataset, assets=assets)
        trace["planning"] = planning
        graph = TaskGraph.load(planning["graph"], task, catalog)
        trace["graphs"].append(graph.document())
        request = approve_graph()
        if request:
            repair(request)
        while True:
            resources.check_deadline()
            # Expand only after actual source evidence is accepted, then re-review new gates.
            expanded = False
            for node in graph.plan["nodes"]:
                if "for_each" in node:
                    try:
                        graph.resolve(node["for_each"], results)
                    except (ValueError, KeyError, IndexError, TypeError):
                        continue
                    new, delta = graph.expand(
                        node["id"],
                        results,
                        catalog,
                        max_items=settings["max_map_items"],
                    )
                    executor.invalidate(delta["invalidate"])
                    for nid in delta["invalidate"]:
                        results.pop(nid, None)
                        pruned.pop(nid, None)
                    graph = new
                    trace["graphs"].append(graph.document())
                    request = approve_graph()
                    if request:
                        repair(request)
                    expanded = True
                    break
            if expanded:
                continue
            # False is supported scientific screening; unresolved and failed are never false.
            for node in graph.plan["nodes"]:
                nid = node["id"]
                if graph.condition_state(nid, results, approved_gates=gates) is False:
                    pruned[nid] = {
                        "reason": "scientific_gate_false",
                        "node_sha256": graph.node_identity(nid),
                        "condition": node["when"],
                    }
            # Propagate an excluded branch; complete deliverables are forbidden to depend on gates by graph validation.
            changed = True
            while changed:
                changed = False
                for node in graph.plan["nodes"]:
                    if node["id"] not in pruned and set.union(
                        *node_dependencies(node)
                    ) & set(pruned):
                        pruned[node["id"]] = {
                            "reason": "excluded_ancestor",
                            "node_sha256": graph.node_identity(node["id"]),
                        }
                        changed = True
            running_ids = [r["node"] for r in executor.running.values()]
            ready = [
                nid
                for nid in graph.ready(
                    results, catalog, approved_gates=gates, running=running_ids
                )
                if nid not in pruned
            ]
            ready = [
                nid
                for nid in ready
                if executor.can_submit(
                    knowledge.tools.get(graph.node(nid)["tool"], {})
                    .get("planning", {})
                    .get("parallel_safe")
                    == "isolated_processes_with_resource_limits"
                )
            ]
            if ready:
                action = ask(
                    "executor",
                    context(
                        "executor",
                        ready=[
                            {
                                "id": nid,
                                "tool": graph.node(nid)["tool"],
                                "arguments": graph.arguments(nid, results, catalog),
                            }
                            for nid in ready
                        ],
                        running=running_ids,
                        available_slots=min(
                            settings["tool_concurrency"] - len(executor.running),
                            max_actions or settings["tool_concurrency"],
                        ),
                    ),
                    EXECUTOR_SCHEMA,
                )
                if "repair" in action:
                    repair(action["repair"])
                    continue
                if "stop" in action:
                    raise ValueError(action["stop"])
                selected = action["dispatch"]
                if not set(selected) <= set(ready) or len(selected) > min(
                    settings["tool_concurrency"] - len(executor.running),
                    max_actions or settings["tool_concurrency"],
                ):
                    raise ValueError(
                        "Executor selected unavailable nodes or exceeded available slots"
                    )
                for nid in selected:
                    node = graph.node(nid)
                    parallel = (
                        knowledge.tools.get(node["tool"], {})
                        .get("planning", {})
                        .get("parallel_safe")
                        == "isolated_processes_with_resource_limits"
                    )
                    if not executor.can_submit(parallel):
                        break  # Resource mutex: queue remaining ready nodes on the next decision.
                    scientific = node["tool"] != "DescribeTools"
                    in_flight = sum(
                        (r["tool"] != "DescribeTools") == scientific
                        for r in executor.running.values()
                    )
                    used = (
                        stats["scientific_calls" if scientific else "discovery_calls"]
                        + in_flight
                    )
                    limit = max_calls if scientific else max_discovery_calls
                    if limit is not None and used >= limit:
                        raise ResourceLimit(
                            "ScientificCallBudget" if scientific else "DiscoveryBudget"
                        )
                    signature = digest(
                        {
                            "tool": node["tool"],
                            "arguments": graph.arguments(nid, results, catalog),
                        }
                    )
                    submitted = [
                        s["signature"]
                        for s in trace["steps"]
                        if s["type"] == "dispatch"
                    ]
                    streak = 0
                    for previous in reversed(submitted):
                        if previous != signature:
                            break
                        streak += 1
                    if (
                        max_identical_tool_steps is not None
                        and streak >= max_identical_tool_steps
                    ):
                        raise ResourceLimit("ConsecutiveIdenticalToolCalls")
                    trace["steps"].append(
                        {
                            "type": "dispatch",
                            "node": nid,
                            "signature": signature,
                            "graph_sha256": graph.identity,
                        }
                    )
                    executor.submit(
                        node,
                        graph.node_identity(nid),
                        graph.arguments(nid, results, catalog),
                        parallel=parallel,
                        files=available_files(),
                        timeout=min(
                            tool_timeout, resources.deadline - time.monotonic()
                        ),
                    )
            if executor.running:
                for record, response in executor.completed():
                    consume(record, response)
                continue
            complete = all(
                n["id"] in results or n["id"] in pruned for n in graph.plan["nodes"]
            )
            if complete:
                if finish():
                    break
                continue
            unresolved = [
                n["id"]
                for n in graph.plan["nodes"]
                if n["id"] not in results and n["id"] not in pruned
            ]
            repair(
                {
                    "nodes": unresolved,
                    "reason": "No runnable nodes: inspect unresolved bindings, semantic requirements, or scientific gates",
                }
            )
    except (Exception, KeyboardInterrupt) as error:
        trace.update(
            status="interrupted" if isinstance(error, KeyboardInterrupt) else "failed",
            final_answer=None,
            failure_reason=type(error).__name__ + ": " + str(error),
        )
        if hasattr(error, "report"):
            trace["planning"] = error.report
    finally:
        executor.cancel_all()
        while executor.running:
            for record, response in executor.completed():
                log_call(
                    record, response
                )  # Preserve real calls even if cancelled/invalidated.
        executor.close()
        stats["model_turns"] = len(resources.requests)
        trace["embedding_usage"] = (
            deepcopy(knowledge.embedding.stats) if knowledge is not None else None
        )
        if trace.get("planning"):
            stats["protocol_errors"] += sum(
                bool(s.get("protocol_errors")) for s in trace["planning"]["steps"]
            )
        trace["finished_at"] = datetime.now(timezone.utc).isoformat()
        trace["duration_seconds"] = time.monotonic() - resources.started
        save()
    return {
        **trace,
        "trace_path": str(path),
        "calls": calls,
        "observations": observations,
    }
