"""Detect changed live selector results without accepting the submitted science."""

import json
import re
from pathlib import Path
from .planning import arguments_match

SELECTORS = {
    "GetMaterialIdByFormula",
    "SearchByBandGap",
    "SearchByChemsys",
    "SearchMaterialsContainingElements",
}


def selector_drift(reference, calls, root, aliases):
    if not set(reference.get("tool_path", [])) & SELECTORS:
        return []
    archived = []
    for line in (Path(root) / reference["reference_trace"]).read_text().splitlines():
        row = json.loads(line)
        if (
            row.get("event") == "tool_result"
            and row.get("tool") in SELECTORS
            and row.get("status") == "success"
        ):
            archived.append(row)

    def identifiers(value):
        text = value if isinstance(value, str) else json.dumps(value)
        return list(dict.fromkeys(re.findall(r"\bmp-(?:[0-9]+|[a-z]{8})\b", text)))

    changes = []
    for actual in calls:
        tool = aliases.get(actual.get("tool"), actual.get("tool"))
        if actual.get("status") != "success" or tool not in SELECTORS:
            continue
        for expected in archived:
            if tool != expected["tool"] or not arguments_match(
                tool, expected["arguments"], actual.get("arguments", {})
            ):
                continue
            old, new = identifiers(expected.get("output")), identifiers(
                actual.get("output")
            )
            if old and new and old != new:
                changes.append(
                    {
                        "tool": tool,
                        "reference_observation_id": expected["observation_id"],
                        "actual_observation_id": actual.get("observation_id"),
                        "archival_identifier_count": len(old),
                        "actual_identifier_count": len(new),
                        "archival_first_identifier": old[0],
                        "actual_first_identifier": new[0],
                        "ordered_identifiers_changed": True,
                        "reference_identifiers": old,
                        "actual_identifiers": new,
                    }
                )
    return changes
