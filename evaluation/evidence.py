"""Explicit evidence-conditioned targets for documented nondeterministic outputs.

This is opt-in per reference, never a global replacement of scientific gold with
whatever an agent reports. Only a successful same-tool, exact-input observation can
condition the named quantity; the derived checks are recomputed independently here.
"""

import copy
import json
import math
import re
from .comparison import arguments_equal


def condition_reference(reference, calls, answer):
    spec = reference.get("scoring", {}).get("evidence_conditioning")
    if not spec:
        return reference, None
    if spec.get("kind") != "normalized_inertia":
        raise ValueError("Unknown evidence-conditioning policy")
    candidates = []
    for call in calls:
        if call.get("tool") != spec["tool"] or call.get("status") != "success":
            continue
        if not arguments_equal(spec["tool"], spec["arguments"], call.get("arguments")):
            continue
        output = call.get("output")
        if not isinstance(output, str):
            continue
        values = []
        for number in [1, 2]:
            match = re.search(
                rf"(?m)^\s*-\s*NPR{number}\s*\([^\n]*?\):\s*([-+0-9.eE]+)\s*$", output
            )
            if match is None:
                break
            values.append(float(match.group(1)))
        if len(values) == 2 and all(math.isfinite(value) for value in values):
            candidates.append((call.get("observation_id"), values))
    if not candidates:
        return reference, {
            "kind": spec["kind"],
            "status": "missing_actual_evidence",
            "error": "A successful CalculatePmi observation for this exact molecule is required; archival ratios are not a substitute.",
        }
    if isinstance(answer, str):
        try:
            answer = json.loads(answer)
        except ValueError:
            answer = None
    reported = (
        ((answer or {}).get("results") or {}).get("native_normalized_ratios")
        if isinstance(answer, dict)
        else None
    )
    selected = candidates[0]
    # Repeated unseeded calls may legitimately differ. A value actually observed in
    # any of those calls is acceptable; the answer cannot introduce a new baseline.
    for candidate in candidates:
        if reported == candidate[1]:
            selected = candidate
            break
    result = copy.deepcopy(reference)
    r = result["expected_answer"]["results"]
    values = selected[1]
    r["native_normalized_ratios"] = values
    r["native_bounds_and_order_satisfied"] = 0 <= values[0] <= values[1] <= 1
    # Four-decimal displayed values have at most 0.0001 uncertainty in their sum.
    r["native_triangle_satisfied_at_display_precision"] = sum(values) >= 1 - 0.0001
    r["seed42_minus_native_ratios"] = [
        a - b for a, b in zip(r["seed42_normalized_ratios"], values)
    ]
    r["ratios_agree_within_tolerance"] = [
        abs(a - b) <= 1e-8 + 1e-6 * abs(b)
        for a, b in zip(r["seed42_normalized_ratios"], values)
    ]
    result["final_answer"] = json.dumps(result["expected_answer"], ensure_ascii=False)
    return result, {
        "kind": spec["kind"],
        "status": "conditioned_on_actual_observation",
        "observation_id": selected[0],
        "quantities": [
            "native_normalized_ratios",
            "native_bounds_and_order_satisfied",
            "native_triangle_satisfied_at_display_precision",
            "seed42_minus_native_ratios",
            "ratios_agree_within_tolerance",
        ],
        "independent_experimental_validation": False,
    }
