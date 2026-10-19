"""Refresh source bindings in the single catalogue; never execute scientific tools."""

import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scitoolflow.io import atomic_json


def main():
    path = ROOT / "tools/catalog.json"
    document = json.loads(path.read_text())
    modules = {}
    for name, spec in document["tools"].items():
        binding = spec["execution"]
        file = ROOT / Path(*binding["module"].split(".")).with_suffix(".py")
        if file not in modules:
            modules[file] = {
                node.name: node
                for node in ast.parse(file.read_text()).body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
        node = modules[file][binding["function"]]
        parameters = [
            arg.arg
            for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs
        ]
        if node.args.vararg:
            parameters.append(node.args.vararg.arg)
        if node.args.kwarg:
            parameters.append(node.args.kwarg.arg)
        if parameters != [item["name"] for item in spec["parameters"]]:
            raise ValueError(
                "Signature changed; update documented contract first: " + name
            )
        spec["source"] = {
            "file": str(file.relative_to(ROOT)),
            "function": binding["function"],
            "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
        }
        spec["documentation_source"] = spec["source"]["file"]
    document["schema_version"] = "2.0"
    atomic_json(path, document)
    quality = Counter(
        item.get("description_basis", "explicit_contract")
        for spec in document["tools"].values()
        for item in spec["parameters"]
    )
    report = {
        "tools": len(document["tools"]),
        "single_catalogue": "tools/catalog.json",
        "parameter_descriptions": dict(quality),
        "scientific_functions_executed": 0,
        "source_files": len(modules),
        "descriptions_and_input_output_contracts_preserved": True,
    }
    atomic_json(ROOT / "results/reports/tool_documentation.json", report)
    print(json.dumps(report))


if __name__ == "__main__":
    main()
