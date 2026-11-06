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
from baselines.common.metrics import task_metrics
from src.utils.io import atomic_json
from src.models.communication import infrastructure_failure
from tools.runtime.contracts import contract_errors
from .schema import TEXT, ID, PATH, obj
from .task_graph import TaskGraph, at, digest, descendants, node_dependencies
from .knowledge import ToolKnowledge, fresh_queries, embedding_usage_since
from .planner import Planner, ACTION_SCHEMA
from .runner import asset_previews
from .roles import Roles, RecordedClient
from .executor import Executor
from .experience import Experience
from .ablation.policy import resolve_ablation, DisabledExperience, LocalRepairDisabled
from .trajectory import append_step
from .verification import numerical_certificate
from .validation import validate_graph

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
    scimas_ablation="full",
    **unused,
):
    """Same public task/trace interface as ReAct; never reads evaluator data."""
    case_id = case_id or "custom"
    policy = resolve_ablation(scimas_ablation)
    if max_failures_per_action is not None and (
        type(max_failures_per_action) is not int or max_failures_per_action < 0
    ):
        raise ValueError("max_failures_per_action must be a nonnegative integer or None")
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
    settings = policy.apply(settings)
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
        "ablation": policy.document(),
        "run_id": run_id,
        "task_id": case_id,
        "dataset": dataset,
        "task": deepcopy(task),
        "model": getattr(client, "model", "injected"),
        "backend": getattr(client, "backend", "injected"),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "running",
        "steps": [],
        "graphs": [],
        "reviews": [],
        "repairs": [],
        "repair_attempts": [],
        "graph_refinements": [],
        "graph_refinement_attempts": [],
        "retrievals": [],
        "gate_evaluations": [],
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
    memory_class = Experience if policy.experience else DisabledExperience
    memory = memory_class(settings["experience_capacity"], settings["experience_matches"])
    evaluated_gates = set()
    gate_states = {}
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
    refinements = 0
    repair_window = None
    executor = Executor(invoke, folder / "calls", settings["tool_concurrency"])
    failures = {}
    assets = []
    output_previews = {}
    planning_report = None
    embedding_baseline = deepcopy(knowledge.embedding.stats) if knowledge is not None else {}

    def save():
        if planning_report is not None and "planning" not in trace:
            # Full request messages already live in steps: avoid serializing a
            # second copy at every planning checkpoint.
            trace["planning_progress"] = {
                key: value for key, value in planning_report.items() if key != "steps"
            }
        trace.update(
            resource_usage=resources.snapshot(),
            stats=dict(stats),
            experiences=deepcopy(memory.entries),
            results=deepcopy(results),
            pruned=deepcopy(pruned),
            approved_gates=dict(gates),
            pending_calls=[
                {
                    key: record[key]
                    for key in (
                        "node",
                        "tool",
                        "node_sha256",
                        "arguments",
                        "files",
                        "timeout_seconds",
                        "started",
                        "directory",
                        "stale",
                    )
                    if key in record
                }
                for record in executor.running.values()
            ],
        )
        query_usage = embedding_usage_since(knowledge.embedding, embedding_baseline) if knowledge is not None else {}
        trace["metrics"] = task_metrics(
            trace["resource_usage"],
            calls,
            runtime_seconds=trace.get("duration_seconds"),
            pending_calls=list(executor.running.values()),
            finished=trace["status"] != "running",
            communication_wait_seconds=query_usage.get("communication_wait_seconds", 0),
            infrastructure_failure=trace.get("infrastructure_failure"),
            communication_intervals=query_usage.get("communication_intervals", []),
        )
        # Preserve every durable checkpoint and raw request, but avoid repeatedly
        # pretty-printing the growing trajectory at each execution boundary.
        atomic_json(path, trace, indent=None)

    def add_step(step):
        return append_step(trace, step, resources)

    def planning_update(report):
        nonlocal planning_report
        planning_report = report

    def recorded(role):
        def request_context():
            if role == "repair" and repair_window is not None:
                return {"revision_stage": repair_window["stage"], "remaining_requests": max(0, settings["repair_requests"] - (
                    len(resources.requests) - repair_window["start_request_count"]
                ))}
            return {}

        def guard():
            if role == "repair" and repair_window is not None:
                used = len(resources.requests) - repair_window["start_request_count"]
                if used >= settings["repair_requests"]:
                    repair_window.update(status="request_limit", requests=used)
                    raise ValueError(
                        "RepairRequestLimit: no valid replacement within "
                        + str(settings["repair_requests"])
                        + " generation requests. Last feedback: "
                        + str(repair_window.get("last_error", "No replacement plan submitted"))
                    )
        return RecordedClient(client, resources, role, trace, save, max_iterations,
                              request_guard=guard, request_context=request_context)

    def protocol_error(errors):
        nonlocal think_streak
        think_streak = 0
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
        prompt_suffix=policy.instructions(),
    )

    def evidence():
        preview = {}
        node_ids = {n["id"] for n in graph.plan["nodes"]}
        observed_nodes = {call["node"] for call in observations.values()} & node_ids
        identities = {nid: graph.node_identity(nid) for nid in observed_nodes}
        for oid, call in observations.items():
            if call["kind"] == "discovery":
                continue
            # Outputs are immutable after logging; cache only their serialization,
            # never graph validity or acceptance, which can change during repair.
            if oid not in output_previews:
                text = json.dumps(call["output"], ensure_ascii=False)
                truncated = len(text) > settings["observation_preview_chars"]
                output_previews[oid] = {
                    "output": None if truncated else call["output"],
                    "preview": (
                        text[: settings["observation_preview_chars"]]
                        if truncated
                        else None
                    ),
                    "truncated": truncated,
                }
            preview[oid] = {
                "tool": call["tool"],
                "status": call["status"],
                "node": call["node"],
                "node_sha256": call["node_sha256"],
                "stale": call.get("stale", False)
                or call["node"] not in node_ids
                or call["node_sha256"] != identities.get(call["node"]),
                "accepted_for_current_graph": results.get(call["node"], {}).get(
                    "observation_id"
                )
                == oid
                and call["node"] not in pruned
                and results[call["node"]]["node_sha256"]
                == identities.get(call["node"]),
                **output_previews[oid],
                **{key: deepcopy(call[key]) for key in
                   ("error", "error_type", "missing_resources") if key in call},
            }
            preview[oid]["review_state"] = (
                "stale" if preview[oid]["stale"] else
                "accepted" if preview[oid]["accepted_for_current_graph"] else
                call.get("review_state", "unreviewed")
            )
        return preview

    def context(role, **extra):
        return {
            "task": task,
            "public_assets": assets,
            "graph": graph.document(),
            "current_graph_nodes": [n["id"] for n in graph.plan["nodes"]],
            "accepted_result_nodes": list(results),
            "accepted_observations": {
                nid: value["observation_id"] for nid, value in results.items()
            },
            "pruned": pruned,
            "observations": evidence(),
            "experience": memory.match(role, graph.contracts),
            "execution_policy": policy.document(),
            "gate_states": dict(gate_states),
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
        add_step({"type": "inspect", "request": request, "value": selected})
        return selected

    def ask(role, payload, schema, *, feedback_out=None):
        nonlocal think_streak
        # Preserve caller feedback (including final format/scientific corrections)
        # when adding inspection and thinking history for this decision.
        feedback = list(payload.get("feedback", []))
        previous_auxiliary, repeated_auxiliary = None, 0
        decision_schema = schema
        while True:
            decision = roles.ask(role, {**payload, "feedback": feedback}, decision_schema)
            if role == "repair" and repair_window is not None:
                trace["steps"][-1]["stage"] = repair_window["stage"]
            if "inspect" in decision or "think" in decision:
                identity = digest(decision)
                repeated_auxiliary = repeated_auxiliary + 1 if identity == previous_auxiliary else 1
                previous_auxiliary = identity
                if repeated_auxiliary >= settings["protocol_retries"]:
                    productive = [branch for branch in schema["oneOf"]
                                  if not ({"inspect", "think"} & branch["properties"].keys())]
                    decision_schema = {**schema, "oneOf": productive}
                    feedback.append({"progress_feedback":
                        "This identical auxiliary decision has already been served. "
                        "Use the supplied evidence and choose a productive action from response_schema."})
                    trace["steps"][-1]["progress_intervention"] = "request_productive_decision"
            if "inspect" in decision:
                think_streak = 0
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
                if feedback_out is not None:
                    feedback_out[:] = feedback
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
        gate_states.clear()
        decision = review(
            "graph", contracts=knowledge.planning_view(sorted(graph.contracts)),
            graph_validation=validate_graph(graph, catalog),
        )
        if "repair" in decision:
            return decision["repair"]
        if "reject" in decision and not stats["scientific_calls"] and not executor.running:
            # A pre-execution concern is feedback to the planner, not evidence
            # that the task itself is impossible. All variants get this chance.
            return {"nodes": [n["id"] for n in graph.plan["nodes"]],
                    "reason": "Initial graph review requested correction: " + decision["reject"]}
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
        nonlocal graph, repairs, refinements, gates, repair_window
        initial = not stats["scientific_calls"] and not executor.running
        if not initial and not policy.local_repair:
            add_step({"type": "repair_disabled", "request": deepcopy(request)})
            raise LocalRepairDisabled(request["reason"])
        while True:
            if initial:
                if refinements >= settings["graph_refinements"]:
                    raise ValueError("GraphRefinementLimit: " + request["reason"])
                refinements += 1
            else:
                if repairs >= settings["local_repairs"]:
                    raise ValueError("LocalRepairLimit: " + request["reason"])
                repairs += 1
            old = graph
            ids = {n["id"] for n in old.plan["nodes"]}
            if not request["nodes"] or not set(request["nodes"]) <= ids:
                raise ValueError("Repair must identify existing affected nodes")
            # Before execution there is no validated scientific work to retain;
            # a source adapter may need correction along with its consumers.
            # During execution, local repair must preserve unaffected evidence.
            allowed = ids if initial else descendants(old.plan, set(request["nodes"]))
            contracts = knowledge.planning_view(sorted(old.contracts))
            feedback = []
            search_history, completed_queries = [], set()
            repair_window = {
                "round": refinements if initial else repairs,
                "stage": "graph_refinement" if initial else "local_repair",
                "request": deepcopy(request), "status": "planning",
                "start_request_count": len(resources.requests),
                "max_requests": settings["repair_requests"],
            }
            trace["graph_refinement_attempts" if initial else "repair_attempts"].append(repair_window)
            while True:
                action = ask(
                    "repair",
                    context(
                        "planner",
                        request=request,
                        revision_stage=repair_window["stage"],
                        allowed_changes=sorted(allowed),
                        contracts=contracts,
                        feedback=feedback,
                        search_history=search_history,
                        remaining_requests=max(0, settings["repair_requests"] - (
                            len(resources.requests) - repair_window["start_request_count"]
                        )),
                    ),
                    {**ACTION_SCHEMA, "oneOf": ACTION_SCHEMA["oneOf"] + [
                        obj({"inspect": INSPECT}), obj({"think": TEXT})
                    ]},
                    feedback_out=feedback,
                )
                if "stop" in action:
                    raise ValueError("RepairPlannerStopped: " + action["stop"])
                if "describe_tools" in action:
                    # A bad name is public lookup feedback, not a fatal repair.
                    errors = []
                    try:
                        discovery(action["describe_tools"])
                    except ValueError as error:
                        errors.append({"error": str(error)})
                    for name in action["describe_tools"]:
                        try:
                            if catalog.canonical(name) not in catalog.tools:
                                raise ValueError("Unknown, retired or excluded tool: " + name)
                            contracts.update(knowledge.planning_view([name]))
                        except ValueError as error:
                            errors.append({"tool": name, "error": str(error)})
                    feedback = [item for item in feedback if "contract_query_errors" not in item]
                    if errors:
                        feedback.append({"contract_query_errors": errors})
                    continue
                if "queries" in action:
                    queries, skipped = fresh_queries(action["queries"], completed_queries)
                    if skipped:
                        feedback.append({"retrieval_notice": "Repeated or blank queries were skipped; use existing contracts or query a genuinely missing capability.",
                                         "skipped_queries": skipped})
                    if queries:
                        found = knowledge.search(queries, resources.deadline)
                        search_history.append(list(queries))
                        trace["retrievals"].append(found)
                        contracts.update(found["tools"])
                    continue
                try:
                    new, delta = old.revise(action["plan"], catalog)
                    if set(delta["changed"]) & (ids - allowed):
                        raise ValueError("Repair modifies unaffected nodes: " + ", ".join(
                            sorted(set(delta["changed"]) & (ids - allowed))
                        ) + ". Copy those nodes unchanged from the current graph.")
                    if not delta["changed"]:
                        raise ValueError("Repair must change the defective branch")
                    break
                except (ValueError, KeyError) as error:
                    repair_window["last_error"] = str(error)
                    feedback = [item for item in feedback if "rejected_plan" not in item]
                    feedback.append({"rejected_plan": action["plan"], "error": str(error)})
            repair_window.update(status="applied", requests=(
                len(resources.requests) - repair_window["start_request_count"]
            ))
            repair_window = None
            executor.invalidate(delta["invalidate"])
            for call in observations.values():
                if call["node"] in delta["invalidate"]:
                    call["stale"] = True
            for nid in delta["invalidate"]:
                results.pop(nid, None)
                pruned.pop(nid, None)
            graph, gates = new, {}
            trace["graphs"].append(graph.document())
            trace["graph_refinements" if initial else "repairs"].append(
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
        call["dispatcher_status"] = response.get("status")
        call["dispatcher_metadata"] = {
            key: value
            for key, value in response.items()
            if key not in {"status", "output"}
        }
        for key in ("files", "timeout_seconds"):
            if key in record:
                call[key] = record[key]
        add_step({"type": "tools", "role": "executor", "calls": [call]})
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
        record = {
            "node": "discovery",
            "tool": "DescribeTools",
            "arguments": {"tools": names},
            "node_sha256": digest(catalog.tools["DescribeTools"]),
            "started": started,
            "directory": str(folder),
            "stale": False,
            "files": [],
            "timeout_seconds": min(tool_timeout, resources.deadline - time.monotonic()),
        }
        try:
            response = invoke(
                "DescribeTools",
                {"tools": names},
                timeout=record["timeout_seconds"],
            )
        except (Exception, KeyboardInterrupt) as error:
            record["finished"] = time.monotonic()
            log_call(
                record,
                {
                    "status": "error",
                    "output": None,
                    "error_type": type(error).__name__,
                    "error": str(error),
                },
            )
            raise
        record["finished"] = time.monotonic()
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
            if response.get("status") != "success":
                structural += "; tool returned " + str(response.get("status"))
                if response.get("error_type"):
                    structural += " (" + str(response["error_type"]) + ")"
                if response.get("error"):
                    structural += ": " + str(response["error"])
        signature = digest({"tool": record["tool"], "arguments": record["arguments"]})
        if accepted is None:
            failures[signature] = failures.get(signature, 0) + 1
            if (
                max_failures_per_action is not None
                and max_failures_per_action > 0
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
                add_step(
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
        certificate = numerical_certificate(record["tool"], record["arguments"], response.get("output"))
        if certificate and not certificate["passed"]:
            structural = "Deterministic numerical verification failed: " + json.dumps(certificate)
            accepted = None
        # Resolution is a mechanical proof of the submitted arguments, not a
        # scientific approval. The Reviewer still checks task intent and units.
        provenance = {
            "declared_arguments": deepcopy(graph.node(nid)["arguments"]),
            "resolved_arguments_field": "arguments",
            "resolution_verified": digest(graph.arguments(nid, results, catalog))
                == digest(record["arguments"]),
            "source_observations": {
                parent: results[parent]["observation_id"]
                for parent in set.union(*node_dependencies(graph.node(nid)))
                if parent in results
            },
        }
        if not provenance["resolution_verified"]:
            accepted = None
            structural = "Submitted arguments do not resolve from the current graph evidence"
        if accepted is None and not policy.local_repair:
            repair({"nodes": [nid], "reason": structural or "Tool execution failed"})
        feedback = []
        for attempt in range(settings["protocol_retries"]):
            call["review_state"] = "pending_review"
            decision = review(
                "result",
                node=nid,
                arguments=record["arguments"],
                observation_id=call["observation_id"],
                structural_validation=structural or "passed",
                contract=knowledge.planning_view([record["tool"]]),
                semantic_feedback=feedback,
                argument_provenance=provenance,
                numerical_certificate=certificate,
            )
            if "repair" in decision:
                call["review_state"] = "repair_requested"
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
                call["review_state"] = "rejected"
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
        previous_rejection, repeated_rejections = None, 0

        def reject_answer(answer, category):
            nonlocal previous_rejection, repeated_rejections
            identity = digest({"answer": answer, "category": category})
            repeated_rejections = repeated_rejections + 1 if identity == previous_rejection else 1
            previous_rejection = identity
            if repeated_rejections >= settings["protocol_retries"]:
                raise ValueError("FinalAnswerNoProgress: unchanged answer repeatedly rejected for " + category)

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
                reject_answer(answer, "format_or_citation")
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
                reject_answer(answer, "scientific_review")
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
            add_step({"type": "finish", "answer": answer})
            return True

    save()
    try:
        knowledge = knowledge or ToolKnowledge(catalog=catalog)
        embedding_baseline = deepcopy(knowledge.embedding.stats)
        trace["embedding_identity"] = deepcopy(knowledge.manifest.get("embedding_identity"))
        assets = asset_previews(task, root / "tasks/full") if files else []
        trace["public_assets"] = assets
        planning = Planner(
            knowledge,
            recorded("planner"),
            max_requests=settings["planning_requests"],
            max_output_tokens=max_output_tokens,
            max_context_chars=max_context_chars,
            timeout=max(0.01, resources.deadline - time.monotonic()),
            describe=discovery,
            schema_guard=protocol_schema_guard,
            on_update=planning_update,
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
                    try:
                        new, delta = graph.expand(
                            node["id"], results, catalog,
                            max_items=settings["max_map_items"],
                        )
                    except (ValueError, KeyError, IndexError, TypeError) as error:
                        repair({"nodes": [node["id"]],
                                "reason": "Template expansion failed: " + str(error)})
                        expanded = True
                        break
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
                state = graph.condition_state(nid, results, approved_gates=gates)
                if "when" in node:
                    gate_states[nid] = state
                    key = (graph.identity, nid, state)
                    if key not in evaluated_gates:
                        evaluated_gates.add(key)
                        action = "continue"
                        if state is None:
                            action = "wait"
                        elif state is False:
                            action = "prune" if policy.early_stop else "continue_without_screening"
                        trace["gate_evaluations"].append({
                            "node": nid, "graph_sha256": graph.identity,
                            "node_sha256": graph.node_identity(nid),
                            "condition": deepcopy(node["when"]), "state": state,
                            "action": action,
                            "recorded_seconds": max(0, resources.clock() - resources.started),
                            "source_observations": {
                                parent: results[parent]["observation_id"]
                                for parent in set.union(*node_dependencies(node))
                                if parent in results
                            },
                        })
                if policy.early_stop and state is False:
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
                    results, catalog, approved_gates=gates, running=running_ids,
                    early_stop=policy.early_stop,
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
            if not policy.parallel:
                # Stable topological tie-breaking uses the approved plan order.
                # Keep the Executor role and review overhead in the comparison.
                ready = [
                    nid for nid in ready
                    if set.union(*node_dependencies(graph.node(nid))) <= results.keys()
                ][:1]
            if ready:
                executor_context = context(
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
                )
                feedback = []
                for _ in range(settings["protocol_retries"]):
                    action = ask(
                        "executor", {**executor_context, "feedback": feedback},
                        EXECUTOR_SCHEMA,
                    )
                    if "dispatch" not in action:
                        break
                    selected = action["dispatch"]
                    unavailable = sorted(set(selected) - set(ready))
                    if not unavailable and len(selected) <= executor_context["available_slots"]:
                        break
                    feedback = [{
                        "error": "Invalid dispatch selection",
                        "unavailable_nodes": unavailable,
                        "available_slots": executor_context["available_slots"],
                        "instruction": "Select only IDs in ready, within available_slots. No rejected node was dispatched.",
                    }]
                    add_step({"type": "selection_error", "role": "executor", "feedback": feedback})
                else:
                    raise ValueError("Executor selection retry limit reached: " + str(feedback))
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
                    arguments = graph.arguments(nid, results, catalog)
                    signature = digest({"tool": node["tool"], "arguments": arguments})
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
                    dispatch_step = add_step(
                        {
                            "type": "dispatch",
                            "node": nid,
                            "tool": node["tool"],
                            "arguments": arguments,
                            "signature": signature,
                            "graph_sha256": graph.identity,
                        }
                    )
                    record = executor.submit(
                        node,
                        graph.node_identity(nid),
                        arguments,
                        parallel=parallel,
                        files=available_files(),
                        timeout=min(
                            tool_timeout, resources.deadline - time.monotonic()
                        ),
                    )
                    dispatch_step.update(
                        directory=record["directory"],
                        files=record["files"],
                        timeout_seconds=record["timeout_seconds"],
                        started_seconds=record["started"] - resources.started,
                        parallel=record["parallel"],
                    )
                    save()
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
            blocked = []
            for nid in unresolved:
                node = graph.node(nid)
                parents = set.union(*node_dependencies(node))
                if not parents <= results.keys():
                    continue
                try:
                    graph.arguments(nid, results, catalog)
                except (ValueError, KeyError, IndexError, TypeError) as error:
                    blocked.append({
                        "node": nid, "error": str(error),
                        "declared_arguments": node["arguments"],
                        "source_semantics": {p: results[p].get("semantics", {}) for p in parents},
                    })
            repair(
                {
                    "nodes": unresolved,
                    "reason": "No runnable nodes: inspect unresolved bindings, semantic requirements, or scientific gates. "
                              + json.dumps({"blocked_bindings": blocked}, ensure_ascii=False),
                }
            )
    except (Exception, KeyboardInterrupt) as error:
        if repair_window is not None:
            repair_window.update(
                status=(repair_window["status"] if repair_window["status"] == "request_limit" else "failed"),
                requests=len(resources.requests) - repair_window["start_request_count"],
                failure_reason=type(error).__name__ + ": " + str(error),
            )
        trace.update(
            status="interrupted" if isinstance(error, KeyboardInterrupt) else "failed",
            final_answer=None,
            failure_reason=type(error).__name__ + ": " + str(error),
        )
        if infrastructure_failure(error):
            trace["infrastructure_failure"] = infrastructure_failure(error)
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
            embedding_usage_since(knowledge.embedding, embedding_baseline) if knowledge is not None else None
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
