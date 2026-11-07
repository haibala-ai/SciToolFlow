"""Task-local, evidence-backed procedural experience, never cached scientific answers."""

from copy import deepcopy
from .task_graph import digest


def binding_recipe(binding, node_tools):
    """Describe a successful interface use without copying objects or answers.

    Array indices become placeholders, not executable paths. Recipes are advice;
    a new graph must resolve its own indices, units, inputs and source nodes.
    """
    kind = binding["kind"]
    recipe = {"kind": kind}
    if kind == "literal":
        value = binding["value"]
        recipe["value_type"] = (
            "null" if value is None else "boolean" if isinstance(value, bool) else
            "number" if isinstance(value, (int, float)) else
            "string" if isinstance(value, str) else
            "array" if isinstance(value, list) else "object"
        )
    elif kind == "list":
        # Repeated candidates share one binding pattern. Do not copy provenance
        # payloads or list lengths into procedural memory.
        patterns = [binding_recipe(item, node_tools) for item in binding["items"]]
        recipe["item_patterns"] = list({digest(p): p for p in patterns}.values())
    elif kind == "python_code":
        recipe["input_patterns"] = {
            name: binding_recipe(source, node_tools)
            for name, source in binding["inputs"].items()
        }
    else:
        recipe["path_pattern"] = ["<index>" if type(p) is int else p
                                  for p in binding.get("path", [])]
        if kind in {"node", "collect"}:
            recipe["source_tool"] = node_tools[binding["node"]]
            recipe["decoded"] = binding.get("decoded", False)
    return recipe


class Experience:
    def __init__(self, capacity=20, matches=3):
        self.capacity, self.matches, self.entries = capacity, matches, []

    def confirm(self, role, tool, contract, operation, evidence, *, dependencies=None):
        if role not in {"planner", "executor", "reviewer"} or not evidence:
            raise ValueError("Experience needs a role and confirming evidence")
        item = {
            "role": role,
            "tool": tool,
            "contract_sha256": contract,
            "operation": deepcopy(operation),
            "evidence": list(evidence),
            "required_contracts": {tool: contract, **(dependencies or {})},
        }
        identity = digest({k: v for k, v in item.items() if k != "evidence"})
        self.entries = [e for e in self.entries if e["identity"] != identity]
        self.entries.append(dict(item, identity=identity))
        # A burst of result reviews must not evict the other roles' skills.
        same_role = [e["identity"] for e in self.entries if e["role"] == role]
        expired = set(same_role[:-self.capacity])
        self.entries = [e for e in self.entries if e["identity"] not in expired]

    def match(self, role, contracts, *, focus_tools=None):
        return deepcopy(
            [
                e
                for e in self.entries
                if e["role"] == role
                and all(contracts.get(t) == sha for t, sha in e["required_contracts"].items())
                and (focus_tools is None or set(e["required_contracts"]) & set(focus_tools))
            ][-self.matches :]
        )

    def invalidate(self, tool, contract):
        self.entries = [
            e
            for e in self.entries
            if e["required_contracts"].get(tool) != contract
        ]
