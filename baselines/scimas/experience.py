"""Task-local, evidence-backed procedural experience, never cached scientific answers."""

from copy import deepcopy
from .task_graph import digest


class Experience:
    def __init__(self, capacity=20, matches=3):
        self.capacity, self.matches, self.entries = capacity, matches, []

    def confirm(self, role, tool, contract, operation, evidence):
        if role not in {"planner", "executor", "reviewer"} or not evidence:
            raise ValueError("Experience needs a role and confirming evidence")
        item = {
            "role": role,
            "tool": tool,
            "contract_sha256": contract,
            "operation": deepcopy(operation),
            "evidence": list(evidence),
        }
        identity = digest({k: v for k, v in item.items() if k != "evidence"})
        self.entries = [e for e in self.entries if e["identity"] != identity]
        self.entries.append(dict(item, identity=identity))
        self.entries = self.entries[-self.capacity :]

    def match(self, role, contracts):
        return deepcopy(
            [
                e
                for e in self.entries
                if e["role"] == role
                and contracts.get(e["tool"]) == e["contract_sha256"]
            ][-self.matches :]
        )

    def invalidate(self, tool, contract):
        self.entries = [
            e
            for e in self.entries
            if not (e["tool"] == tool and e["contract_sha256"] == contract)
        ]
