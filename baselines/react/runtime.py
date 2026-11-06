"""Names-first ReAct baseline; no private reference or tool implementation imports."""

from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math
import re
import time
import uuid
from itertools import count

from baselines.react.context import Context, encode, finite, preview, _inspect
from baselines.common.protocol import parse_reply, expand_citations
from baselines.react.trajectory import atomic_json
from baselines.react.feedback import (
    action_feedback,
    schema_issues,
    required_answer_fields,
)
from tools.catalog import DISCOVERY_TOOL
from baselines.common.answers import (
    AnswerFormatError,
    answer_format,
    render_answer_format,
    contains_placeholder,
    correction_decision_schema,
    protocol_decision_schema,
)
from baselines.common.session import SessionOptions
from baselines.common.resources import (
    TaskResources,
    BudgetedClient,
    ResourceLimit,
    remaining as quota_remaining,
    available,
)
from baselines.common.repetition import ConsecutiveToolSteps
from baselines.common.metrics import task_metrics
from src.models.communication import infrastructure_failure


def build_prompt(catalog, limits):
    from src.utils.paths import project_root

    prompt = (project_root() / "baselines/react/system_prompt.md").read_text().strip()
    groups = catalog.names_by_domain()
    names = encode(dict(sorted(groups.items())))
    return (
        prompt
        + "\n\nRUN LIMITS\n"
        + encode(limits)
        + "\n\nTOOL NAMES BY DISCIPLINE\n"
        + names
    )


def validate_action(action, catalog, observations):
    if not isinstance(action, dict) or set(action) - {"tool", "arguments"}:
        raise ValueError("Each action has only tool and arguments")
    name = action.get("tool")
    arguments = action.get("arguments")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("tool must be a nonempty catalogue name")
    canonical = catalog.canonical(name)
    if canonical not in catalog.tools:
        suggestion = catalog.describe([name])["unknown"]
        raise ValueError(
            "Unknown tool "
            + repr(name)
            + ". "
            + encode(suggestion)
            + ". Use DescribeTools on an existing catalogue name."
        )
    if not isinstance(arguments, dict):
        raise ValueError(name + " arguments must be a JSON object")
    bound = expand_citations(arguments, observations)
    from jsonschema import Draft202012Validator

    errors = schema_issues(
        Draft202012Validator(catalog.tools[canonical]["input_schema"]), bound
    )
    if errors:
        raise ValueError(
            name
            + " input: "
            + encode(errors)
            + ". Use DescribeTools for its exact contract."
        )
    return {"tool": canonical, "arguments": bound}


