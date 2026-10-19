"""Inspect every implementation/contract/link/resource without scientific execution."""

import ast
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scitoolflow.paths import bootstrap_runtime


def main():
    bootstrap_runtime()
    from tools.runtime.dispatch import missing_resources
    from tools.runtime.environments import environment_python, tool_environment

    catalog = json.loads((ROOT / "tools/catalog.json").read_text())
    from tools.catalog import ToolCatalog

    registry = ToolCatalog(ROOT).registry()
    sources = {name: spec["source"] for name, spec in catalog["tools"].items()}
    graph = json.loads((ROOT / "tools/graph/graph_store.json").read_text())[
        "graph_dict"
    ]
    results = []
    modules = {}
    for name, spec in catalog["tools"].items():
        source = ROOT / sources[name]["file"]
        if source not in modules:
            modules[source] = {
                n.name: n
                for n in ast.parse(source.read_text()).body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
        assert sources[name]["function"] in modules[source]
        node = modules[source][sources[name]["function"]]
        declared = [
            a.arg for a in node.args.posonlyargs + node.args.args + node.args.kwonlyargs
        ]
        if node.args.vararg:
            declared.append(node.args.vararg.arg)
        if node.args.kwarg:
            declared.append(node.args.kwarg.arg)
        assert declared == [p["name"] for p in spec["parameters"]], name
        assert (
            hashlib.sha256(source.read_bytes()).hexdigest() == sources[name]["sha256"]
        )
        assert ["has the functionality that", spec["description"]] in graph[name]
        assert [
            "has implementation",
            sources[name]["file"] + ":" + sources[name]["function"],
        ] in graph[name]
        assert ["is documented at", "tools/catalog.json#/tools/" + name] in graph[name]
        assert ["is the functionality of", name] in graph[spec["description"]]
        for key, relation, reverse in [
            ("input_schema", "has input schema", "is input schema of"),
            ("output_schema", "has output schema", "is output schema of"),
            (
                "parameters",
                "has parameter documentation",
                "is parameter documentation of",
            ),
            ("returns", "has return documentation", "is return documentation of"),
        ]:
            value = json.dumps(spec[key], ensure_ascii=False, sort_keys=True)
            assert [relation, value] in graph[name] and [reverse, name] in graph[value]
        runtime = registry["tools"][name]
        resources = [] if spec["kind"] == "discovery" else missing_resources(runtime)
        environment = (
            "host"
            if spec["kind"] == "discovery"
            else tool_environment(runtime["environment"])
        )
        python_ok = environment == "host" or environment_python(environment).is_file()
        results.append(
            {
                "tool": name,
                "kind": spec["kind"],
                "implementation_exists": True,
                "source_signature_checked": True,
                "contract_and_graph_links_valid": True,
                "environment": environment,
                "environment_python_exists": python_ok,
                "missing_resources": resources,
                "retired_service": runtime.get("unavailable_service"),
                "preflight_ready": python_ok
                and not resources
                and not runtime.get("unavailable_service"),
                "scientific_tool_executed": False,
            }
        )
    for alias, canonical in catalog["aliases"].items():
        assert (
            canonical in catalog["tools"]
            and ["is an alias of", canonical] in graph[alias]
            and ["has alias", alias] in graph[canonical]
        )
    vector_store = json.loads((ROOT / "tools/graph/index_store.json").read_text())
    index = json.loads(
        next(iter(vector_store["index_store/data"].values()))["__data__"]
    )
    expected = {
        str((name, "has the functionality that", spec["description"]))
        for name, spec in catalog["tools"].items()
        if spec["kind"] == "scientific"
    }
    assert set(index["embedding_dict"]) == expected
    assert all(
        len(v) == 3072 and abs(sum(x * x for x in v) - 1) < 1e-6
        for v in index["embedding_dict"].values()
    )
    report = {
        "tools": len(results),
        "scientific_tools": 546,
        "discovery_tools": 1,
        "alias_links": len(catalog["aliases"]),
        "ready_by_static_preflight": sum(r["preflight_ready"] for r in results),
        "functionality_vectors": len(expected),
        "full_live_all_tool_validation": False,
        "tools_detail": results,
    }
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
