from copy import deepcopy
from types import SimpleNamespace
import pytest
from baselines.scimas.task_graph import TaskGraph, digest
from baselines.scimas.validation import validate_graph


def spec(inputs, output):
    return {
        "input_schema": {
            "type": "object",
            "properties": inputs,
            "required": list(inputs),
            "additionalProperties": False,
        },
        "output_schema": output,
        "output_encoding": {"decoded_type": "object"},
    }


@pytest.fixture
def catalog():
    number = {"type": "number"}
    return SimpleNamespace(
        tools={
            "Produce": spec(
                {"value": number},
                {
                    "type": "object",
                    "properties": {"value": number},
                    "required": ["value"],
                },
            ),
            "Consume": spec(
                {"value": number},
                {
                    "type": "object",
                    "properties": {"value": number},
                    "required": ["value"],
                },
            ),
            "Array": spec(
                {"values": {"type": "array", "items": number}},
                {
                    "type": "object",
                    "properties": {"values": {"type": "array", "items": number}},
                    "required": ["values"],
                },
            ),
            "Text": spec({"value": number}, {"type": "string"}),
        }
    )


def lit(value):
    return {"kind": "literal", "value": value}


def ref(node, path=None, **kw):
    return {"kind": "node", "node": node, "path": path or ["value"], **kw}


def node(nid, binding=None, tool="Produce", **kw):
    return {
        "id": nid,
        "tool": tool,
        "purpose": "Test binding",
        "object": "candidate",
        "arguments": {"value": binding or lit(2)},
        **kw,
    }


def requirement(mode="complete"):
    return [
        {
            "id": "result",
            "description": "Report result",
            "evidence": "Report result",
            "mode": mode,
        }
    ]


def graph(catalog, nodes, outputs=None, mode="complete", inputs=None):
    return TaskGraph.create(
        {
            "id": "case",
            "question": "Report result; require value <= 3.",
            "inputs": inputs or {},
        },
        requirement(mode),
        {
            "nodes": nodes,
            "deliverables": [
                {
                    "requirement": "result",
                    "nodes": outputs or [nodes[-1]["id"]],
                    "description": "Evidence",
                }
            ],
        },
        catalog,
        "custom",
    )


def check(g, catalog):
    return validate_graph(g, catalog, allowed=lambda n: True)


def gate(left=None):
    return {
        "op": "le",
        "left": left or ref("a"),
        "right": lit(3),
        "evidence": "require value <= 3",
    }


def result(g, catalog, nid, value):
    return g.accept_result(
        nid, {"status": "success", "output": {"value": value}}, catalog
    )


def test_valid_dag_shared_predecessor(catalog):
    g = graph(
        catalog, [node("a"), node("b", ref("a")), node("c", ref("a"))], ["b", "c"]
    )
    report = check(g, catalog)
    assert report["valid"], report
    assert report["data_edges"] == [["a", "b"], ["a", "c"]]
    assert g.ready({}, catalog) == ["a"]
    evidence = {"a": result(g, catalog, "a", 2)}
    assert g.ready(evidence, catalog) == ["b", "c"]
    assert g.arguments("b", evidence, catalog) == {"value": 2}


@pytest.mark.parametrize(
    "mutation,expected",
    [
        (lambda p: p["nodes"].append(deepcopy(p["nodes"][0])), "Duplicate"),
        (
            lambda p: p["nodes"][1]["arguments"].update(extra=lit(1)),
            "unknown tool arguments",
        ),
        (lambda p: p["nodes"][1].update(arguments={}), "missing required"),
        (lambda p: p["nodes"][1]["arguments"].update(value=ref("missing")), "dangling"),
        (
            lambda p: p["nodes"][1]["arguments"].update(value=ref("a", ["invented"])),
            "not declared",
        ),
        (lambda p: p["nodes"][0]["arguments"].update(value=lit(True)), "Incompatible"),
        (lambda p: p["nodes"][0]["arguments"].update(value=ref("b")), "cycle"),
        (
            lambda p: p["deliverables"][0].update(requirement="invented"),
            "cover exactly",
        ),
        (lambda p: p["nodes"][1].update(tool="RetiredTool"), "unknown, retired"),
    ],
)
def test_reject_bad_graphs(catalog, mutation, expected):
    g = graph(catalog, [node("a"), node("b", ref("a"))])
    mutation(g.plan)
    report = check(g, catalog)
    assert not report["valid"]
    assert expected in str(report["errors"])


