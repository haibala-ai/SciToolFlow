"""Single source of truth for tool documentation and execution bindings."""

import json
from contextvars import ContextVar
from pathlib import Path
from src.utils.paths import project_root

DISCOVERY_TOOL = "DescribeTools"
CURRENT_CATALOG = ContextVar("tool_catalog", default=None)


class ToolCatalog:
    def __init__(self, root=None):
        self.root = Path(root) if root else project_root()
        document = json.loads((self.root / "tools/catalog/catalog.json").read_text())
        self.tools = document["tools"]
        self.aliases = document.get("aliases", {})
        self.retired = document.get("retired_tools", {})

    def canonical(self, name):
        seen = set()
        while name in self.aliases:
            if name in seen:
                raise ValueError("Cycle in tool aliases")
            seen.add(name)
            name = self.aliases[name]
        return name

    def indexed_tools(self, index="graph"):
        """Index membership is independent of a tool's discipline or executor."""
        if index not in {"graph", "embedding"}:
            raise ValueError("Index must be graph or embedding")
        return {
            name: spec
            for name, spec in self.tools.items()
            if spec.get("indexing", {}).get(index, True)
        }

    def names_by_domain(self):
        groups = {}
        for name, spec in sorted(self.tools.items()):
            groups.setdefault(spec["domain"], []).append(name)
        return groups

    def describe(self, names):
        from tools.catalog.discovery import describe

        return describe(names, self)

    def registry(self):
        """Derived runtime registry view; the catalog remains the only stored contract."""
        return {
            "aliases": self.aliases,
            "retired_tools": self.retired,
            "tools": {
                name: {
                    **spec["execution"],
                    "category": spec["domain"],
                    "kind": spec["kind"],
                    "parameters": spec["parameters"],
                    "description": spec["description"],
                    "input_schema": spec.get("input_schema", {}),
                    "output_schema": spec.get("output_schema", {}),
                    "output_encoding": spec.get("output_encoding", {}),
                }
                for name, spec in self.tools.items()
            },
        }
