"""End-to-end role orchestration and failure boundaries, without answer access."""

from copy import deepcopy
import json
import threading
import time
import pytest
from baselines.scimas.runtime import run_scimas
from baselines.scimas.experience import Experience
from baselines.scimas.executor import Executor
from baselines.scimas.task_graph import digest
from tools import ToolCatalog, execute
from .test_knowledge_planner import public_example, decomposition, valid_plan


class Knowledge:
    def __init__(self):
        self.catalog = ToolCatalog()
        self.allowed = lambda name: True
        self.manifest = {"graph_sha256": "test"}
        self.embedding = type("Embedding", (), {"stats": {"requests": 0}})()
        self.tools = {
            name: {
                "planning": {
                    "parallel_safe": "isolated_processes_with_resource_limits",
                    "output_access": "native_fields",
                }
            }
            for name in ["MatrixInverse", "MatrixMultiply", "MatrixSVD"]
        }

    def planning_view(self, names):
        return {n: self.catalog.describe(n)["tools"][n] for n in names}

    def search(self, queries, deadline):
        return {"tools": self.planning_view(self.tools), "queries": queries}


class Client:
    model = "scripted-regression"
    backend = "injected"
    supports_response_schema = True

    def __init__(self, hook=None):
        self.hook, self.contexts, self.summary_attempts = hook, [], 0

    def request(self, messages, **kwargs):
        payload = json.loads(messages[-1]["content"])
        self.contexts.append(payload)
        if payload.get("stage") == "decompose":
            action = decomposition()
        elif payload.get("stage") == "graph":
            action = {"plan": valid_plan()}
        else:
            ctx = payload["context"]
            if "stage" in ctx:
                if ctx["stage"] == "result":
                    action = {
                        "accept": {
                            "reason": "Actual shape and numerical result checked",
                            "semantics": [],
                        }
                    }
                else:
                    action = {
                        "approve": {
                            "reason": "Matches public task",
                            "gates": [
                                n["id"]
                                for n in ctx["graph"]["plan"]["nodes"]
                                if "when" in n and ctx["stage"] == "graph"
                            ],
                        }
                    }
            elif "ready" in ctx:
                action = {
                    "dispatch": [r["id"] for r in ctx["ready"]][
                        : ctx["available_slots"]
                    ]
                }
            elif "request" in ctx:
                action = {"plan": valid_plan()}
            else:
                self.summary_attempts += 1
                outputs = {
                    v["node"]: v["output"]
                    for v in ctx["observations"].values()
                    if not v["truncated"]
                }
                action = {
                    "finish": {
                        "inverse": outputs.get("inverse", {}).get("inverse", []),
                        "product": outputs.get("check", {}).get("product", []),
                    }
                }
        if self.hook:
            action = self.hook(payload, action)
        return {
            "text": json.dumps(action),
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }


def fixture_invoke(name, args, **kwargs):
    # Exact small deterministic matrices in this fixture, not a scientific acceptance run.
    if name == "MatrixInverse":
        return {
            "status": "success",
            "output": {
                "inverse": [[0.5, 0], [0, 0.25]],
                "condition_number": 2.0,
                "residual_norm": 0.0,
            },
        }
    if name == "MatrixSVD":
        return execute(name, args, timeout=30)
    return {
        "status": "success",
        "output": {
            "product": [[1.0, 0.0], [0.0, 1.0]],
            "left_shape": [2, 2],
            "right_shape": [2, 2],
            "product_shape": [2, 2],
            "operation": "matrix_matrix",
        },
    }


def run(tmp_path, client=None, invoke=fixture_invoke, **kwargs):
    k = Knowledge()
    return run_scimas(
        public_example()["question"],
        catalog=k.catalog,
        client=client or Client(),
        invoke=invoke,
        trace_dir=tmp_path,
        case_id="EXAMPLE",
        dataset="custom",
        inputs=public_example()["inputs"],
        knowledge=k,
        answer_schema={
            "type": "object",
            "properties": {"inverse": {"type": "array"}, "product": {"type": "array"}},
            "required": ["inverse", "product"],
            "additionalProperties": False,
        },
        **kwargs,
    )


