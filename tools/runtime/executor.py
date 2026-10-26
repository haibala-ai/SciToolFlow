"""Stable agent-facing entry point for discovery and isolated scientific execution."""

import json
from src.utils.paths import bootstrap_runtime
from tools.catalog import CURRENT_CATALOG, ToolCatalog


def execute(name, arguments, files=None, timeout=180, catalog=None):
    catalog = catalog or ToolCatalog()
    canonical = catalog.canonical(name)
    if canonical in catalog.retired:
        return {
            "tool": name,
            "status": "error",
            "output": None,
            "error_type": "RetiredTool",
            **catalog.retired[canonical],
            "error": "Tool retired after capability consolidation. Query DescribeTools for the replacement contract.",
        }
    if (
        canonical in catalog.tools
        and catalog.tools[canonical]["execution"].get("backend") == "host"
    ):
        try:
            import importlib
            import inspect
            from tools.runtime.contracts import contract_errors

            spec = catalog.tools[canonical]
            if not isinstance(arguments, dict):
                raise ValueError("Tool arguments must be a JSON object")
            errors = contract_errors(arguments, spec["input_schema"])
            if errors:
                raise ValueError("; ".join(str(e) for e in errors[:8]))
            binding = spec["execution"]
            function = getattr(
                importlib.import_module(binding["module"]), binding["function"]
            )
            inspect.signature(function).bind(**arguments)
            token = CURRENT_CATALOG.set(catalog)
            try:
                output = function(**arguments)
            finally:
                CURRENT_CATALOG.reset(token)
            from tools.runtime.dispatch import validate_result

            return {"tool": canonical, "kind": "tool", **validate_result(output, spec)}
        except (ValueError, TypeError) as error:
            return {
                "tool": canonical,
                "kind": "tool",
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
    from tools.runtime.contracts import contract_errors

    errors = contract_errors(arguments, catalog.tools[canonical]["input_schema"])
    if errors:
        return {
            "tool": canonical,
            "kind": "tool",
            "status": "error",
            "output": None,
            "error_type": "InvalidInput",
            "error": "; ".join(errors),
            "contract_lookup": {
                "tool": "DescribeTools",
                "arguments": {"tools": [canonical]},
            },
        }
    bootstrap_runtime()
    from tools.runtime.dispatch import execute as dispatch

    return {
        **dispatch(
            canonical,
            json.dumps(arguments, ensure_ascii=False, allow_nan=False),
            files,
            timeout=timeout,
        ),
        "kind": "tool",
    }
