"""Single source of truth for tool documentation and execution bindings."""

import json
from pathlib import Path
from scitoolflow.paths import project_root

DISCOVERY_TOOL = "DescribeTools"


class ToolCatalog:
    def __init__(self, root=None):
        self.root = Path(root) if root else project_root()
        document = json.loads((self.root / "tools/catalog.json").read_text())
        self.tools = document["tools"]
        self.aliases = document.get("aliases", {})

    def canonical(self, name):
        return self.aliases.get(name, name)

    def names_by_domain(self):
        groups = {}
        for name, spec in sorted(self.tools.items()):
            groups.setdefault(spec["domain"], []).append(name)
        return groups

    def describe(self, names):
        from .discovery import describe

        return describe(names, self)

    def registry(self):
        """Compatibility-shaped in-memory view; never a second registry file."""
        return {
            "aliases": self.aliases,
            "tools": {
                name: {
                    **spec["execution"],
                    "category": spec["domain"],
                    "kind": spec["kind"],
                    "parameters": spec["parameters"],
                    "description": spec["description"],
                }
                for name, spec in self.tools.items()
            },
        }
