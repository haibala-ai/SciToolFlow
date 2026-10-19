"""Explicit optional non-biological execution scope; existing scientific safety checks remain enabled."""

from functools import lru_cache
import json
import os
from pathlib import Path
import re


@lru_cache(maxsize=1)
def scope_metadata(construction=False):
    from scitoolflow.paths import project_root
    from tools.catalog import ToolCatalog

    root = project_root()
    registry = ToolCatalog().registry()
    if construction:
        # Construction uses audited categories, never KG relations; unknowns fail closed.
        allowed = {"Chemical", "Material", "MachineLearning", "General"}
        excluded = {
            name
            for name, spec in registry["tools"].items()
            if spec.get("category") not in allowed
            or ".biology." in spec.get("module", "")
        }
        excluded.add("PerformBlastQuery")
        return registry, excluded
    graph = json.loads((root / "tools/graph/graph_store.json").read_text())[
        "graph_dict"
    ]
    excluded = set()
    for name in set(graph) | set(registry["tools"]):
        canonical = registry["aliases"].get(name, name)
        spec = registry["tools"].get(canonical, {})
        edges = graph.get(name, graph.get(canonical, []))
        domain = " ".join(
            str(value)
            for relation, value in edges
            if relation in ["inputs", "outputs", "is a"]
        )
        if (
            spec.get("category") == "Biology"
            or ".biology." in spec.get("module", "")
            or re.search(
                r"\b(?:biological|protein|dna|rna|peptide|antibody|gene|sequence|nucleic acid|amino acid)\b",
                domain,
                re.I,
            )
        ):
            excluded.add(canonical)
    excluded.add("PerformBlastQuery")
    return registry, excluded


def tool_allowed(name):
    scope = os.getenv("SCITOOL_TOOL_SCOPE", "all")
    if scope not in ["all", "nonbiological", "nonbiological_with_human_annotations"]:
        raise ValueError("Unknown execution scope")
    if scope == "all":
        return True
    registry, excluded = scope_metadata(
        bool(os.getenv("SCITOOL_CONSTRUCTION_READ_AUDIT"))
    )
    canonical = registry["aliases"].get(name, name)
    if scope == "nonbiological_with_human_annotations" and canonical in {
        "INGAArchitecture",
        "INGAHomology",
        "INGAInteraction",
    }:
        return (
            registry["tools"].get(canonical, {}).get("scope_permission")
            == "human_annotations"
        )
    return canonical in registry["tools"] and canonical not in excluded


def triple_allowed(text):
    match = re.search(r"\('([^']+)'\s*,", text)
    return bool(match and tool_allowed(match[1]))
