"""Validate all active tool contracts, registrations, graph links and vectors."""

import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.utils.paths import bootstrap_runtime
from tools.catalog import ToolCatalog
from scripts.tools.build_graph import functionality_text, make_graph
from tools.catalog.ports import validate_ports


def main():
    bootstrap_runtime()
    from tools.runtime.dispatch import missing_resources
    from tools.runtime.environments import environment_python, tool_environment

    catalog = ToolCatalog(ROOT)
    registry = catalog.registry()
    graph = json.loads((ROOT / "tools/graph/graph_store.json").read_text())[
        "graph_dict"
    ]
    assert graph == make_graph(
        catalog
    ), "Graph contains stale, missing or unexpected relations"
    modules, results = {}, []
    graph_names = set(catalog.indexed_tools("graph"))
    embedding_names = set(catalog.indexed_tools("embedding"))
    bindings = {}
    for name, spec in catalog.tools.items():
        assert spec["name"] == name and spec["kind"] == "tool", name
        validate_ports(name, spec)
        for field in ["description", "call_signature", "output_description"]:
            assert isinstance(spec[field], str) and spec[field].strip(), (name, field)
        assert isinstance(spec["input_schema"], dict) and isinstance(
            spec["output_schema"], dict
        ), name
        Draft202012Validator.check_schema(spec["input_schema"])
        Draft202012Validator.check_schema(spec["output_schema"])
        if spec.get("output_encoding", {}).get("decoded_schema"):
            Draft202012Validator.check_schema(spec["output_encoding"]["decoded_schema"])
        assert spec["returns"] and all(
            p.get("type") and p.get("description", "").strip() for p in spec["returns"]
        ), name
        assert all(
            p.get("description", "").strip() and p.get("type")
            for p in spec["parameters"]
        ), name
        source = ROOT / spec["source"]["file"]
        if source not in modules:
            modules[source] = {
                n.name: n
                for n in ast.parse(source.read_text()).body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
        node = modules[source][spec["source"]["function"]]
        names = [
            a.arg for a in node.args.posonlyargs + node.args.args + node.args.kwonlyargs
        ]
        if node.args.vararg:
            names.append(node.args.vararg.arg)
        if node.args.kwarg:
            names.append(node.args.kwarg.arg)
        assert names == [p["name"] for p in spec["parameters"]], name
        assert set(spec["input_schema"].get("properties", {})) == set(names), name
        positional = node.args.posonlyargs + node.args.args
        defaults = (
            [None] * (len(positional) - len(node.args.defaults))
            + node.args.defaults
            + node.args.kw_defaults
        )
        for parameter, default in zip(spec["parameters"], defaults):
            assert parameter["required"] == (default is None), (
                name,
                parameter["name"],
                "required",
            )
            if default is not None:
                assert parameter.get("default") == ast.literal_eval(default), (
                    name,
                    parameter["name"],
                    "default",
                )
        assert (
            hashlib.sha256(source.read_bytes()).hexdigest() == spec["source"]["sha256"]
        ), name
        if name != "DescribeTools":
            evidence = spec["dataflow"].get("evidence", {})
            assert evidence.get("source_sha256") == spec["source"]["sha256"], (
                name,
                "dataflow source review is stale",
            )
            assert evidence.get("function") == spec["source"]["function"], (
                name,
                "dataflow binding mismatch",
            )
        binding = (spec["execution"]["module"], spec["execution"]["function"])
        assert (
            binding not in bindings
        ), f"Duplicate public execution binding: {name}/{bindings.get(binding)}"
        bindings[binding] = name
        indexed = name in graph_names
        assert (name in graph) == indexed, name
        if indexed:
            assert ["has the functionality that", spec["description"]] in graph[name]
            assert [
                "has implementation",
                spec["source"]["file"] + ":" + spec["source"]["function"],
            ] in graph[name]
            assert ["is the functionality of", name] in graph[spec["description"]]
        runtime = registry["tools"][name]
        host = runtime.get("backend") == "host"
        resources = [] if host else missing_resources(runtime)
        environment = "host" if host else tool_environment(runtime["environment"])
        python_ok = host or environment_python(environment).is_file()
        results.append(
            dict(
                tool=name,
                domain=spec["domain"],
                implementation_exists=True,
                source_signature_checked=True,
                contract_and_graph_links_valid=True,
                graph_indexed=indexed,
                embedding_indexed=name in embedding_names,
                environment=environment,
                environment_python_exists=python_ok,
                missing_resources=resources,
                retired_service=runtime.get("unavailable_service"),
                preflight_ready=python_ok
                and not resources
                and not runtime.get("unavailable_service"),
                tool_executed=False,
            )
        )
    assert not set(catalog.retired) & set(catalog.tools)
    assert not set(catalog.aliases) & set(catalog.tools)
    assert not set(catalog.aliases) & set(catalog.retired)
    for alias in catalog.aliases:
        canonical = catalog.canonical(alias)
        assert canonical in catalog.tools, alias
        if canonical in catalog.indexed_tools("graph"):
            assert ["is an alias of", canonical] in graph[alias]
    for name, record in catalog.retired.items():
        assert record["reason"] and all(
            n in catalog.tools for n in record["replacements"]
        ), name
    store = json.loads((ROOT / "tools/graph/index_store.json").read_text())
    index = json.loads(next(iter(store["index_store/data"].values()))["__data__"])
    expected = {
        functionality_text(name, spec)
        for name, spec in catalog.indexed_tools("embedding").items()
    }
    assert set(index["embedding_dict"]) == expected
    assert all(
        len(v) == 3072 and abs(sum(x * x for x in v) - 1) < 1e-6
        for v in index["embedding_dict"].values()
    )
    report = dict(
        tools=len(results),
        domain_counts=dict(Counter(r["domain"] for r in results)),
        graph_tools=len(catalog.indexed_tools("graph")),
        functionality_vectors=len(expected),
        aliases=len(catalog.aliases),
        retired_names=len(catalog.retired),
        ready_by_static_preflight=sum(r["preflight_ready"] for r in results),
        full_live_all_tool_validation=False,
        tools_detail=results,
    )
    output = ROOT / "results/reports/tool_preflight.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {k: v for k, v in report.items() if k != "tools_detail"}, ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()