def test_full_workflow_real_tools_and_trace_integrity(tmp_path):
    from evaluation.integrity.traces import verify_trajectory
    from evaluation.integrity.resources import check_resources

    client = Client()
    result = run(tmp_path, client, invoke=execute)
    assert result["status"] == "completed", result["failure_reason"]
    assert result["final_answer"]["product"] == [[1, 0], [0, 1]]
    assert len(result["calls"]) == 2
    assert len(result["experiences"]) == 5
    assert any(c.get("context", {}).get("experience") for c in client.contexts)
    prediction = dict(result, id="EXAMPLE", completed=True)
    verify_trajectory(result, prediction, {"tools": Knowledge().catalog.tools})
    prediction.update(
        _resource_usage=result["resource_usage"],
        _execution_limits=result["limits"],
        _model_steps=sum("model" in s for s in result["steps"]),
        _think_steps=0,
        _consecutive_thinks=0,
    )
    policy = {
        "version": "task-resources.v1",
        "max_model_requests": 400,
        "task_seconds": 7200,
    }
    assert not check_resources(prediction, policy)["exceeded"]
    assert json.loads(open(result["trace_path"]).read())["status"] == "completed"


def test_bad_binding_repaired_before_scientific_call(tmp_path):
    once = []

    def hook(payload, action):
        if payload.get("stage") == "graph":
            action["plan"]["nodes"][1]["arguments"]["left"] = {
                "kind": "node",
                "node": "inverse",
                "path": ["inverse"],
            }
        ctx = payload.get("context", {})
        if ctx.get("stage") == "graph" and not once:
            once.append(True)
            return {
                "repair": {
                    "nodes": ["check"],
                    "reason": "Must multiply original matrix by inverse",
                }
            }
        return action

    result = run(tmp_path, Client(hook))
    assert result["status"] == "completed", result["failure_reason"]
    assert len(result["repairs"]) == 1
    assert result["calls"][1]["arguments"]["left"] == [[2, 0], [0, 4]]
    assert len(result["calls"]) == 2


def test_failed_call_cannot_be_accepted_by_reviewer(tmp_path):
    result = run(
        tmp_path,
        invoke=lambda *a, **k: {
            "status": "error",
            "output": None,
            "error_type": "InvalidOutput",
        },
    )
    assert result["status"] == "failed"
    assert not result["results"] and not result["pruned"]
    assert len(result["calls"]) == 1
    assert "ResultRejected" in result["failure_reason"]


def test_transient_retry_bounded(tmp_path):
    result = run(
        tmp_path,
        invoke=lambda *a, **k: {
            "status": "error",
            "output": None,
            "error_type": "Timeout",
        },
    )
    assert result["status"] == "failed" and len(result["calls"]) == 2
    assert len([s for s in result["steps"] if s["type"] == "retry"]) == 1


def test_format_correction_and_independent_final_review(tmp_path):
    once = []

    def hook(payload, action):
        if "finish" in action and not once:
            once.append(True)
            return {"finish": {"wrong_nesting": action["finish"]}}
        return action

    client = Client(hook)
    result = run(tmp_path, client)
    assert result["status"] == "completed", result["failure_reason"]
    assert result["stats"]["answer_format_errors"] == 1
    assert result["reviews"][-1]["stage"] == "final"
    assert "ground_truth" not in json.dumps(client.contexts)


def test_all_roles_share_request_budget(tmp_path):
    result = run(tmp_path, max_model_requests=4)
    assert result["status"] == "failed"
    assert result["resource_usage"]["model_requests"] == 4
    assert len([s for s in result["steps"] if "model" in s]) == 4
    assert {r["phase"] for r in result["resource_usage"]["requests"]} == {
        "planner",
        "reviewer",
        "executor",
    }


def test_semantics_must_be_actual_output_metadata(tmp_path):
    def hook(payload, action):
        if "accept" in action:
            action["accept"]["semantics"] = [
                {
                    "key": "unit",
                    "value": "eV",
                    "path": ["condition_number"],
                    "decoded": False,
                }
            ]
        return action

    result = run(tmp_path, Client(hook))
    assert result["status"] == "failed" and "not grounded" in result["failure_reason"]
    assert not result["results"]


def test_memory_is_task_local_bounded_and_invalidates():
    memory = Experience(2, 1)
    for i in range(3):
        memory.confirm("executor", "T", str(i), {"binding": "task"}, ["o1"])
    assert len(memory.entries) == 2
    assert not memory.match("executor", {"T": "0"})
    assert len(memory.match("executor", {"T": "2"})) == 1
    memory.invalidate("T", "2")
    assert not memory.match("executor", {"T": "2"})
    assert not Experience().entries


