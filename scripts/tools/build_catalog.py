"""Refresh source bindings in the single catalogue; never execute scientific tools."""

import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.utils.io import atomic_json


def write_implementation_index(document):
    """Keep the human-readable source index derived from the canonical bindings."""
    bindings = {}
    for name, spec in document["tools"].items():
        bindings.setdefault(spec["source"]["file"], []).append(name)
    base = ROOT / "tools/implementations"
    lines = [
        "# 科学实现模块索引",
        "",
        "公开绑定来自当前唯一catalog；未直接注册的模块为共享依赖或既有内部适配，不因此自动视为可调用的公开工具。名称和输入输出以catalog为准。",
        "",
    ]
    for folder in (
        "",
        "chemistry",
        "materials",
        "biology",
        "machine_learning",
        "general",
        "shared",
    ):
        lines.extend(
            [
                "## " + (folder or "跨领域适配"),
                "",
                "| 模块 | 公开工具／辅助职责 |",
                "| --- | --- |",
            ]
        )
        for path in sorted((base / folder).glob("*.py")):
            if path.name == "__init__.py":
                continue
            names = sorted(bindings.get(str(path.relative_to(ROOT)), []))
            doc = (
                ast.get_docstring(ast.parse(path.read_text()))
                or "辅助实现；由上层模块导入。"
            )
            summary = (
                ", ".join("`" + name + "`" for name in names)
                if names
                else " ".join(doc.split())[:180].replace("|", "／")
            )
            lines.append(f"| [{path.name}]({path.relative_to(base)}) | {summary} |")
        lines.append("")
    (base / "INDEX.md").write_text("\n".join(lines) + "\n")


def main():
    path = ROOT / "tools/catalog/catalog.json"
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
        positional = node.args.posonlyargs + node.args.args
        defaults = (
            [None] * (len(positional) - len(node.args.defaults))
            + node.args.defaults
            + node.args.kw_defaults
        )
        for parameter, default_node in zip(spec["parameters"], defaults):
            if parameter["required"] != (default_node is None):
                raise ValueError(
                    "Required-argument contract changed: "
                    + name
                    + "."
                    + parameter["name"]
                )
            if default_node is None:
                continue
            default = ast.literal_eval(default_node)
            parameter["default"] = default
            prop = spec["input_schema"]["properties"][parameter["name"]]
            if default is None and not Draft202012Validator(prop).is_valid(None):
                description = prop.get("description", parameter["description"])
                prop = {
                    "anyOf": [
                        {
                            k: v
                            for k, v in prop.items()
                            if k not in {"description", "default"}
                        },
                        {"type": "null"},
                    ],
                    "description": description,
                }
                spec["input_schema"]["properties"][parameter["name"]] = prop
            prop["default"] = default
            parameter["json_schema"] = {
                k: v for k, v in prop.items() if k != "description"
            }
        spec["source"] = {
            "file": str(file.relative_to(ROOT)),
            "function": binding["function"],
            "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
        }
        spec["documentation_source"] = spec["source"]["file"]
    document["schema_version"] = "3.0"
    document["tool_count"] = len(document["tools"])
    document["graph_tool_count"] = sum(
        spec.get("indexing", {}).get("graph", True)
        for spec in document["tools"].values()
    )
    document["embedding_tool_count"] = sum(
        spec.get("indexing", {}).get("embedding", True)
        for spec in document["tools"].values()
    )
    for key in ["scientific_tools", "discovery_tools"]:
        document.pop(key, None)
    atomic_json(path, document)
    write_implementation_index(document)
    requirements = {}
    for name, spec in sorted(document["tools"].items()):
        for key in spec["execution"].get("requires", []):
            requirements.setdefault(key, []).append(name)
    atomic_json(
        ROOT / "configs/tool_resources.json",
        {
            "source": "tools/catalog/catalog.json execution.requires",
            "scope": "Declared runtime requirements, not an exhaustive license/OS dependency manifest; online reachability, checkpoint contents and external programs still require deployment checks.",
            "requirements": {
                key: {"tool_count": len(names), "tools": names}
                for key, names in sorted(requirements.items())
            },
        },
    )
    quality = Counter(
        item.get("description_basis", "explicit_contract")
        for spec in document["tools"].values()
        for item in spec["parameters"]
    )
    report = {
        "tools": len(document["tools"]),
        "single_catalogue": "tools/catalog/catalog.json",
        "parameter_descriptions": dict(quality),
        "scientific_functions_executed": 0,
        "source_files": len(modules),
        "descriptions_and_input_output_contracts_preserved": True,
    }
    atomic_json(ROOT / "results/reports/tool_documentation.json", report)
    print(json.dumps(report))


if __name__ == "__main__":
    main()