def test_union_of_control_and_data_is_acyclic(catalog):
    g = graph(
        catalog, [node("a", when=gate(ref("b"))), node("b", ref("a"))], mode="screen"
    )
    assert "cycle" in str(check(g, catalog)["errors"])


def test_full_report_cannot_be_screened(catalog):
    g = graph(catalog, [node("a"), node("b", ref("a"), when=gate())])
    assert "Complete-report" in str(check(g, catalog)["errors"])


def test_gate_needs_review_and_failure_is_unknown(catalog):
    g = graph(catalog, [node("a"), node("b", ref("a"), when=gate())], mode="screen")
    assert check(g, catalog)["valid"]
    good = {"a": result(g, catalog, "a", 2)}
    assert g.condition_state("b", good) is None
    assert g.ready(good, catalog) == []
    assert (
        g.condition_state("b", good, approved_gates={"b": g.node_identity("b")}) is True
    )
    bad = {"a": {"status": "error", "output": {"value": 999}}}
    assert (
        g.condition_state("b", bad, approved_gates={"b": g.node_identity("b")}) is None
    )
    negative = {"a": result(g, catalog, "a", 4)}
    assert (
        g.condition_state("b", negative, approved_gates={"b": g.node_identity("b")})
        is False
    )


def test_semantics_not_inferred_from_plan_claim(catalog):
    g = graph(
        catalog,
        [
            node("a", semantics={"unit": "eV"}),
            node("b", ref("a", expect={"unit": "eV"})),
        ],
    )
    evidence = {"a": result(g, catalog, "a", 2)}
    with pytest.raises(ValueError, match="semantics"):
        g.arguments("b", evidence, catalog)
    evidence["a"] = g.accept_result(
        "a",
        {"status": "success", "output": {"value": 2}},
        catalog,
        semantics={"unit": "eV"},
    )
    assert g.arguments("b", evidence, catalog)["value"] == 2


def test_reject_failed_and_invalid_output(catalog):
    g = graph(catalog, [node("a")])
    for response in [
        {"status": "error", "output": {"value": 1}},
        {"status": "success", "output": {"value": float("nan")}},
        {"status": "success", "output": {}},
        {"status": "success", "output": {"value": True}},
    ]:
        with pytest.raises(ValueError):
            g.accept_result("a", response, catalog)


def test_json_decode_and_text_field_boundaries(catalog):
    catalog.tools["Text"]["output_encoding"] = {"decoded_type": "text"}
    g = graph(catalog, [node("a", tool="Text"), node("b", ref("a"))])
    assert not check(g, catalog)["valid"]
    g.plan["nodes"][1]["arguments"]["value"] = ref("a", decoded=True)
    assert "decoding" in str(check(g, catalog)["errors"])
    catalog.tools["Text"]["output_encoding"] = {
        "decoded_type": "json_object",
        "decoded_schema": catalog.tools["Produce"]["output_schema"],
    }
    g = graph(catalog, [node("a", tool="Text"), node("b", ref("a", decoded=True))])
    assert check(g, catalog)["valid"]
    evidence = {
        "a": g.accept_result(
            "a", {"status": "success", "output": '{"value": 7}'}, catalog
        )
    }
    assert g.arguments("b", evidence, catalog) == {"value": 7}