def test_executor_directories_event_order_and_cancel(tmp_path):
    from src.utils.paths import work_root
    from tools.runtime.context import CALL_CANCEL

    slow = threading.Event()
    started = threading.Event()

    def invoke(name, args, **kwargs):
        directory = work_root()
        (directory / "same_name.txt").write_text(name)
        if name == "slow":
            started.set()
            while not CALL_CANCEL.get().is_set() and not slow.wait(0.01):
                pass
        return {"status": "success", "output": {"directory": str(directory)}}

    pool = Executor(invoke, tmp_path, 2)
    try:
        pool.submit(
            {"id": "slow", "tool": "slow"},
            "one",
            {},
            parallel=True,
            files=[],
            timeout=10,
        )
        assert started.wait(2)
        pool.submit(
            {"id": "fast", "tool": "fast"},
            "two",
            {},
            parallel=True,
            files=[],
            timeout=10,
        )
        done = pool.completed(2)
        assert [r["node"] for r, _ in done] == ["fast"]
        assert next(iter(pool.running.values()))["node"] == "slow"
        pool.invalidate(["slow"])
        done = pool.completed(2)
        assert done[0][0]["stale"]
        assert len(list(tmp_path.rglob("same_name.txt"))) == 2
    finally:
        slow.set()
        pool.close()


def test_repair_retains_unaffected_results(tmp_path):
    repaired = []

    def hook(payload, action):
        if payload.get("stage") == "graph":
            # Parameter values are wrong scientifically but structurally well-formed.
            action["plan"]["nodes"][1]["arguments"]["left"] = {
                "kind": "node",
                "node": "inverse",
                "path": ["inverse"],
            }
        ctx = payload.get("context", {})
        if ctx.get("stage") == "result" and ctx.get("node") == "check" and not repaired:
            repaired.append(True)
            return {
                "repair": {
                    "nodes": ["check"],
                    "reason": "Actual product used the inverse twice",
                }
            }
        return action

    result = run(tmp_path, Client(hook), invoke=execute)
    assert result["status"] == "completed", result["failure_reason"]
    assert [c["tool"] for c in result["calls"]] == [
        "MatrixInverse",
        "MatrixMultiply",
        "MatrixMultiply",
    ]
    assert result["repairs"][0]["retained"] == ["inverse"]
    assert result["calls"][1]["output"]["product"] != [[1, 0], [0, 1]]
    assert result["final_answer"]["product"] == [[1, 0], [0, 1]]


def test_scientific_gate_prunes_only_with_successful_evidence(tmp_path):
    def hook(payload, action):
        if payload.get("stage") == "decompose":
            action["requirements"][0]["mode"] = "screen"
        if payload.get("stage") == "graph":
            action["plan"]["nodes"][1]["when"] = {
                "op": "gt",
                "left": {
                    "kind": "node",
                    "node": "inverse",
                    "path": ["condition_number"],
                },
                "right": {"kind": "literal", "value": 3},
                "evidence": "condition number exceeds 3",
            }
        if "finish" in action:
            return {"finish": {"inverse": [[0.5, 0], [0, 0.25]], "product": []}}
        return action

    k = Knowledge()
    result = run_scimas(
        "Report the inverse and its identity-product check. Only check if condition number exceeds 3.",
        catalog=k.catalog,
        knowledge=k,
        client=Client(hook),
        invoke=fixture_invoke,
        trace_dir=tmp_path,
        inputs=public_example()["inputs"],
        dataset="custom",
    )
    assert result["status"] == "completed", result["failure_reason"]
    assert len(result["calls"]) == 1
    assert result["pruned"]["check"]["reason"] == "scientific_gate_false"


def test_worker_cancellation_kills_process_group():
    import subprocess, sys
    from tools.runtime.dispatch import run_worker
    from tools.runtime.context import CALL_CANCEL

    cancelled = threading.Event()
    cancelled.set()
    token = CALL_CANCEL.set(cancelled)
    start = time.monotonic()
    try:
        with pytest.raises(subprocess.TimeoutExpired):
            run_worker(
                [sys.executable, "-c", "import time;time.sleep(60)"],
                input="",
                timeout=60,
                text=True,
            )
    finally:
        CALL_CANCEL.reset(token)
    assert time.monotonic() - start < 4


