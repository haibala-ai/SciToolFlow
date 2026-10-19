"""KG retrieval → planning → per-tool parameter extraction → summary/replanning.

Adapted from upstream scripts/retrieve_tool_info.py and app/llms/planning/ at
ac1cf19fcef84e69f149db6da424afe4e9b2f11f. Bounded role sessions reuse the
ReAct execution harness, not its unrestricted tool-selection strategy.
"""

from datetime import datetime, timezone
import copy
import json
import re
from pathlib import Path
import time
import uuid

from baselines.common.session import SessionOptions
from baselines.react.runtime import run_react
from baselines.react.context import preview
from scitoolflow.io import atomic_json
from .retrieval import GraphRetriever


def run_scitoolagent(
    question,
    *,
    catalog,
    client,
    invoke,
    trace_dir,
    case_id="case",
    inputs=None,
    files=None,
    answer_schema=None,
    max_iterations=80,
    max_calls=32,
    max_actions=8,
    max_discovery_calls=20,
    max_reasoning_turns=8,
    max_consecutive_thinks=2,
    max_protocol_errors=5,
    max_failures_per_action=0,
    max_identical_tool_steps=10,
    answer_schema_guard=True,
    protocol_schema_guard=True,
    task_timeout=1800,
    tool_timeout=180,
    max_context_chars=200000,
    max_output_tokens=4096,
    retriever=None,
):
    if not isinstance(question, str) or not question.strip():
        raise ValueError("A nonempty question is required")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", case_id):
        raise ValueError("Unsafe task identifier")
    root = catalog.root
    config = json.loads((root / "baselines/scitoolagent/config.json").read_text())
    prompt = (root / "baselines/scitoolagent/system_prompt.md").read_text()
    started = time.monotonic()
    deadline = started + task_timeout
    run_id = case_id + "-" + uuid.uuid4().hex[:12]
    path = Path(trace_dir) / run_id / "trajectory.json"
    stats = {
        k: 0
        for k in [
            "model_turns",
            "scientific_calls",
            "discovery_calls",
            "think_steps",
            "inspection_steps",
            "protocol_errors",
            "rejected_actions",
            "answer_format_errors",
            "prompt_tokens",
            "completion_tokens",
            "context_compactions",
            "answer_schema_guard_requests",
            "protocol_schema_guard_requests",
            "max_consecutive_identical_tool_steps",
        ]
    }
    trajectory = {
        "schema_version": "scitoolflow.trajectory.v1",
        "baseline": "scitoolagent",
        "run_id": run_id,
        "task_id": case_id,
        "model": getattr(client, "model", "injected"),
        "backend": getattr(client, "backend", "injected"),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "running",
        "steps": [],
        "phases": [],
        "preparations": [],
        "retrievals": [],
        "limits": {
            "decisions": max_iterations,
            "scientific_calls": max_calls,
            "discovery_calls": max_discovery_calls,
            "think_steps": max_reasoning_turns,
            "consecutive_thinks": max_consecutive_thinks,
            "consecutive_protocol_errors": max_protocol_errors,
            "failures_per_identical_action": max_failures_per_action,
            "consecutive_identical_tool_steps": max_identical_tool_steps,
            "answer_schema_guard": bool(answer_schema_guard),
            "protocol_schema_guard": bool(protocol_schema_guard),
            "task_seconds": task_timeout,
            "tool_seconds": tool_timeout,
            "actions_per_decision": max_actions,
            "plan_rounds": config["max_plan_rounds"],
        },
    }
    observations = {}
    calls = []
    contracts = {}
    failures = {}
    repetition_state = {}
    answer = None
    failure = None
    interrupted = False

    def save():
        trajectory["stats"] = dict(stats)
        atomic_json(path, trajectory)

    save()

    def remaining():
        if time.monotonic() >= deadline:
            raise RuntimeError("TaskDeadline")
        if stats["model_turns"] >= max_iterations:
            raise RuntimeError("DecisionBudget")
        return max_iterations - stats["model_turns"]

    def evidence():
        return [
            {
                k: row.get(k)
                for k in ["observation_id", "tool", "status", "error_type", "error"]
            }
            | {
                "arguments": preview(row.get("arguments"), 1600),
                "output": preview(row.get("output"), 1600),
            }
            for row in observations.values()
            if row.get("kind") == "scientific"
        ]

    def phase(role, cycle, schema, allowed, extra, *, stop_after_success=False):
        budget = remaining()
        prefix_steps = list(trajectory["steps"])
        prefix_stats = dict(stats)
        record = {"role": role, "cycle": cycle}
        if role == "executor":
            record.update({k: extra[k] for k in ("planned_tool", "plan_position")})
        trajectory["phases"].append(record)
        instructions = {
            "planner": 'YOUR CURRENT ROLE: PLANNER. Use only retrieved candidates to propose an ordered tool chain. Repeat a name if distinct inputs require it. No tool calls, including DescribeTools, are allowed in this role: candidate metadata is already supplied, and the harness reads each execution contract later. Return {"finish":{"plan":["ToolA","ToolB"]}} using existing candidate names; do not invent arguments or observations. answer_schema describes your plan response; task_answer_schema is the original task output contract to plan toward, not your response format. Use previous evidence to avoid repeating successful work.',
            "executor": "YOUR CURRENT ROLE: PARAMETER EXTRACTOR. Call exactly the specified planned_tool for the one-based plan_position in ordered_plan, using its verified contract and actual available inputs/results. Repeated tool names can represent different entities or inputs; use earlier arguments and outputs to distinguish completed work from this plan item. Inspect part=arguments or part=output for truncated observations. This role cannot finish the task. On a successful scientific call the harness advances to the next plan item. If the plan is impossible, stop with a reason.",
            "summarizer": "YOUR CURRENT ROLE: SUMMARIZER. Assess whether the original task has been solved using actual observations. Return finish satisfying the original public answer_schema. No new scientific tools may be dispatched in this role. If essential evidence is missing, stop with a reason; the planner may then revise the chain.",
        }

        def update(inner):
            record.update(
                initial_messages=inner["initial_messages"],
                limits=inner["limits"],
                status=inner["status"],
            )
            trajectory["initial_messages"] = trajectory["phases"][0].get(
                "initial_messages", []
            )
            converted = []
            for step in inner["steps"]:
                item = copy.deepcopy(step)
                item.update(
                    phase=role,
                    cycle=cycle,
                    phase_step=step["step"],
                    step=len(prefix_steps) + len(converted) + 1,
                )
                converted.append(item)
            trajectory["steps"] = prefix_steps + converted
            for key in stats:
                value = inner.get("stats", {}).get(key, 0)
                stats[key] = (
                    max(prefix_stats[key], value)
                    if key == "max_consecutive_identical_tool_steps"
                    else prefix_stats[key] + value
                )
            save()

        session = SessionOptions(
            baseline="scitoolagent",
            phase=role,
            system_prompt=prompt + "\n\n" + instructions[role],
            allowed_tools=set(allowed),
            allow_discovery=False,
            extra_inputs={
                "task_answer_schema": answer_schema,
                "previous_observations": evidence(),
                **extra,
            },
            observations=observations,
            counter_offsets={
                "scientific_calls": stats["scientific_calls"],
                "discovery_calls": stats["discovery_calls"],
                "model_turns": stats["model_turns"],
            },
            failures=failures,
            repetition_state=repetition_state,
            yield_after_success=stop_after_success,
            persist=False,
            on_update=update,
        )

        result = run_react(
            question,
            catalog=catalog,
            client=client,
            invoke=invoke,
            trace_dir=trace_dir,
            case_id=case_id,
            inputs=inputs,
            files=files,
            answer_schema=schema,
            max_iterations=(
                min(budget, config["planner_max_steps"])
                if role == "planner"
                else budget
            ),
            max_calls=max_calls - stats["scientific_calls"],
            max_actions=1 if role == "executor" else max_actions,
            max_discovery_calls=max_discovery_calls - stats["discovery_calls"],
            max_reasoning_turns=max_reasoning_turns - stats["think_steps"],
            max_consecutive_thinks=max_consecutive_thinks,
            max_protocol_errors=max_protocol_errors,
            max_failures_per_action=max_failures_per_action,
            max_identical_tool_steps=max_identical_tool_steps,
            answer_schema_guard=answer_schema_guard,
            protocol_schema_guard=protocol_schema_guard,
            task_timeout=max(0.01, deadline - time.monotonic()),
            tool_timeout=tool_timeout,
            max_context_chars=max_context_chars,
            max_output_tokens=max_output_tokens,
            session=session,
        )
        calls.extend(result["calls"])
        observations.update(result["observations"])
        record["failure_reason"] = result["failure_reason"]
        return result

    try:
        retriever = retriever or GraphRetriever(catalog, config)
        for cycle in range(1, config["max_plan_rounds"] + 1):
            remaining()
            query = (
                question
                + "\nPublic input field names: "
                + ", ".join((inputs or {}).keys())
            )
            retrieved = retriever.retrieve(query, deadline)
            trajectory["retrievals"].append({"cycle": cycle, **retrieved})
            save()
            names = [t["name"] for t in retrieved["tools"]]
            plan_schema = {
                "type": "object",
                "properties": {
                    "plan": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": max(1, max_calls - stats["scientific_calls"]),
                        "items": {"type": "string", "enum": names},
                    }
                },
                "required": ["plan"],
                "additionalProperties": False,
            }
            planned = phase(
                "planner",
                cycle,
                plan_schema,
                set(),
                {"tool_candidates": retrieved["tools"]},
            )
            if planned["status"] != "completed":
                failure = planned["failure_reason"] or "PlanningFailed"
                if (
                    failure == "DecisionBudget"
                    and stats["model_turns"] < max_iterations
                ):
                    failure = "PlannerDecisionBudget"
                break
            plan = planned["final_answer"]["plan"]
            trajectory["phases"][-1]["plan"] = plan
            save()
            execution_failed = False
            for plan_position, name in enumerate(plan, start=1):
                remaining()
                if stats["scientific_calls"] >= max_calls:
                    raise RuntimeError("ScientificCallBudget")
                if name not in contracts:
                    if stats["discovery_calls"] >= max_discovery_calls:
                        raise RuntimeError("DiscoveryCallBudget")
                    before_read = time.monotonic()
                    row = invoke(
                        "DescribeTools",
                        {"tools": [name]},
                        files=files or [],
                        timeout=min(
                            tool_timeout, max(0.01, deadline - time.monotonic())
                        ),
                    )
                    stats["discovery_calls"] += 1
                    identifier = "d" + str(stats["discovery_calls"]).zfill(3)
                    doc = {
                        "tool": "DescribeTools",
                        "arguments": {"tools": [name]},
                        "kind": "discovery",
                        "status": row["status"],
                        "output": row.get("output"),
                        "observation_id": identifier,
                        "automatic": True,
                        "phase": "executor",
                        "cycle": cycle,
                        "duration_seconds": time.monotonic() - before_read,
                        "error_type": row.get("error_type"),
                        "error": row.get("error"),
                    }
                    calls.append(doc)
                    observations[identifier] = doc
                    trajectory["preparations"].append(doc)
                    save()
                    if row["status"] != "success":
                        raise RuntimeError("ToolContractReadFailed")
                    contracts[name] = row["output"]["tools"][name]
                executed = phase(
                    "executor",
                    cycle,
                    None,
                    {name},
                    {
                        "planned_tool": name,
                        "tool_contract": contracts[name],
                        "ordered_plan": plan,
                        "plan_position": plan_position,
                    },
                    stop_after_success=True,
                )
                if executed["status"] != "yielded":
                    failure = (
                        executed["failure_reason"] or "ExecutorDidNotCallPlannedTool"
                    )
                    execution_failed = True
                    break
            if execution_failed:
                # Protocol failures are terminal, not a reason to restart an unlimited agent loop.
                if failure and (
                    "ProtocolError" in failure
                    or failure in {"DecisionBudget", "TaskDeadline", "RepeatedToolLoop"}
                ):
                    break
                continue
            summarized = phase("summarizer", cycle, answer_schema, set(), {})
            if summarized["status"] == "completed":
                answer = summarized["final_answer"]
                failure = None
                break
            failure = summarized["failure_reason"] or "NotCompleted"
            if not failure.startswith("AgentStopped:"):
                break
    except KeyboardInterrupt:
        failure = "Interrupted"
        interrupted = True
    except Exception as error:
        failure = (
            str(error)
            if str(error)
            in {
                "TaskDeadline",
                "DecisionBudget",
                "ScientificCallBudget",
                "DiscoveryCallBudget",
            }
            else type(error).__name__ + ": " + str(error)[:800]
        )
    if retriever is not None and hasattr(retriever, "embedding"):
        trajectory["embedding_usage"] = dict(retriever.embedding.stats)
    trajectory.update(
        status=(
            "interrupted"
            if interrupted
            else ("completed" if answer is not None else "failed")
        ),
        final_answer=answer,
        failure_reason=failure,
        duration_seconds=time.monotonic() - started,
    )
    save()
    if interrupted:
        raise KeyboardInterrupt
    return {
        **trajectory,
        "trace_path": str(path),
        "calls": calls,
        "observations": observations,
    }