def test_revision_invalidation_and_safe_reuse(catalog):
    g = graph(catalog, [node("a"), node("b", ref("a")), node("c")], ["b", "c"])
    evidence = {nid: result(g, catalog, nid, 2) for nid in ["a", "b", "c"]}
    replacement = deepcopy(g.plan)
    replacement["nodes"][0]["arguments"]["value"] = lit(8)
    revised, change = g.revise(replacement, catalog)
    assert change == {"changed": ["a"], "invalidate": ["a", "b"]}
    assert revised.version == 2 and revised.parent == g.identity
    assert revised.node_identity("c") == g.node_identity("c")
    with pytest.raises(ValueError, match="stale"):
        revised.arguments("b", evidence, catalog)
    assert revised.ready(evidence, catalog) == ["a"]
    assert g.plan["nodes"][0]["arguments"]["value"] == lit(2)
    replacement["nodes"][0]["arguments"]["value"] = ref("b")
    with pytest.raises(ValueError, match="cycle"):
        g.revise(replacement, catalog)


def test_stale_contract_rejected(catalog):
    g = graph(catalog, [node("a")])
    catalog.tools["Produce"]["output_schema"]["description"] = "changed"
    assert "stale" in str(check(g, catalog)["errors"])
    with pytest.raises(ValueError, match="changed"):
        g.arguments("a", {}, catalog)


def template_graph(catalog):
    first = {
        "id": "source",
        "tool": "Array",
        "purpose": "Get candidates",
        "object": "panel",
        "arguments": {"values": lit([2, 3])},
    }
    template = node(
        "mapped", {"kind": "item", "path": []}, for_each=ref("source", ["values"])
    )
    collect = {
        "id": "joined",
        "tool": "Array",
        "purpose": "Join evidence",
        "object": "panel",
        "arguments": {
            "values": {"kind": "collect", "node": "mapped", "path": ["value"]}
        },
    }
    return graph(catalog, [first, template, collect])


def test_template_expansion_preserves_dependencies_and_order(catalog):
    g = template_graph(catalog)
    assert check(g, catalog)["valid"]
    evidence = {
        "source": g.accept_result(
            "source", {"status": "success", "output": {"values": [2, 3]}}, catalog
        )
    }
    expanded, change = g.expand("mapped", evidence, catalog)
    assert check(expanded, catalog)["valid"]
    assert expanded.ready(evidence, catalog) == ["mapped__0", "mapped__1"]
    for nid in ["mapped__0", "mapped__1"]:
        v = expanded.arguments(nid, evidence, catalog)["value"]
        evidence[nid] = result(expanded, catalog, nid, v)
    assert expanded.arguments("joined", evidence, catalog) == {"values": [2, 3]}
    with pytest.raises(ValueError, match="limit"):
        g.expand("mapped", evidence, catalog, max_items=1)


def test_empty_dynamic_candidates_are_not_fabricated(catalog):
    g = template_graph(catalog)
    evidence = {
        "source": g.accept_result(
            "source", {"status": "success", "output": {"values": []}}, catalog
        )
    }
    expanded, _ = g.expand("mapped", evidence, catalog)
    assert expanded.arguments("joined", evidence, catalog) == {"values": []}
    assert all(not n["id"].startswith("mapped") for n in expanded.plan["nodes"])


def test_unknown_gate_values_and_numeric_boolean(catalog):
    g = graph(
        catalog,
        [
            node("a"),
            node(
                "b",
                ref("a"),
                when={"op": "any", "args": [gate(), {**gate(), "left": lit(5)}]},
            ),
        ],
        mode="screen",
    )
    assert (
        g.condition_state("b", {}, approved_gates={"b": g.node_identity("b")}) is None
    )
    g.plan["nodes"][1]["when"] = {**gate(), "left": lit(True)}
    assert not check(g, catalog)["valid"]


def test_no_hidden_task_fields(catalog):
    g = TaskGraph.create(
        {"id": "test", "question": "Report result", "inputs": {}, "gold": "secret"},
        requirement(),
        {
            "nodes": [node("a", {"kind": "task", "path": ["gold"]})],
            "deliverables": [
                {"requirement": "result", "nodes": ["a"], "description": "out"}
            ],
        },
        catalog,
        "custom",
    )
    assert "gold" not in g.task
    assert not check(g, catalog)["valid"]