def test_runtime_expands_maps_and_reviews_concrete_nodes(tmp_path):
    def hook(payload, action):
        if payload.get("stage") == "graph":
            action = {
                "plan": {
                    "nodes": [
                        {
                            "id": "inverse",
                            "tool": "MatrixInverse",
                            "object": "matrix",
                            "purpose": "Inverse of every matrix",
                            "for_each": {
                                "kind": "task",
                                "path": ["inputs", "matrices"],
                            },
                            "arguments": {"values": {"kind": "item", "path": []}},
                        }
                    ],
                    "deliverables": [
                        {
                            "requirement": "report",
                            "nodes": ["inverse"],
                            "description": "Every inverse",
                        }
                    ],
                }
            }
        if "finish" in action:
            rows = payload["context"]["observations"].values()
            return {"finish": {"inverses": [r["output"]["inverse"] for r in rows]}}
        return action

    k = Knowledge()
    result = run_scimas(
        public_example()["question"],
        catalog=k.catalog,
        knowledge=k,
        client=Client(hook),
        invoke=execute,
        trace_dir=tmp_path,
        inputs={"matrices": [[[2, 0], [0, 4]], [[4, 0], [0, 8]]]},
        dataset="custom",
    )
    assert result["status"] == "completed", result["failure_reason"]
    assert len(result["calls"]) == 2
    assert {c["node"] for c in result["calls"]} == {"inverse__0", "inverse__1"}
    assert len(result["graphs"]) == 2
    assert len([r for r in result["reviews"] if r["stage"] == "graph"]) == 2


def test_slow_branch_does_not_block_ready_successor(tmp_path):
    slow_started = threading.Event()
    release = threading.Event()
    order = []

    def hook(payload, action):
        if payload.get("stage") == "graph":
            p = action["plan"]
            p["nodes"].append(
                {
                    "id": "svd",
                    "tool": "MatrixSVD",
                    "purpose": "Independent SVD",
                    "object": "matrix",
                    "arguments": {
                        "values": {"kind": "task", "path": ["inputs", "matrix"]}
                    },
                }
            )
            p["deliverables"][0]["nodes"].append("svd")
        return action

    def invoke(name, args, **kwargs):
        if name == "MatrixSVD":
            slow_started.set()
            assert release.wait(5), "Downstream work was blocked by unrelated branch"
            return {
                "status": "success",
                "output": {
                    "u": [[1]],
                    "vt": [[1]],
                    "singular_values": [1],
                    "reconstruction_error": 0,
                },
            }
        if name == "MatrixInverse":
            assert slow_started.wait(3)
        if name == "MatrixMultiply":
            release.set()
        order.append(name)
        return fixture_invoke(name, args, **kwargs)

    try:
        result = run(tmp_path, Client(hook), invoke=invoke)
        assert result["status"] == "completed", result["failure_reason"]
        rows = {c["tool"]: c for c in result["calls"]}
        assert (
            rows["MatrixMultiply"]["started_seconds"]
            < rows["MatrixSVD"]["finished_seconds"]
        )
    finally:
        release.set()


def test_call_budget_counts_inflight_calls(tmp_path):
    def hook(payload, action):
        if payload.get("stage") == "graph":
            action["plan"]["nodes"][1]["arguments"]["right"] = {
                "kind": "task",
                "path": ["inputs", "matrix"],
            }
        return action

    result = run(tmp_path, Client(hook), max_calls=1)
    assert (
        result["status"] == "failed"
        and "ScientificCallBudget" in result["failure_reason"]
    )
    assert len(result["calls"]) == 1


def test_repair_cannot_modify_unrelated_successful_node(tmp_path):
    def hook(payload, action):
        ctx = payload.get("context", {})
        if ctx.get("stage") == "result" and ctx["node"] == "check":
            return {"repair": {"nodes": ["check"], "reason": "Need corrected product"}}
        if "request" in ctx:
            action["plan"]["nodes"][0]["arguments"]["values"] = {
                "kind": "literal",
                "value": [[1, 0], [0, 1]],
            }
        return action

    result = run(tmp_path, Client(hook), max_model_requests=12)
    assert result["status"] == "failed"
    assert len(result["calls"]) == 2
    assert len(result["graphs"]) == 1
    assert "inverse" in result["results"]


