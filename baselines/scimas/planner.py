"""Bounded public-input planning: decompose, retrieve, propose, validate, revise."""

from contextlib import nullcontext
from copy import deepcopy
import json
import difflib
import re
from pathlib import Path
import time
from tools.runtime.contracts import contract_errors
from .schema import DECOMPOSITION_SCHEMA, PLAN_SCHEMA, TEXT, obj, decoding_schema
from .task_graph import TaskGraph, public_task, digest
from .validation import validate_graph, grounded
from .assets import evidence_sources
from .context import encode_payload
from .knowledge import fresh_queries, embedding_usage_since

ACTION_SCHEMA = {
    "oneOf": [
        obj({"plan": {k: v for k, v in PLAN_SCHEMA.items() if k != "$defs"}}),
        obj(
            {"queries": {"type": "array", "minItems": 1, "maxItems": 8, "items": TEXT}}
        ),
        obj(
            {
                "describe_tools": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 20,
                    "items": TEXT,
                }
            }
        ),
        obj({"stop": TEXT}),
    ],
    "$defs": PLAN_SCHEMA["$defs"],
}


class PlanningFailure(RuntimeError):
    def __init__(self, report):
        self.report = report
        super().__init__(report.get("error", "Planning failed"))


class Planner:
    def __init__(
        self,
        knowledge,
        client,
        *,
        max_requests=8,
        max_retrieval_rounds=3,
        max_output_tokens=8192,
        max_context_chars=180000,
        timeout=600,
        describe=None,
        schema_guard=True,
        on_update=None,
    ):
        for value in (
            max_requests,
            max_retrieval_rounds,
            max_output_tokens,
            max_context_chars,
            timeout,
        ):
            if value <= 0:
                raise ValueError("Planning limits must be positive")
        self.knowledge, self.client = knowledge, client
        self.describe = describe
        self.on_update = on_update
        self.schema_guard = schema_guard
        self.max_requests, self.max_retrieval_rounds = (
            max_requests,
            max_retrieval_rounds,
        )
        self.max_output_tokens, self.max_context_chars, self.timeout = (
            max_output_tokens,
            max_context_chars,
            timeout,
        )
        self.prompt = (Path(__file__).parent / "prompts/planner.md").read_text()
        self.decomposition_prompt = (Path(__file__).parent / "prompts/decompose.md").read_text()

    def plan(self, task, *, dataset="full", assets=None):
        public = public_task(task)
        embedding_baseline = deepcopy(self.knowledge.embedding.stats)
        report = {
            "schema_version": "scimas.planning_run.v1",
            "status": "planning",
            "dataset": dataset,
            "task_id": public["id"],
            "public_task_sha256": digest(public),
            "public_assets_sha256": digest(assets or []),
            "kg_sha256": self.knowledge.manifest["graph_sha256"],
            "steps": [],
            "retrievals": [],
            "contract_queries": [],
            "scientific_calls": 0,
            "scientific_correctness": "not_evaluated",
        }
        deadline = time.monotonic() + self.timeout
        if self.on_update:
            self.on_update(report)

        def request(stage, payload, schema):
            format_feedback = None
            while (
                len(report["steps"]) < self.max_requests and time.monotonic() < deadline
            ):
                messages = [
                    {"role": "system", "content": self.decomposition_prompt
                     if stage == "decompose" else self.prompt},
                    {
                        "role": "user",
                        "content": encode_payload(
                            {
                                "task": public,
                                "public_assets": assets or [],
                                "stage": stage,
                                "response_schema": schema,
                                "instructions": payload,
                                "format_feedback": format_feedback,
                            },
                        ),
                    },
                ]
                if sum(len(m["content"]) for m in messages) > self.max_context_chars:
                    raise ValueError(
                        "Planning context exceeds configured limit; use more focused retrieval"
                    )
                if getattr(self.client, "backend", None) == "vllm":
                    budget = self.client.input_budget(
                        self.max_output_tokens, timeout=deadline - time.monotonic()
                    )
                    count = self.client.count_tokens(
                        messages, timeout=deadline - time.monotonic()
                    )
                    if count > budget:
                        raise ValueError(
                            f"Planning context has {count} tokens; model permits {budget} input tokens"
                        )
                step = {"stage": stage, "messages": messages}
                report["steps"].append(step)
                options = (
                    {"response_schema": decoding_schema(schema)}
                    if self.schema_guard
                    and getattr(self.client, "supports_response_schema", False)
                    else {}
                )
                step["validation_schema_sha256"] = digest(schema)
                step["decoding_schema_sha256"] = (
                    digest(options["response_schema"]) if options else None
                )
                scope = (
                    self.client.generation_scope()
                    if hasattr(self.client, "generation_scope")
                    else nullcontext()
                )
                with scope:
                    reply = self.client.request(
                        messages,
                        max_tokens=self.max_output_tokens,
                        timeout=deadline - time.monotonic(),
                        **options,
                    )
                step["response"] = reply
                text = reply["text"].strip()
                if text.startswith("```json") and text.endswith("```"):
                    text = text[7:-3].strip()
                try:
                    value = json.loads(text)
                    errors = contract_errors(value, schema)
                except (ValueError, TypeError) as error:
                    value = None
                    errors = [
                        "Expected finite JSON matching response_schema: "
                        + type(error).__name__
                    ]
                if hasattr(self.client, "record_validation"):
                    self.client.record_validation(value, errors)
                if not errors:
                    return value
                step["protocol_errors"] = errors
                format_feedback = {
                    "errors": errors,
                    "previous_response": text,
                    "instruction": "Correct the response format using response_schema; no answer information is supplied.",
                }
            raise ValueError("Planning request/time limit reached")

        try:
            instruction = {
                "instruction": "Extract required deliverables and focused scientific subtask queries. Copy each evidence quote as a contiguous verbatim span; do not join fragments or add ellipses."
            }
            while True:
                decomposition = request("decompose", instruction, DECOMPOSITION_SCHEMA)
                invalid = [
                    r["id"]
                    for r in decomposition["requirements"]
                    if not grounded(r["evidence"], public)
                ]
                if not invalid:
                    break
                report["steps"][-1]["grounding_errors"] = invalid
                source = "\n".join(evidence_sources(public))
                options = {}
                for requirement in decomposition["requirements"]:
                    if requirement["id"] not in invalid:
                        continue
                    quote = requirement["evidence"]
                    position = source.lower().find(quote.lower())
                    if position >= 0:
                        options[requirement["id"]] = [
                            source[position : position + len(quote)]
                        ]
                    else:
                        spans = re.split(r"(?<=[.!?。])\s+", source)
                        options[requirement["id"]] = sorted(
                            spans,
                            key=lambda text: difflib.SequenceMatcher(
                                None, quote.lower(), text.lower()
                            ).ratio(),
                            reverse=True,
                        )[:3]
                instruction = {
                    "instruction": "Correct these evidence fields by copying a contiguous original sentence. Do not paraphrase or join excerpts. Preserve scientific requirements.",
                    "invalid_requirements": invalid,
                    "verbatim_source_options": options,
                    "copy_instruction": "Copy a suitable source option exactly, including capitalization. These options are public question text, not answers. Revise unsupported requirements rather than using unrelated quotes.",
                    "previous": decomposition,
                }
            report["requirements"] = decomposition["requirements"]
            candidates, feedback, contracts = {}, [], {}
            search_history = []
            completed_queries = set()
            queries = decomposition["queries"]
            while len(report["steps"]) < self.max_requests:
                if queries:
                    queries, skipped = fresh_queries(queries, completed_queries)
                    if skipped:
                        feedback.append({"retrieval_notice": "Repeated or blank queries were skipped; use existing candidates or query a genuinely missing capability.",
                                         "skipped_queries": skipped})
                    if queries:
                        if len(report["retrievals"]) >= self.max_retrieval_rounds:
                            raise ValueError("Retrieval round limit reached")
                        search_history.append(list(queries))
                        retrieval = self.knowledge.search(queries, deadline)
                        report["retrievals"].append(retrieval)
                        candidates.update(retrieval["tools"])
                summaries = {}
                for name, record in candidates.items():
                    contract = record.get("contract", record)
                    summaries[name] = {
                        "description": contract["description"],
                        "call_signature": contract.get("call_signature"),
                        "output_access": record.get("planning", {}).get(
                            "output_access"
                        ),
                        "planning_constraints": record.get("planning", {})
                        .get("reviewed_annotation", {})
                        .get("constraints", []),
                    }
                action_schema = deepcopy(ACTION_SCHEMA)
                if len(report["retrievals"]) >= self.max_retrieval_rounds:
                    action_schema["oneOf"] = [
                        branch
                        for branch in action_schema["oneOf"]
                        if "queries" not in branch["properties"]
                    ]
                action = request(
                    "graph",
                    {
                        "requirements": decomposition["requirements"],
                        "candidates": summaries,
                        "contracts": contracts,
                        "feedback": feedback,
                        "search_history": search_history,
                        "remaining_retrieval_rounds": self.max_retrieval_rounds
                        - len(report["retrievals"]),
                        "remaining_generation_requests": self.max_requests
                        - len(report["steps"]),
                        "instruction": "Return plan; describe_tools to inspect full contracts for selected names; or queries for missing capabilities.",
                    },
                    action_schema,
                )
                queries = []
                if "stop" in action:
                    raise ValueError("PlannerStopped: " + action["stop"])
                if "queries" in action:
                    queries = action["queries"]
                    continue
                if "describe_tools" in action:
                    try:
                        if self.describe is not None:
                            self.describe(action["describe_tools"])
                        described = self.knowledge.planning_view(
                            action["describe_tools"]
                        )
                    except ValueError as error:
                        feedback = [{"contract_query_error": str(error)}]
                        continue
                    contracts.update(described)
                    candidates.update(described)
                    report["contract_queries"].append(
                        {
                            "tool": "DescribeTools",
                            "names": action["describe_tools"],
                            "mode": "public_catalogue_and_scimas_knowledge_lookup",
                            "contracts": described,
                            "scientific_call": False,
                        }
                    )
                    continue
                plan = action["plan"]
                graph = TaskGraph.create(
                    public,
                    decomposition["requirements"],
                    plan,
                    self.knowledge.catalog,
                    dataset,
                )
                validation = validate_graph(
                    graph, self.knowledge.catalog, allowed=self.knowledge.allowed
                )
                undiscovered = (
                    {n["tool"] for n in plan["nodes"]}
                    - set(candidates)
                    - {"DescribeTools"}
                )
                # Retrieval proposes useful tools; it is not an allowlist. The
                # canonical catalogue and scope decide availability, and the
                # reviewer receives full current contracts before execution.
                available = sorted(name for name in undiscovered
                                   if name in self.knowledge.catalog.tools
                                   and self.knowledge.allowed(name))
                if available:
                    described = (
                        self.knowledge.planning_view(available)
                        if hasattr(self.knowledge, "planning_view") else {
                            name: self.knowledge.catalog.describe(name)["tools"][name]
                            for name in available
                        }
                    )
                    contracts.update(described)
                    candidates.update(described)
                    report["contract_queries"].append({
                        "mode": "plan_contract_resolution", "names": available,
                        "contracts": described, "scientific_call": False,
                    })
                report["steps"][-1]["validation"] = validation
                report["validation"] = validation
                if validation["valid"]:
                    report.update(
                        status="planned",
                        graph=graph.document(),
                        graph_sha256=graph.identity,
                        embedding_usage=embedding_usage_since(self.knowledge.embedding, embedding_baseline),
                    )
                    return report
                # Give actionable contract evidence with errors, without requiring
                # a separate discovery decision or exposing scientific answers.
                used = sorted(
                    {
                        n["tool"]
                        for n in plan["nodes"]
                        if n["tool"] in self.knowledge.catalog.tools
                        and self.knowledge.allowed(n["tool"])
                    }
                )
                if hasattr(self.knowledge, "planning_view"):
                    described = self.knowledge.planning_view(used)
                else:
                    described = {
                        n: self.knowledge.catalog.describe(n)["tools"][n] for n in used
                    }
                contracts.update(described)
                report["contract_queries"].append(
                    {
                        "mode": "validation_feedback",
                        "names": used,
                        "contracts": described,
                        "scientific_call": False,
                    }
                )
                feedback = [{"rejected_plan": plan, "errors": validation["errors"]}]
            raise ValueError("No valid graph within the planning request limit")
        except Exception as error:
            report.update(
                status="failed",
                error=type(error).__name__ + ": " + str(error),
                embedding_usage=embedding_usage_since(self.knowledge.embedding, embedding_baseline),
            )
            raise PlanningFailure(report) from error
