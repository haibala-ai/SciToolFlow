"""Batch public contracts only; this module never executes a scientific tool."""

import difflib
from .catalog import ToolCatalog

PUBLIC_FIELDS = (
    "name",
    "domain",
    "kind",
    "description",
    "call_signature",
    "parameters",
    "input_schema",
    "output_description",
    "output_schema",
    "returns",
    "output_encoding",
    "limitations",
)


def describe(names, catalog):
    if isinstance(names, str):
        names = [names]
    if (
        not isinstance(names, list)
        or not 1 <= len(names) <= 20
        or any(not isinstance(n, str) or not n.strip() for n in names)
    ):
        raise ValueError(
            "DescribeTools.tools must be one name or an array of 1–20 nonempty tool names"
        )
    found = {}
    unknown = []
    for requested in dict.fromkeys(names):
        name = catalog.canonical(requested)
        if name not in catalog.tools:
            unknown.append(
                {
                    "name": requested,
                    "suggestions": difflib.get_close_matches(
                        requested, catalog.tools, n=3, cutoff=0.5
                    ),
                }
            )
            continue
        found[requested] = {key: catalog.tools[name][key] for key in PUBLIC_FIELDS}
    return {"tools": found, "unknown": unknown, "count": len(found)}


def describe_tools(tools):
    return ToolCatalog().describe(tools)