def test_model_requested_discovery_is_a_real_non_scientific_call(tmp_path):
    described = []

    def hook(payload, action):
        if payload.get("stage") == "graph" and not described:
            described.append(True)
            return {"describe_tools": ["MatrixInverse", "MatrixMultiply"]}
        return action

    result = run(tmp_path, Client(hook), invoke=execute)
    assert result["status"] == "completed", result["failure_reason"]
    assert result["calls"][0]["tool"] == "DescribeTools"
    assert result["calls"][0]["kind"] == "discovery"
    assert (
        result["stats"]["discovery_calls"] == 1
        and result["stats"]["scientific_calls"] == 2
    )


def test_stale_result_cannot_advance_repaired_graph(tmp_path):
    gate = threading.Event()
    first = [True]
    repair_requested = []

    def hook(payload, action):
        if payload.get("stage") == "graph":
            p = action["plan"]
            p["nodes"].append(
                {
                    "id": "svd",
                    "tool": "MatrixSVD",
                    "purpose": "Independent SVD",
                    "object": "matrix",
                    "arguments": {
                        "values": {"kind": "task", "path": ["inputs", "matrix"]}
                    },
                }
            )
            p["deliverables"][0]["nodes"].append("svd")
        ctx = payload.get("context", {})
        if (
            ctx.get("stage") == "result"
            and ctx.get("node") == "inverse"
            and not repair_requested
        ):
            repair_requested.append(True)
            return {
                "repair": {
                    "nodes": ["svd"],
                    "reason": "Use explicitly bound original matrix for this branch",
                }
            }
        if "request" in ctx:
            p = deepcopy(ctx["graph"]["plan"])
            p["nodes"][2]["arguments"]["values"] = {
                "kind": "literal",
                "value": [[2, 0], [0, 4]],
            }
            return {"plan": p}
        return action

    def invoke(name, args, **kwargs):
        if name == "MatrixSVD":
            from tools.runtime.context import CALL_CANCEL

            gate.set()
            if first[0]:
                first[0] = False
                assert CALL_CANCEL.get().wait(5)
            return {
                "status": "success",
                "output": {
                    "u": [[1]],
                    "vt": [[1]],
                    "singular_values": [4, 2],
                    "reconstruction_error": 0,
                },
            }
        if name == "MatrixInverse":
            assert gate.wait(3)
        return fixture_invoke(name, args, **kwargs)

    result = run(tmp_path, Client(hook), invoke=invoke)
    assert result["status"] == "completed", result["failure_reason"]
    rows = [c for c in result["calls"] if c["tool"] == "MatrixSVD"]
    assert len(rows) == 2 and rows[0]["stale"] and not rows[1]["stale"]
    assert result["results"]["svd"]["observation_id"] == rows[1]["observation_id"]


def test_final_citations_copy_only_current_accepted_evidence(tmp_path):
    def hook(payload, action):
        if "finish" in action:
            rows = {
                v["node"]: oid for oid, v in payload["context"]["observations"].items()
            }
            return {
                "finish": {
                    "inverse": {"$observation": rows["inverse"], "field": ["inverse"]},
                    "product": {"$observation": rows["check"], "field": ["product"]},
                }
            }
        return action

    result = run(tmp_path, Client(hook))
    assert result["status"] == "completed", result["failure_reason"]
    assert result["final_answer"]["inverse"] == [[0.5, 0], [0, 0.25]]
    assert result["final_answer"]["product"] == [[1, 0], [0, 1]]


def test_failed_observation_citation_cannot_submit_answer(tmp_path):
    first = []

    def invoke(name, args, **kwargs):
        if not first:
            first.append(True)
            return {"status": "error", "output": None, "error_type": "Timeout"}
        return fixture_invoke(name, args, **kwargs)

    def hook(payload, action):
        if "finish" in action:
            action["finish"]["inverse"] = {
                "$observation": "o0001",
                "field": ["inverse"],
            }
        return action

    result = run(tmp_path, Client(hook), invoke=invoke, max_model_requests=15)
    assert result["status"] == "failed"
    assert result["stats"]["answer_format_errors"] > 0
    assert result["final_answer"] is None


