from copy import deepcopy
import json
import pytest
from .test_graph import catalog, graph, node, ref, gate, lit, result, check
from .test_knowledge_planner import (
    ScriptedClient,
    FixedKnowledge,
    public_example,
    decomposition,
    valid_plan,
)
from baselines.scimas.task_graph import TaskGraph
from baselines.scimas.planner import Planner


def test_saved_graph_rejects_other_task_or_namespace(catalog):
    g = graph(catalog, [node("a")])
    assert TaskGraph.load(g.document(), g.task, catalog).identity == g.identity
    task = {**g.task, "inputs": {"different": 2}}
    with pytest.raises(ValueError, match="identity"):
        TaskGraph.load(g.document(), task, catalog)
    altered = g.document()
    altered["dataset"] = "foreign"
    with pytest.raises(ValueError):
        TaskGraph.load(altered, g.task, catalog)


def test_output_checks_cannot_fetch_remote_schema(catalog):
    g = graph(
        catalog,
        [
            node(
                "a",
                checks=[
                    {
                        "path": ["value"],
                        "schema": {"$ref": "https://example.invalid/check"},
                    }
                ],
            )
        ],
    )
    assert "self-contained" in str(check(g, catalog)["errors"])


def test_old_gate_approval_does_not_authorize_modified_condition(catalog):
    g = graph(catalog, [node("a"), node("b", ref("a"), when=gate())], mode="screen")
    approval = {"b": g.node_identity("b")}
    evidence = {"a": result(g, catalog, "a", 2)}
    replacement = deepcopy(g.plan)
    replacement["nodes"][1]["when"]["op"] = "lt"
    revised, _ = g.revise(replacement, catalog)
    assert revised.condition_state("b", evidence, approved_gates=approval) is None


def test_three_valued_logic_and_equality(catalog):
    g = graph(
        catalog,
        [
            node("a"),
            node(
                "b",
                ref("a"),
                when={"op": "all", "args": [gate(), {**gate(), "left": lit(4)}]},
            ),
        ],
        mode="screen",
    )
    assert (
        g.condition_state("b", {}, approved_gates={"b": g.node_identity("b")}) is False
    )
    g.plan["nodes"][1]["when"] = {
        "op": "eq",
        "left": lit(True),
        "right": lit(1),
        "evidence": "Report result",
    }
    assert (
        g.condition_state("b", {}, approved_gates={"b": g.node_identity("b")}) is False
    )


def test_item_outside_template_and_invalid_collect(catalog):
    g = graph(catalog, [node("a", {"kind": "item", "path": []})])
    assert "outside" in str(check(g, catalog)["errors"])
    g = graph(
        catalog,
        [node("a"), node("b", {"kind": "collect", "node": "a", "path": ["value"]})],
    )
    assert "unexpanded template" in str(check(g, catalog)["errors"])


def test_binding_list_provenance_cannot_be_missing(catalog):
    n = {
        "id": "array",
        "tool": "Array",
        "purpose": "array",
        "object": "panel",
        "arguments": {
            "values": {"kind": "list", "items": [], "provenance": [ref("missing")]}
        },
    }
    g = graph(catalog, [n])
    assert not check(g, catalog)["valid"]


def test_format_feedback_bounded_and_answer_free():
    client = ScriptedClient(
        [{"incorrect": "format"}, decomposition(), {"plan": valid_plan()}]
    )
    report = Planner(FixedKnowledge(), client).plan(public_example(), dataset="custom")
    assert report["status"] == "planned" and len(report["steps"]) == 3
    assert report["steps"][0]["protocol_errors"]
    assert "must not be seen" not in json.dumps(client.calls)


def test_requirement_quote_gets_correction_feedback():
    bad = decomposition()
    bad["requirements"][0]["evidence"] = "Report ... inverse"
    client = ScriptedClient([bad, decomposition(), {"plan": valid_plan()}])
    report = Planner(FixedKnowledge(), client).plan(public_example(), dataset="custom")
    assert report["status"] == "planned" and report["steps"][0]["grounding_errors"]


def test_demand_driven_contract_lookup(kg=None):
    from .test_knowledge_planner import EchoEmbedding
    from baselines.scimas.knowledge import ToolKnowledge

    knowledge = ToolKnowledge()
    knowledge.embedding = EchoEmbedding(knowledge.vectors["MatrixInverse"])
    client = ScriptedClient(
        [
            decomposition(),
            {"describe_tools": ["MatrixInverse", "MatrixMultiply"]},
            {"plan": valid_plan()},
        ]
    )
    report = Planner(knowledge, client).plan(public_example(), dataset="custom")
    assert report["status"] == "planned"
    assert len(report["contract_queries"]) == 1
    first = json.loads(report["steps"][1]["messages"][1]["content"])["instructions"]
    assert first["contracts"] == {}
    assert "input_schema" not in json.dumps(first["candidates"])
    last = json.loads(report["steps"][2]["messages"][1]["content"])["instructions"]
    assert last["contracts"]["MatrixMultiply"]["contract"]["input_schema"]


def test_grammar_subset_keeps_full_uniqueness_validation(catalog):
    from baselines.scimas.schema import PLAN_SCHEMA, decoding_schema
    from tools.runtime.contracts import contract_errors

    g = graph(catalog, [node("a")])
    g.plan["deliverables"][0]["nodes"] = ["a", "a"]
    assert contract_errors(g.plan, PLAN_SCHEMA)
    assert not contract_errors(g.plan, decoding_schema(PLAN_SCHEMA))
    assert not check(g, catalog)["valid"]
