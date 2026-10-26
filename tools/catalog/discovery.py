"""Batch public contracts only; this module never executes a scientific tool."""

import difflib
from tools.catalog import CURRENT_CATALOG, ToolCatalog

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
    "indexing",
    "dataflow",
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
            if requested in catalog.retired:
                record = catalog.retired[requested]
                unknown.append(
                    {
                        "name": requested,
                        "status": "retired",
                        **record,
                        "replacement_contracts": {
                            replacement: {
                                key: catalog.tools[replacement].get(key)
                                for key in PUBLIC_FIELDS
                            }
                            for replacement in record.get("replacements", [])
                            if replacement in catalog.tools
                        },
                    }
                )
                continue
            unknown.append(
                {
                    "name": requested,
                    "suggestions": difflib.get_close_matches(
                        requested, catalog.tools, n=3, cutoff=0.5
                    ),
                }
            )
            continue
        found[requested] = {key: catalog.tools[name].get(key) for key in PUBLIC_FIELDS}
        if "failure_feedback" in catalog.tools[name]:
            found[requested]["failure_feedback"] = catalog.tools[name][
                "failure_feedback"
            ]
    return {"tools": found, "unknown": unknown, "count": len(found)}


def describe_tools(tools):
    return (CURRENT_CATALOG.get() or ToolCatalog()).describe(tools)
