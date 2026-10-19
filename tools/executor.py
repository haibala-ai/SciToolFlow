"""Stable agent-facing entry point for discovery and isolated scientific execution."""

import json
from scitoolflow.paths import bootstrap_runtime
from .catalog import DISCOVERY_TOOL, ToolCatalog


def execute(name, arguments, files=None, timeout=180, catalog=None):
    catalog = catalog or ToolCatalog()
    canonical = catalog.canonical(name)
    if canonical == DISCOVERY_TOOL:
        try:
            if not isinstance(arguments, dict) or set(arguments) != {"tools"}:
                raise ValueError("DescribeTools expects exactly the tools argument")
            return {
                "tool": canonical,
                "kind": "discovery",
                "status": "success",
                "output": catalog.describe(arguments["tools"]),
            }
        except (ValueError, TypeError) as error:
            return {
                "tool": canonical,
                "kind": "discovery",
                "status": "error",
                "output": None,
                "error_type": "InvalidInput",
                "error": str(error),
            }
    if canonical not in catalog.tools:
        return {
            "tool": name,
            "status": "error",
            "output": None,
            "error_type": "UnknownTool",
            "error": "Unregistered tool: "
            + str(name)
            + ". Query an existing name with DescribeTools.",
        }
    bootstrap_runtime()
    from .runtime.dispatch import execute as dispatch

    return {
        **dispatch(
            canonical,
            json.dumps(arguments, ensure_ascii=False, allow_nan=False),
            files,
            timeout=timeout,
        ),
        "kind": "scientific",
    }