def dynamic_document_graph(catalog, *, mapped=False):
    catalog.tools["Document"] = spec(
        {"value": {"type": "number"}},
        {"type": "object", "properties": {"document": {}}, "required": ["document"]},
    )
    source = node("read", tool="Document")
    if mapped:
        consumer = node(
            "use",
            {"kind": "item", "path": ["score"]},
            tool="Consume",
            for_each=ref("read", ["document", "records"]),
        )
    else:
        consumer = node("use", ref("read", ["document", "score"]), tool="Consume")
    return graph(catalog, [source, consumer])


def test_dynamic_document_field_requires_actual_value_and_target_contract(catalog):
    g = dynamic_document_graph(catalog)
    report = check(g, catalog)
    assert report["valid"], report
    for document in [{"score": 7}, {}, {"score": "wrong"}]:
        evidence = {
            "read": g.accept_result(
                "read", {"status": "success", "output": {"document": document}}, catalog
            )
        }
        if document == {"score": 7}:
            assert g.arguments("use", evidence, catalog) == {"value": 7}
        else:
            with pytest.raises((ValueError, KeyError)):
                g.arguments("use", evidence, catalog)


def test_dynamic_document_array_checked_at_expansion(catalog):
    g = dynamic_document_graph(catalog, mapped=True)
    report = check(g, catalog)
    assert report["valid"], report
    assert any(
        x["check"] == "actual_array_and_bounded_map_expansion"
        for x in report["runtime_obligations"]
    )
    evidence = {
        "read": g.accept_result(
            "read",
            {
                "status": "success",
                "output": {"document": {"records": [{"score": 3}, {"score": 5}]}},
            },
            catalog,
        )
    }
    expanded, _ = g.expand("use", evidence, catalog)
    assert check(expanded, catalog)["valid"]
    assert expanded.arguments("use__0", evidence, catalog) == {"value": 3}
    assert expanded.arguments("use__1", evidence, catalog) == {"value": 5}
    for document in [{}, {"records": "not-an-array"}, {"records": {"score": 3}}]:
        invalid = {
            "read": g.accept_result(
                "read", {"status": "success", "output": {"document": document}}, catalog
            )
        }
        with pytest.raises((KeyError, ValueError)):
            g.expand("use", invalid, catalog)


def test_dynamic_paths_do_not_open_typed_closed_or_scalar_outputs():
    from baselines.scimas.validation import path_schema

    assert (
        path_schema(
            {"type": "object", "additionalProperties": True}, ["runtime", "value"]
        )
        == {}
    )
    for schema in [
        {"type": "number"},
        {"type": "string"},
        {"type": "object", "additionalProperties": False},
        {"type": "object", "properties": {"known": {"type": "number"}}},
    ]:
        with pytest.raises(ValueError):
            path_schema(schema, ["undeclared"])


@pytest.mark.parametrize(
    "first_id,second_id", [("mapped", "independent"), ("independent", "mapped")]
)
def test_expanding_one_map_preserves_other_map_items(catalog, first_id, second_id):
    original = template_graph(catalog)
    plan = deepcopy(original.plan)
    plan["nodes"].insert(
        2,
        node(
            "independent",
            {"kind": "item", "path": []},
            for_each={"kind": "task", "path": ["inputs", "other"]},
        ),
    )
    plan["deliverables"][0]["nodes"].append("independent")
    g = graph(
        catalog,
        plan["nodes"],
        plan["deliverables"][0]["nodes"],
        inputs={"other": [7, 11]},
    )
    assert check(g, catalog)["valid"]
    evidence = {
        "source": g.accept_result(
            "source", {"status": "success", "output": {"values": [2, 3]}}, catalog
        )
    }
    expanded, _ = g.expand(first_id, evidence, catalog)
    assert expanded.node(second_id) == g.node(second_id)
    assert check(expanded, catalog)["valid"]
    expanded, _ = expanded.expand(second_id, evidence, catalog)
    assert check(expanded, catalog)["valid"]
    for name, values in [("mapped", [2, 3]), ("independent", [7, 11])]:
        assert [
            expanded.arguments(name + "__" + str(i), evidence, catalog)["value"]
            for i in range(2)
        ] == values
