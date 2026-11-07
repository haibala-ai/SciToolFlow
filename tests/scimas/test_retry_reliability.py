"""Regressions for data bindings, disputed reviews and role-channel confusion."""
import ast
import json

import pytest

from baselines.scimas.task_graph import node_dependencies
from baselines.scimas.validation import validate_graph
from .test_graph import catalog, graph, node, lit, ref, result
from .test_runtime import run, Client, fixture_invoke


def code_graph(catalog, *, value=None, name="values"):
    catalog.tools["ExecuteNumericalCode"] = {
        "input_schema": {"type": "object", "properties": {"code": {"type": "string"}},
                         "required": ["code"], "additionalProperties": False},
        "output_schema": {"type": "object"},
    }
    source = node("source", lit(value if value is not None else 7))
    calc = {"id": "calc", "tool": "ExecuteNumericalCode", "purpose": "Compute from actual data",
            "object": "current source", "arguments": {"code": {
                "kind": "python_code", "code": "print(values)",
                "inputs": {name: ref("source")}}}}
    return graph(catalog, [source, calc])


def test_code_inputs_are_real_edges_and_safely_quoted(catalog):
    g = code_graph(catalog)
    assert validate_graph(g, catalog, allowed=lambda _: True)["valid"]
    assert node_dependencies(g.node("calc"))[0] == {"source"}
    evidence = {"source": result(g, catalog, "source", 7)}
    assert g.arguments("calc", evidence, catalog)["code"] == "values = 7\nprint(values)"
    # Quoting a hostile string must yield literal data, never extra statements.
    payload = "x'\nraise RuntimeError('not data')\n#"
    binding = {"kind": "python_code", "code": "print(values)",
               "inputs": {"values": lit(payload)}}
    rendered = g.resolve(binding, {})
    tree = ast.parse(rendered)
    assert len(tree.body) == 2
    assert ast.literal_eval(tree.body[0].value) == payload


def test_code_inputs_reject_stale_evidence_and_oversize_data(catalog):
    g = code_graph(catalog)
    evidence = {"source": result(g, catalog, "source", 7)}
    evidence["source"]["node_sha256"] = "stale"
    with pytest.raises(ValueError, match="stale"):
        g.arguments("calc", evidence, catalog)
    with pytest.raises(ValueError, match="12000"):
        g.resolve({"kind": "python_code", "code": "print(values)",
                   "inputs": {"values": lit("x"*12000)}}, {})


def test_code_binding_names_and_receiving_parameter_are_validated(catalog):
    g = code_graph(catalog, name="class")
    assert not validate_graph(g, catalog, allowed=lambda _: True)["valid"]
    g = graph(catalog, [node("a", {"kind": "python_code", "code": "print(x)",
                                   "inputs": {"x": lit(1)}})])
    report = validate_graph(g, catalog, allowed=lambda _: True)
    assert not report["valid"]
    assert any("only an ExecuteNumericalCode.code" in e for e in report["errors"])


def test_false_review_can_be_withdrawn_without_faking_a_repair(tmp_path):
    seen = {"requested": False, "reconsidered": 0}
    def hook(payload, action):
        ctx = payload.get("context", {})
        if "counterevidence" in ctx:
            seen["reconsidered"] += 1
            return {"accept": {"reason": "Existing output satisfies the requested method", "semantics": []}}
        if ctx.get("stage") == "result" and not seen["requested"]:
            seen["requested"] = True
            return {"repair": {"nodes": [ctx["node"]], "reason": "Unfounded expected-value claim"}}
        if "request" in ctx:
            return {"stop": "The observation is correct under the required method; the expectation is unsupported"}
        return action
    trace = run(tmp_path, client=Client(hook))
    assert trace["status"] == "completed", trace.get("failure_reason")
    assert seen["reconsidered"] == 1
    assert trace["repair_attempts"][0]["status"] == "not_needed_after_reconsideration"
    assert trace["repairs"] == []


def test_disagreement_does_not_bypass_deterministic_failure(tmp_path):
    seen = {"counter": 0}
    def hook(payload, action):
        ctx = payload.get("context", {})
        if "counterevidence" in ctx:seen["counter"] += 1
        if ctx.get("stage") == "result":
            return {"repair": {"nodes": [ctx["node"]], "reason": "Wrong numerical result"}}
        if "request" in ctx:return {"stop": "I disagree"}
        return action
    def invoke(name, arguments, **kw):
        response = fixture_invoke(name, arguments, **kw)
        if name == "MatrixInverse":response["output"].pop("inverse")
        return response
    trace = run(tmp_path, client=Client(hook), invoke=invoke)
    assert trace["status"] == "failed"
    assert seen["counter"] == 0


def test_executor_answer_in_stop_gets_feedback_instead_of_submission(tmp_path):
    seen = {"sent": False, "feedback": False}
    def hook(payload, action):
        ctx = payload.get("context", {})
        if "ready" in ctx:
            if not seen["sent"]:
                seen["sent"] = True
                return {"stop": json.dumps({"inverse": [], "product": []})}
            seen["feedback"] |= any("protocol_error" in row for row in ctx.get("feedback", []))
        return action
    trace = run(tmp_path, client=Client(hook))
    assert trace["status"] == "completed", trace.get("failure_reason")
    assert seen["feedback"]