def test_shared_protocol_flag_and_failure_limit(tmp_path):
    class Unguarded(Client):
        def request(self, messages, **kwargs):
            assert "response_schema" not in kwargs
            return super().request(messages, **kwargs)

    result = run(tmp_path, Unguarded(), protocol_schema_guard=False)
    assert result["status"] == "completed", result["failure_reason"]
    failed = run(
        tmp_path,
        invoke=lambda *a, **k: {
            "status": "error",
            "output": None,
            "error_type": "Timeout",
        },
        max_failures_per_action=1,
    )
    assert failed["status"] == "failed" and len(failed["calls"]) == 1
    assert "RepeatedActionFailure" in failed["failure_reason"]


def test_kg_initialization_failure_has_a_zero_request_trace(tmp_path, monkeypatch):
    from baselines.scimas import runtime

    def bad(**kwargs):
        raise ValueError("Stale graph test fixture")

    monkeypatch.setattr(runtime, "ToolKnowledge", bad)
    result = runtime.run_scimas(
        "Public question",
        catalog=ToolCatalog(),
        client=Client(),
        invoke=execute,
        trace_dir=tmp_path,
    )
    assert result["status"] == "failed" and "Stale graph" in result["failure_reason"]
    assert result["resource_usage"]["model_requests"] == 0
    assert result["embedding_usage"] is None
    assert json.loads(open(result["trace_path"]).read())["status"] == "failed"


def test_role_protocol_errors_are_recorded(tmp_path):
    class Malformed(Client):
        once = False

        def request(self, messages, **kwargs):
            ctx = json.loads(messages[-1]["content"]).get("context", {})
            if ctx.get("stage") == "graph" and not self.once:
                self.once = True
                return {
                    "text": "{",
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                }
            return super().request(messages, **kwargs)

    result = run(tmp_path, Malformed())
    assert result["status"] == "completed", result["failure_reason"]
    assert result["stats"]["protocol_errors"] == 1
    assert len([s for s in result["steps"] if s.get("protocol_errors")]) == 1


def test_repaired_observations_are_explicitly_labeled_in_role_context(tmp_path):
    repaired = []
    seen = []

    def hook(payload, action):
        if payload.get("stage") == "graph":
            action["plan"]["nodes"][1]["arguments"]["left"] = {
                "kind": "node",
                "node": "inverse",
                "path": ["inverse"],
            }
        ctx = payload.get("context", {})
        if ctx.get("stage") == "result" and ctx.get("node") == "check" and not repaired:
            repaired.append(True)
            return {
                "repair": {
                    "nodes": ["check"],
                    "reason": "Correct original left operand",
                }
            }
        if "finish" in action:
            seen.append(ctx)
        return action

    result = run(tmp_path, Client(hook), invoke=execute)
    assert result["status"] == "completed", result["failure_reason"]
    evidence = seen[-1]["observations"]
    assert (
        evidence["o0002"]["stale"]
        and not evidence["o0002"]["accepted_for_current_graph"]
    )
    assert (
        evidence["o0003"]["accepted_for_current_graph"]
        and not evidence["o0003"]["stale"]
    )
    assert seen[-1]["accepted_observations"]["check"] == "o0003"


def test_gate_approval_contract_distinguishes_conditions_from_all_nodes(tmp_path):
    once = []

    def hook(payload, action):
        ctx = payload.get("context", {})
        if ctx.get("stage") == "graph" and not once:
            once.append(True)
            action["approve"]["gates"] = ["inverse", "check"]
        return action

    result = run(tmp_path, Client(hook))
    assert result["status"] == "completed", result["failure_reason"]
    assert result["stats"]["protocol_errors"] == 1
    assert result["reviews"][0]["decision"]["approve"]["gates"] == []


def test_all_roles_receive_the_same_verified_public_attachment(tmp_path):
    file = ToolCatalog().root / "tasks/full/assets/study_original_FLOW-0481.json"
    client = Client()
    result = run(tmp_path, client, files=[str(file)])
    assert result["status"] == "completed", result["failure_reason"]
    contexts = [row["context"] for row in client.contexts if "context" in row]
    assert contexts and all(
        row["public_assets"][0]["path"] == str(file) for row in contexts
    )
    assert all(
        "independent_proper_imputation_records" in row["public_assets"][0]["text"]
        for row in contexts
    )
    assert all(row["public_assets"][0]["sha256"] for row in contexts)