def run_react(
    question,
    *,
    catalog,
    client,
    invoke,
    trace_dir,
    case_id="case",
    dataset="full",
    inputs=None,
    files=None,
    answer_schema=None,
    max_iterations=None,
    max_calls=None,
    max_actions=8,
    max_discovery_calls=None,
    max_reasoning_turns=None,
    max_consecutive_thinks=None,
    max_protocol_errors=5,
    max_failures_per_action=0,
    max_identical_tool_steps=10,
    answer_schema_guard=True,
    protocol_schema_guard=True,
    task_timeout=7200,
    max_model_requests=400,
    tool_timeout=180,
    max_context_chars=200000,
    max_output_tokens=4096,
    preview_chars=2000,
    clock=time.monotonic,
    session=None,
):
    session = session or SessionOptions()
    from tasks.datasets import dataset_files

    dataset_files(dataset)
    if not isinstance(question, str) or not question.strip():
        raise ValueError("A nonempty question is required")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", case_id):
        raise ValueError("Unsafe task identifier")
    resources = session.resources or TaskResources(
        max_model_requests, task_timeout, clock
    )
    client = BudgetedClient(client, resources, session.phase)
    limits = dict(
        resource_policy="task-resources.v1",
        model_requests=resources.max_model_requests,
        decisions=max_iterations,
        scientific_calls=max_calls,
        actions_per_decision=max_actions,
        discovery_calls=max_discovery_calls,
        think_steps=max_reasoning_turns,
        consecutive_thinks=max_consecutive_thinks,
        task_seconds=task_timeout,
        tool_seconds=tool_timeout,
        consecutive_protocol_errors=max_protocol_errors,
        failures_per_identical_action=max_failures_per_action,
        consecutive_identical_tool_steps=max_identical_tool_steps,
        answer_schema_guard=bool(answer_schema_guard),
        protocol_schema_guard=bool(protocol_schema_guard),
    )
    if any(
        isinstance(v, bool)
        or not isinstance(v, (int, float))
        or not math.isfinite(v)
        or v <= 0
        for k, v in limits.items()
        if k
        not in {
            "resource_policy",
            "decisions",
            "consecutive_thinks",
            "think_steps",
            "scientific_calls",
            "discovery_calls",
            "answer_schema_guard",
            "protocol_schema_guard",
            "failures_per_identical_action",
        }
    ):
        raise ValueError("Execution limits must be positive")
    if isinstance(max_identical_tool_steps, bool) or not isinstance(
        max_identical_tool_steps, int
    ):
        raise ValueError("consecutive_identical_tool_steps must be a positive integer")
    if type(max_failures_per_action) is not int or max_failures_per_action < 0:
        raise ValueError(
            "failures_per_identical_action must be nonnegative; 0 disables it"
        )
    for name, value in [
        ("decisions", max_iterations),
        ("scientific_calls", max_calls),
        ("discovery_calls", max_discovery_calls),
        ("think_steps", max_reasoning_turns),
        ("consecutive_thinks", max_consecutive_thinks),
    ]:
        if value is not None and (
            type(value) is not int
            or value < (1 if name in {"decisions", "consecutive_thinks"} else 0)
        ):
            raise ValueError(name + " must be null or a valid nonnegative integer")
    guide = answer_format(answer_schema) if answer_schema else None
    system = session.system_prompt or build_prompt(catalog, limits)
    if session.system_prompt:
        system += "\n\nRUN LIMITS\n" + encode(limits)
    initial = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": encode(
                {
                    "question": question,
                    "inputs": inputs or {},
                    "files": files or [],
                    "answer_schema": answer_schema,
                    "required_answer_fields": required_answer_fields(answer_schema),
                    **session.extra_inputs,
                }
            ),
        },
    ]
    if guide:
        initial.append({"role": "user", "content": render_answer_format(guide)})
    counter = (
        client.count_tokens if getattr(client, "backend", None) == "vllm" else None
    )
    context = None
    run_id = case_id + "-" + uuid.uuid4().hex[:12]
    path = Path(trace_dir) / run_id / "trajectory.json"
    started = clock()
    deadline = min(started + task_timeout, resources.deadline)
    trajectory = {
        "schema_version": "scitoolflow.trajectory.v1",
        "run_id": run_id,
        "task_id": case_id,
        "dataset": dataset,
        "model": getattr(client, "model", "injected"),
        "backend": getattr(client, "backend", "injected"),
        "baseline": session.baseline,
        "phase": session.phase,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "limits": limits,
        "initial_messages": initial,
        "status": "running",
        "steps": [],
    }
    stats = dict(
        model_turns=0,
        scientific_calls=0,
        discovery_calls=0,
        think_steps=0,
        inspection_steps=0,
        protocol_errors=0,
        rejected_actions=0,
        answer_format_errors=0,
        prompt_tokens=0,
        completion_tokens=0,
        context_compactions=0,
        answer_schema_guard_requests=0,
        protocol_schema_guard_requests=0,
        max_consecutive_identical_tool_steps=0,
    )
    observations = dict(session.observations)
    calls = []
    summaries = []
    failures = session.failures
    consecutive_thinks = 0
    errors = 0
    answer = None
    failure = None
    interrupted = False
    yielded = False
    repetition = ConsecutiveToolSteps(session.repetition_state)
    guarded_schema = None
    visible_input_schemas = {
        DISCOVERY_TOOL: catalog.tools[DISCOVERY_TOOL]["input_schema"]
    }

    def save():
        trajectory["resource_usage"] = resources.snapshot()
        trajectory["metrics"] = task_metrics(
            trajectory["resource_usage"],
            calls,
            runtime_seconds=trajectory.get("duration_seconds"),
            runtime_started_monotonic=started,
            infrastructure_failure=trajectory.get("infrastructure_failure"),
            finished=trajectory["status"] not in {"running", "interrupted"},
        )
        if session.persist:
            atomic_json(path, trajectory)
        if session.on_update:
            session.on_update(trajectory)

    save()
    try:
        context = Context(
            initial,
            max_context_chars,
            counter,
            client.input_budget(max_output_tokens) if counter else None,
        )
        for index in count():
            if max_iterations is not None and index >= max_iterations:
                failure = "DecisionBudget"
                break
            try:
                resources.check()
            except ResourceLimit as error:
                failure = str(error)
                break
            if clock() >= deadline:
                failure = "TaskDeadline"
                break
            remaining = {
                "decisions_including_current": quota_remaining(max_iterations, index),
                "model_requests": resources.remaining_requests(),
                "scientific_calls": quota_remaining(
                    max_calls, stats["scientific_calls"]
                ),
                "discovery_calls": quota_remaining(
                    max_discovery_calls, stats["discovery_calls"]
                ),
                "think_steps": quota_remaining(
                    max_reasoning_turns, stats["think_steps"]
                ),
                "consecutive_thinks": quota_remaining(
                    max_consecutive_thinks, consecutive_thinks
                ),
                "consecutive_protocol_errors": max_protocol_errors - errors,
                "seconds": round(max(0, deadline - clock()), 1),
                "final_decision": (
                    max_iterations is not None and index == max_iterations - 1
                )
                or resources.remaining_requests() == 1,
            }
            messages = context.build(summaries, state={"remaining_budget": remaining})
            stats["model_turns"] += 1
            step = {
                "step": index + 1,
                "type": "pending",
                "remaining_budget": remaining,
                "model": {
                    "prompt_sha256": hashlib.sha256(
                        encode(messages).encode()
                    ).hexdigest()
                },
            }
            trajectory["steps"].append(step)
            scope = (
                client.generation_scope()
                if hasattr(client, "generation_scope")
                else nullcontext()
            )
            try:
                with scope:
                    options = {}
                    request_schema = guarded_schema
                    if protocol_schema_guard and getattr(
                        client, "supports_response_schema", False
                    ):
                        for observation in observations.values():
                            if (
                                observation.get("tool") == DISCOVERY_TOOL
                                and observation.get("status") == "success"
                            ):
                                for spec in (
                                    observation.get("output", {})
                                    .get("tools", {})
                                    .values()
                                ):
                                    if isinstance(spec, dict) and spec.get(
                                        "input_schema"
                                    ):
                                        visible_input_schemas[spec["name"]] = spec[
                                            "input_schema"
                                        ]
                        names = [
                            name
                            for name in catalog.tools
                            if (
                                name == DISCOVERY_TOOL
                                and session.allow_discovery
                                and available(remaining["discovery_calls"])
                            )
                            or (
                                name != DISCOVERY_TOOL
                                and available(remaining["scientific_calls"])
                                and (
                                    session.allowed_tools is None
                                    or name in session.allowed_tools
                                )
                            )
                        ]
                        names += [
                            alias
                            for alias, canonical in catalog.aliases.items()
                            if canonical in names
                        ]
                        request_schema = protocol_decision_schema(
                            names,
                            max_actions=(
                                min(
                                    max_actions,
                                    sum(
                                        v
                                        for v in [
                                            remaining["scientific_calls"],
                                            remaining["discovery_calls"],
                                        ]
                                        if v is not None
                                    ),
                                )
                                if remaining["scientific_calls"] is not None
                                and remaining["discovery_calls"] is not None
                                else max_actions
                            ),
                            answer_schema=(
                                answer_schema if guarded_schema is not None else None
                            ),
                            known_inputs={
                                name: visible_input_schemas[catalog.canonical(name)]
                                for name in names
                                if catalog.canonical(name) in visible_input_schemas
                            },
                            allow_think=available(remaining["think_steps"])
                            and available(remaining["consecutive_thinks"]),
                        )
                        stats["protocol_schema_guard_requests"] += 1
                        step["model"]["visible_input_contracts"] = sorted(
                            visible_input_schemas
                        )
                    if request_schema is not None:
                        options["response_schema"] = request_schema
                    if guarded_schema is not None:
                        stats["answer_schema_guard_requests"] += 1
                    if request_schema is not None:
                        step["model"]["response_schema_sha256"] = hashlib.sha256(
                            encode(request_schema).encode()
                        ).hexdigest()
                        step["model"]["response_schema_source"] = (
                            "public_answer_schema_structure_and_protocol"
                            if guarded_schema is not None
                            else "public_protocol_and_visible_input_contracts"
                        )
                    reply = client.request(
                        messages,
                        max_tokens=max_output_tokens,
                        timeout=max(0.01, deadline - clock()),
                        **options,
                    )
            except Exception as error:
                if infrastructure_failure(error):
                    trajectory["infrastructure_failure"] = infrastructure_failure(error)
                step.update(
                    type="error",
                    error={"type": type(error).__name__, "message": str(error)[:1000]},
                )
                failure = (
                    "TaskDeadline"
                    if clock() >= deadline
                    else (
                        str(error)
                        if isinstance(error, ResourceLimit)
                        else "ModelError: " + str(error)[:500]
                    )
                )
                break
            usage = reply.get("usage") or {}
            step["model"].update(
                response_id=reply.get("response_id"),
                usage=usage or None,
                duration_seconds=reply.get("duration_seconds"),
                truncated=bool(reply.get("truncated")),
                provider_backend=reply.get(
                    "provider_backend", getattr(client, "backend", None)
                ),
                requested_model=reply.get(
                    "request_model", getattr(client, "model", None)
                ),
                response_model=reply.get("model"),
                execution_mode=(
                    "resident_service"
                    if reply.get("device_map") == "resident_service"
                    else (
                        "transformers"
                        if isinstance(reply.get("device_map"), dict)
                        else None
                    )
                ),
            )
            stats["prompt_tokens"] += usage.get("prompt_tokens", 0) or 0
            stats["completion_tokens"] += usage.get("completion_tokens", 0) or 0
            try:
                if reply.get("truncated"):
                    raise ValueError(
                        "Response was truncated at the output token limit; nothing executed. "
                        "Send a shorter complete decision, avoid reprinting observations, "
                        "and use observation references for large values."
                    )
                decision = parse_reply(reply["text"])
                if decision.get("actions") == [] and decision.get("intent"):
                    decision = {"think": decision["intent"]}
                # A short note beside an operation is equivalent to optional intent,
                # not a second standalone thinking decision.
                operations = [
                    k for k in ["actions", "inspect", "finish", "stop"] if k in decision
                ]
                if len(operations) == 1 and isinstance(decision.get("think"), str):
                    decision = dict(decision)
                    note = decision.pop("think")
                    decision.setdefault("intent", note)
                    step["normalizations"] = ["think_alongside_operation_as_intent"]
                if sum(
                    k in decision
                    for k in ["actions", "think", "inspect", "finish", "stop"]
                ) != 1 or set(decision) - {
                    "actions",
                    "think",
                    "inspect",
                    "finish",
                    "intent",
                    "stop",
                }:
                    raise ValueError(
                        "Choose exactly one of actions, think, inspect, finish or stop; optional intent is allowed. "
                        "All answer fields belong inside finish, not beside it."
                    )
                if "intent" in decision and not isinstance(decision["intent"], str):
                    raise ValueError("intent must be a short string")
                step["decision"] = decision
                context.append("assistant", encode(decision))
                if "think" in decision:
                    note = decision["think"]
                    if not isinstance(note, str) or not note.strip():
                        raise ValueError(
                            "think must be a nonempty working-state string"
                        )
                    if (
                        max_reasoning_turns is not None
                        and stats["think_steps"] >= max_reasoning_turns
                    ) or (
                        max_consecutive_thinks is not None
                        and consecutive_thinks >= max_consecutive_thinks
                    ):
                        raise ValueError(
                            "Thinking limit reached; call a tool, inspect evidence or finish"
                        )
                    stats["think_steps"] += 1
                    consecutive_thinks += 1
                    step["type"] = "think"
                    context.append(
                        "user",
                        encode(
                            {
                                "think_step_recorded": True,
                                "remaining_think_steps": quota_remaining(
                                    max_reasoning_turns, stats["think_steps"]
                                ),
                                "remaining_consecutive_thinks": quota_remaining(
                                    max_consecutive_thinks, consecutive_thinks
                                ),
                                "next": "Call tools, inspect or finish when the consecutive-think limit is reached.",
                            }
                        ),
                    )
                    errors = 0
                elif "inspect" in decision:
                    view = _inspect(
                        decision["inspect"], observations, preview_chars * 2
                    )
                    step.update(type="inspect", observation=view)
                    stats["inspection_steps"] += 1
                    consecutive_thinks = 0
                    context.append("user", encode(view))
                    errors = 0
                elif "finish" in decision:
                    if session.yield_after_success:
                        raise ValueError(
                            "This parameter-extraction role must call its planned scientific tool, not finish. Use stop if execution is impossible."
                        )
                    candidate = expand_citations(decision["finish"], observations)
                    if not isinstance(candidate, dict) or not finite(candidate):
                        raise AnswerFormatError("finish must be a finite answer object")
                    if contains_placeholder(candidate):
                        raise AnswerFormatError(
                            "Replace literal <FILL:...> placeholders with typed evidence values before submitting finish"
                        )
                    if answer_schema:
                        from jsonschema import Draft202012Validator

                        invalid = schema_issues(
                            Draft202012Validator(answer_schema), candidate
                        )
                        if invalid:
                            raise AnswerFormatError(
                                "Answer schema: "
                                + encode(invalid)
                                + ". Correct these paths inside finish using the public answer_schema. "
                                "If required evidence is unavailable, use stop with a reason; do not invent values."
                            )
                    if clock() >= deadline:
                        failure = "TaskDeadline"
                        step.update(
                            type="error",
                            error={
                                "type": "TaskDeadline",
                                "message": "Task deadline reached before final submission",
                            },
                        )
                        break
                    if session.phase is None or session.phase == "summarizer":
                        resources.complete()
                    answer = candidate
                    step.update(type="finish", answer=candidate)
                    trajectory["status"] = "completed"
                    break
                elif "stop" in decision:
                    stop = decision["stop"]
                    if (
                        not isinstance(stop, dict)
                        or set(stop) != {"reason"}
                        or not isinstance(stop["reason"], str)
                        or not stop["reason"].strip()
                    ):
                        raise ValueError(
                            "stop must contain exactly one nonempty reason string"
                        )
                    step.update(type="stop", reason=stop["reason"])
                    failure = "AgentStopped: " + stop["reason"][:1000]
                    break
                else:
                    actions = decision["actions"]
                    if (
                        not isinstance(actions, list)
                        or not 1 <= len(actions) <= max_actions
                    ):
                        raise ValueError(
                            "actions must contain 1–"
                            + str(max_actions)
                            + " ready actions; use think for a no-tool turn"
                        )
                    bound, rejected = [], []
                    for position, action in enumerate(actions):
                        try:
                            valid = validate_action(action, catalog, observations)
                            if (
                                valid["tool"] == DISCOVERY_TOOL
                                and not session.allow_discovery
                            ):
                                raise ValueError(
                                    "Tool discovery is provided by the harness in this role; use the supplied metadata and contracts."
                                )
                            if (
                                valid["tool"] != DISCOVERY_TOOL
                                and session.allowed_tools is not None
                                and valid["tool"] not in session.allowed_tools
                            ):
                                raise ValueError(
                                    "This role may call only its planned tool(s): "
                                    + encode(sorted(session.allowed_tools))
                                    + ". Use stop to request replanning if the plan is insufficient."
                                )
                            if (
                                max_failures_per_action > 0
                                and failures.get(encode(valid), 0)
                                >= max_failures_per_action
                            ):
                                raise ValueError(
                                    "Identical tool inputs have repeatedly failed; change inputs or use stop to report the limitation"
                                )
                            bound.append((position, valid))
                        except (ValueError, KeyError, TypeError, IndexError) as error:
                            rejected.append(
                                action_feedback(position, action, error, catalog)
                            )
                    stats["rejected_actions"] += len(rejected)
                    for error in rejected:
                        if error.get("expected_input_schema"):
                            visible_input_schemas[catalog.canonical(error["tool"])] = (
                                error["expected_input_schema"]
                            )
                    step["action_errors"] = rejected
                    science = sum(a["tool"] != DISCOVERY_TOOL for _, a in bound)
                    discovery = len(bound) - science
                    if (
                        max_calls is not None
                        and stats["scientific_calls"] + science > max_calls
                    ):
                        raise ValueError(
                            "Scientific call budget insufficient for this batch; nothing executed. Reduce the batch, finish or stop."
                        )
                    if (
                        max_discovery_calls is not None
                        and stats["discovery_calls"] + discovery > max_discovery_calls
                    ):
                        raise ValueError(
                            "Discovery call budget insufficient for this batch; nothing executed. Reuse known contracts, finish or stop."
                        )
                    if not bound:
                        raise ValueError(
                            "No actions executed. Correct the rejected actions listed in action_errors."
                        )
                    step.update(type="tools", calls=[])
                    feedback = []
                    for position, action in bound:
                        if clock() >= deadline:
                            failure = "TaskDeadline"
                            break
                        kind = (
                            "discovery"
                            if action["tool"] == DISCOVERY_TOOL
                            else "scientific"
                        )
                        stat = (
                            "discovery_calls"
                            if kind == "discovery"
                            else "scientific_calls"
                        )
                        stats[stat] += 1
                        identifier = ("d" if kind == "discovery" else "o") + str(
                            stats[stat] + session.counter_offsets.get(stat, 0)
                        ).zfill(3)
                        begin = clock()
                        call_interrupted = False
                        try:
                            row = invoke(
                                action["tool"],
                                action["arguments"],
                                files=files or [],
                                timeout=min(
                                    tool_timeout, max(0.01, deadline - clock())
                                ),
                            )
                            if not isinstance(row, dict) or row.get("status") not in {
                                "success",
                                "error",
                                "blocked",
                                "skipped",
                            }:
                                raise ValueError("Invalid dispatcher envelope")
                            encode(row)
                        except KeyboardInterrupt:
                            call_interrupted = True
                            row = {
                                "status": "error",
                                "output": None,
                                "error_type": "Interrupted",
                                "error": "Tool call interrupted",
                            }
                        except Exception as error:
                            row = {
                                "status": "error",
                                "output": None,
                                "error_type": type(error).__name__,
                                "error": str(error)[:1000],
                            }
                        call = {
                            **action,
                            "action_index": position,
                            "kind": kind,
                            "status": row["status"],
                            "output": row.get("output"),
                            "observation_id": identifier,
                            "duration_seconds": clock() - begin,
                            "error_type": row.get("error_type"),
                            "error": row.get("error"),
                        }
                        diagnostics = {
                            key: row[key]
                            for key in [
                                "worker_stderr",
                                "worker_stdout",
                                "missing_resources",
                                "environment",
                                "logical_environment",
                            ]
                            if row.get(key)
                        }
                        if diagnostics:
                            # Dispatcher has already redacted credentials recursively.
                            call["dispatcher_diagnostics"] = diagnostics
                        step["calls"].append(call)
                        calls.append(call)
                        observations[identifier] = call
                        if call_interrupted:
                            raise KeyboardInterrupt
                        if row["status"] != "success":
                            failures[encode(action)] = (
                                failures.get(encode(action), 0) + 1
                            )
                        visible = {
                            k: call[k]
                            for k in [
                                "tool",
                                "kind",
                                "status",
                                "observation_id",
                                "error_type",
                                "error",
                            ]
                        }
                        visible["output"] = (
                            call["output"]
                            if kind == "discovery"
                            else preview(call["output"], preview_chars)
                        )
                        if row["status"] != "success" and diagnostics:
                            visible["diagnostic_hint"] = preview(diagnostics, 1000)
                        if kind == "scientific" and row.get("error_type") in {
                            "InvalidInput",
                            "TypeError",
                            "ValidationError",
                        }:
                            visible["suggested_action"] = {
                                "tool": DISCOVERY_TOOL,
                                "arguments": {"tools": [action["tool"]]},
                            }
                            call["suggested_action"] = visible["suggested_action"]
                        feedback.append(visible)
                        summaries.append(
                            {**visible, "output": preview(call["output"], 200)}
                        )
                        if (
                            session.yield_after_success
                            and kind == "scientific"
                            and call["status"] == "success"
                        ):
                            yielded = True
                            break
                    context.append(
                        "user",
                        encode(
                            {
                                "observations": feedback,
                                "action_errors": rejected,
                                "remaining_scientific_calls": quota_remaining(
                                    max_calls, stats["scientific_calls"]
                                ),
                            }
                        ),
                    )
                    consecutive_thinks = 0
                    errors = 0
                    if failure or yielded:
                        break
            except (ValueError, KeyError, TypeError, IndexError) as error:
                errors += 1
                stats["protocol_errors"] += 1
                is_answer_error = isinstance(error, AnswerFormatError)
                stats["answer_format_errors"] += int(is_answer_error)
                step.update(
                    type="error",
                    raw_response=reply["text"],
                    error={
                        "type": (
                            "AnswerFormatError" if is_answer_error else "ProtocolError"
                        ),
                        "message": str(error)[:1500],
                    },
                )
                feedback = {
                    "error": step["error"],
                    "instruction": "Correct the named issue. Query DescribeTools only for tool-contract questions.",
                }
                if step.get("action_errors"):
                    feedback["action_errors"] = step["action_errors"]
                if is_answer_error and guide:
                    if answer_schema_guard and getattr(
                        client, "supports_response_schema", False
                    ):
                        guarded_schema = correction_decision_schema(
                            answer_schema, max_actions=max_actions
                        )
                    feedback["answer_format"] = guide
                    feedback["schema_constrained_correction"] = (
                        guarded_schema is not None
                    )
                    feedback["instruction"] = (
                        "Formatting correction only: rewrite finish to match the supplied tree and correct the named paths. Keep supported scientific values; do not rerun successful tools to fix JSON nesting. The harness does not fill or move any values."
                    )
                    step["format_feedback"] = guide
                    # Put the readable tree last, so it remains visible during correction.
                    context.append(
                        "user", encode(feedback) + "\n\n" + render_answer_format(guide)
                    )
                else:
                    context.append("user", encode(feedback))
                if errors >= max_protocol_errors:
                    failure = "RepeatedProtocolError"
                    break
            finally:
                streak = repetition.observe(
                    step,
                    stats["model_turns"]
                    + session.counter_offsets.get("model_turns", 0),
                )
                stats["max_consecutive_identical_tool_steps"] = max(
                    stats["max_consecutive_identical_tool_steps"], streak
                )
                if streak:
                    step["consecutive_identical_tool_steps"] = streak
                if streak >= max_identical_tool_steps and failure is None:
                    failure = "RepeatedToolLoop"
                    yielded = False
                    step["loop_termination"] = {
                        **repetition.state,
                        "limit": max_identical_tool_steps,
                    }
                    step["error"] = {
                        "type": "RepeatedToolLoop",
                        "message": f"Terminated after {streak} consecutive tool decision steps with the same tool and resolved arguments; no next model request is sent.",
                    }
                trajectory["stats"] = dict(stats)
                save()
            if failure:
                break
        if answer is None and failure is None and not yielded:
            failure = "DecisionBudget"
    except KeyboardInterrupt:
        failure = "Interrupted"
        interrupted = True
        if trajectory["steps"] and trajectory["steps"][-1]["type"] == "pending":
            trajectory["steps"][-1].update(
                type="error",
                error={
                    "type": "Interrupted",
                    "message": "Generation interrupted by user",
                },
            )
    except Exception as error:
        if infrastructure_failure(error):
            trajectory["infrastructure_failure"] = infrastructure_failure(error)
        failure = (
            str(error)
            if isinstance(error, ResourceLimit)
            else type(error).__name__ + ": " + str(error)[:1000]
        )
    stats["context_compactions"] = context.compactions if context else 0
    trajectory.update(
        status=(
            "interrupted"
            if interrupted
            else (
                "yielded"
                if yielded
                else ("completed" if answer is not None else "failed")
            )
        ),
        final_answer=answer,
        failure_reason=failure,
        duration_seconds=clock() - started,
        stats=stats,
    )
    save()
    if interrupted:
        raise KeyboardInterrupt
    return {
        **trajectory,
        "trace_path": str(path) if session.persist else None,
        "calls": calls,
        "observations": observations,
    }
