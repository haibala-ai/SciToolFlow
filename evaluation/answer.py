"""Two-stage Flow scoring: deterministic field rules first, optional semantic review second.

Why this exists (v0.1 problems this module fixes):

* ``tool_planning_accuracy`` used exact reference matching only.  The paper and the
  original SciToolEval code both fall back to a semantic judge when the path does not
  match exactly, so a legitimate alternative path must not become an undefined score.
* ``final_answer_accuracy`` compared the agent answer with a deeply nested reference
  dict under strict key-set equality.  Free-text answers could never match, and every
  non-match became ``None``, which made the aggregate ``null``.
* No partial credit and no per-field reporting, so a single wrong leaf hid everything.

The module keeps the strict result available and adds a *defaulted* result where an
unresolved field counts as incorrect but is flagged for review, so aggregate metrics
are always defined and never silently invented.
"""

from collections import Counter
import copy
import hashlib
import json
import math
import re

from .comparison import canonical

NUMBER = re.compile(r"(?<![A-Za-z])[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")


def normalize_key(value):
    """Compare answer keys ignoring case, separators and surrounding markup."""
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def normalize_text(value):
    text = str(value)
    text = re.sub(r"(?m)^\s*#{1,6}\s*", "", text)
    return re.sub(r"\s+", " ", text.replace("**", "").replace("`", "")).strip()


def parse_answer(answer):
    """Return (structured_or_None, raw_text).  JSON embedded in text is decoded."""
    if isinstance(answer, (dict, list)):
        return answer, json.dumps(answer, ensure_ascii=False)
    if not isinstance(answer, str):
        return None, "" if answer is None else str(answer)
    text = answer.strip()
    if not text:
        return None, ""
    for candidate in (text, *re.findall(r"```(?:json)?\s*(.*?)```", text, re.S)):
        try:
            return json.loads(candidate), text
        except (ValueError, TypeError):
            continue
    if text[:1] in "[{" and text[-1:] in "]}":
        try:
            return json.loads(text), text
        except (ValueError, TypeError):
            pass
    return None, text


def key_lookup(container, name):
    """Find a key by normalized name; returns (found, value)."""
    if not isinstance(container, dict):
        return False, None
    if name in container:
        return True, container[name]
    target = normalize_key(name)
    matches = [v for k, v in container.items() if normalize_key(k) == target]
    if len(matches) == 1:
        return True, matches[0]
    return False, None


_BRACKET = re.compile(r"^([^\[]*)((?:\[[^\]]*\])*)$")


def split_path(path):
    """Split a dotted field path into segments, expanding ``name[i]`` and ``name[key]``.

    A rule may write an array index or a keyed entry in brackets, as in
    ``interfaces[0].contacts`` or ``results[mp-6930].formula``. Splitting on the dot alone leaves
    ``interfaces[0]`` as a single literal key that no answer carries, which silently drops the rule
    before it is scored, so the field it guards is never checked.
    """
    if isinstance(path, list):
        return [str(part) for part in path]
    segments = []
    for part in str(path).split("."):
        if not part:
            continue
        match = _BRACKET.match(part)
        head, brackets = match.group(1), match.group(2)
        if head:
            segments.append(head)
        segments.extend(
            inner for inner in re.findall(r"\[([^\]]*)\]", brackets) if inner
        )
    return segments


def strip_envelope(path):
    parts = split_path(path)
    if parts and normalize_key(parts[0]) == "results":
        parts = parts[1:]
    return parts


def path_candidates(path):
    """Both the declared path and the same path with/without the ``results`` envelope."""
    full = split_path(path)
    candidates = [full]
    if full and normalize_key(full[0]) == "results":
        candidates.append(full[1:])
    elif full:
        candidates.append(["results"] + full)
    return [c for c in candidates if c]


def resolve_candidates(value, candidates, text=None):
    for parts in candidates:
        found, resolved = resolve_path(value, parts, text=text)
        if found:
            return True, resolved, parts
    return False, None, None


def field_paths(reference):
    """Field rules declared by the reference, falling back to the answer leaves."""
    rules = (reference.get("scoring") or {}).get("field_rules") or []
    paths = []
    for rule in rules:
        parts = strip_envelope(rule.get("path", rule.get("field", "")))
        if parts and parts not in [p["parts"] for p in paths]:
            paths.append({"parts": parts, "rule": rule})
    if paths:
        return paths
    answer = reference.get("expected_answer")
    for key in (answer.get("results") if isinstance(answer, dict) else {}) or {}:
        paths.append(
            {
                "parts": [key],
                "rule": {"field": "results." + key, "atol": 1e-6, "rtol": 1e-6},
            }
        )
    return paths


def resolve_path(value, parts, text=None):
    """Resolve a path in a structured answer, then in key/value text lines."""
    if isinstance(value, (dict, list)):
        current = value
        for part in parts:
            if isinstance(current, list):
                if not part.isdigit() or int(part) >= len(current):
                    return False, None
                current = current[int(part)]
                continue
            found, current = key_lookup(current, part)
            if not found:
                return False, None
        return True, current
    if text:
        for part in reversed(parts):
            pattern = re.escape(part).replace(r"\_", r"[\s_-]*")
            match = re.search(
                r"(?im)^[\s>*-]*" + pattern + r"[\s*`]*[:=]\s*(.+)$", text
            )
            if match:
                raw = match.group(1).strip().rstrip(".,;")
                try:
                    return True, json.loads(raw)
                except (ValueError, TypeError):
                    return True, raw
    return False, None


def scalar_compare(expected, actual, atol, rtol):
    """Return 'match' | 'mismatch' | 'unresolved' for one leaf."""
    if isinstance(expected, bool) or expected is None:
        if isinstance(actual, str):
            folded = actual.strip().lower()
            if folded in {"true", "false"} and isinstance(expected, bool):
                return "match" if (folded == "true") == expected else "mismatch"
            if folded in {"none", "null", "n/a"} and expected is None:
                return "match"
        return (
            "match"
            if (type(expected) is type(actual) and expected == actual)
            else "mismatch"
        )
    if isinstance(expected, (int, float)):
        if isinstance(actual, bool):
            return "unresolved"
        if isinstance(actual, (int, float)):
            if not math.isfinite(actual):
                return "mismatch"
            return (
                "match"
                if abs(expected - actual) <= atol + rtol * abs(expected)
                else "mismatch"
            )
        if isinstance(actual, str):
            if not re.fullmatch(NUMBER, actual.strip()):
                return "unresolved"
            value = float(actual.strip())
            return (
                "match"
                if math.isfinite(value)
                and abs(expected - value) <= atol + rtol * abs(expected)
                else "mismatch"
            )
        return "unresolved"
    if isinstance(expected, str):
        if not isinstance(actual, str):
            actual = (
                json.dumps(actual, ensure_ascii=False)
                if isinstance(actual, (dict, list))
                else str(actual)
            )
        if normalize_text(expected) == normalize_text(actual):
            return "match"
        return "unresolved"
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return "unresolved"
        outcomes = [
            scalar_compare(expected[k], actual[k], atol, rtol)
            for k in expected
            if k in actual
        ]
        if len(outcomes) != len(expected):
            return "unresolved"
        return (
            "mismatch"
            if "mismatch" in outcomes
            else ("unresolved" if "unresolved" in outcomes else "match")
        )
    if isinstance(expected, list):
        if not isinstance(actual, list):
            return "unresolved"
        if len(expected) != len(actual):
            return "mismatch"
        outcomes = [scalar_compare(a, b, atol, rtol) for a, b in zip(expected, actual)]
        return (
            "mismatch"
            if "mismatch" in outcomes
            else ("unresolved" if "unresolved" in outcomes else "match")
        )
    return "unresolved"


def expand_leaves(expected, parts, limit=None, depth=0):
    """Expand a composite expected value into scored leaves.

    Field rules are declared at group level (``results.test_metrics``), while a
    free-text answer only exposes leaves, so each group must be descended into.
    Every leaf is checked; limit remains a compatibility argument, not a sampling cap.
    """
    if isinstance(expected, dict):
        rows = []
        for key, value in expected.items():
            rows.extend(
                expand_leaves(value, parts + [key], limit=limit, depth=depth + 1)
            )
        return rows or [{"parts": parts, "expected": {}, "kind": "leaf"}]
    if isinstance(expected, list):
        rows = [{"parts": parts, "expected": len(expected), "kind": "length"}]
        for index, value in enumerate(expected):
            rows.extend(
                expand_leaves(value, parts + [str(index)], limit=limit, depth=depth + 1)
            )
        return rows
    return [{"parts": parts, "expected": expected, "kind": "leaf"}]


def score_answer(reference, answer):
    """Per-field answer score, descending composite rules into leaves."""
    structured, text = parse_answer(answer)
    from .equivalence import normalize_answer_equivalences

    structured, representation_proofs = normalize_answer_equivalences(
        reference, structured
    )
    from scitoolflow.benchmark.schema import validation_errors

    contract_errors = (
        validation_errors(structured, reference["answer_contract"])
        if reference.get("answer_contract")
        else []
    )
    grouped, matched_leaves, total_leaves = [], 0, 0
    unique_leaves = {}
    for entry in field_paths(reference):
        rule = entry["rule"]
        candidates = path_candidates(rule.get("path", rule.get("field", "")))
        found, expected, reference_parts = resolve_candidates(
            reference.get("expected_answer"), candidates
        )
        if not found:
            raise ValueError(
                "Unresolvable reference scoring rule: " + str(rule.get("field"))
            )
        base = reference_parts or candidates[0]
        if rule.get("comparison") == "unordered_string_array":
            if not isinstance(expected, list) or any(
                not isinstance(v, str) for v in expected
            ):
                raise ValueError(
                    "unordered_string_array requires a string-array reference"
                )
            found, actual, _ = resolve_candidates(structured, candidates, text=text)
            outcome = (
                "match"
                if found
                and isinstance(actual, list)
                and all(isinstance(v, str) for v in actual)
                and Counter(actual) == Counter(expected)
                else "mismatch"
            )
            unique_leaves[(tuple(base), "unordered_string_array")] = outcome
            grouped.append(
                {
                    "field": rule.get("field", ".".join(base)),
                    "unit": rule.get("unit"),
                    "atol": 0,
                    "rtol": 0,
                    "outcome": outcome,
                    "leaves_total": 1,
                    "leaves_matched": int(outcome == "match"),
                    "leaves": [{"path": ".".join(base), "outcome": outcome}],
                }
            )
            continue
        atol = float(rule.get("atol", 1e-6))
        rtol = float(rule.get("rtol", 1e-6))
        if any(not math.isfinite(v) or v < 0 for v in [atol, rtol]):
            raise ValueError("Tolerances must be finite and nonnegative")
        leaves = []
        for leaf in expand_leaves(expected, base):
            if leaf["kind"] == "length":
                located, actual, _ = resolve_candidates(
                    structured, path_candidates(leaf["parts"]), text=text
                )
                outcome = (
                    "match"
                    if isinstance(actual, list) and len(actual) == leaf["expected"]
                    else (
                        "mismatch"
                        if isinstance(actual, list)
                        else "unresolved" if structured is None else "mismatch"
                    )
                )
            else:
                located, actual, _ = resolve_candidates(
                    structured, path_candidates(leaf["parts"]), text=text
                )
                if not located and text:
                    located_text, actual, _ = resolve_candidates(
                        None, [leaf["parts"]], text=text
                    )
                    if located_text:
                        located = True
                if not located:
                    outcome = "unresolved" if structured is None else "mismatch"
                else:
                    effective_rule = (
                        reference.get("scoring", {})
                        .get("leaf_rules", {})
                        .get(json.dumps(leaf["parts"]), rule)
                    )
                    if effective_rule.get("comparison") == "literal_string":
                        outcome = (
                            "match"
                            if type(actual) is str and actual == leaf["expected"]
                            else "mismatch"
                        )
                    else:
                        outcome = scalar_compare(
                            leaf["expected"],
                            actual,
                            float(effective_rule.get("atol", atol)),
                            float(effective_rule.get("rtol", rtol)),
                        )
            leaves.append({"path": ".".join(leaf["parts"]), "outcome": outcome})
            identity = (tuple(leaf["parts"]), leaf["kind"])
            prior = unique_leaves.get(identity)
            priority = {"match": 0, "unresolved": 1, "mismatch": 2}
            if prior is None or priority[outcome] > priority[prior]:
                unique_leaves[identity] = outcome
            total_leaves += 1
            if outcome == "match":
                matched_leaves += 1
        outcomes = [leaf["outcome"] for leaf in leaves]
        if not outcomes:
            rule_outcome = "unresolved"
        elif all(o == "match" for o in outcomes):
            rule_outcome = "match"
        elif any(o == "mismatch" for o in outcomes):
            rule_outcome = "mismatch"
        else:
            rule_outcome = "unresolved"
        grouped.append(
            {
                "field": rule.get("field", ".".join(base)),
                "unit": rule.get("unit"),
                "atol": atol,
                "rtol": rtol,
                "outcome": rule_outcome,
                "leaves_total": len(outcomes),
                "leaves_matched": sum(1 for o in outcomes if o == "match"),
                "leaves": leaves[:20],
            }
        )
    outcomes = [row["outcome"] for row in grouped]
    total_leaves = len(unique_leaves)
    matched_leaves = sum(value == "match" for value in unique_leaves.values())
    if not grouped:
        exact = canonical(reference.get("expected_answer")) == canonical(answer)
        return {
            "fields": [],
            "matched": 0,
            "total": 0,
            "unresolved": 0,
            "status": (
                "failed"
                if contract_errors
                else (
                    "passed"
                    if exact
                    else ("failed" if structured is not None else "needs_review")
                )
            ),
            "contract_errors": contract_errors,
        }
    if contract_errors:
        status = "failed"
    elif all(o == "match" for o in outcomes):
        status = "passed"
    elif any(o == "mismatch" for o in outcomes):
        status = "failed"
    else:
        status = "needs_review"
    return {
        "fields": grouped,
        "representation_normalizations": representation_proofs,
        "matched": sum(1 for o in outcomes if o == "match"),
        "total": len(grouped),
        "leaves_matched": matched_leaves,
        "leaves_total": total_leaves,
        "unresolved": sum(1 for o in outcomes if o == "unresolved"),
        "status": status,
        "contract_errors": contract_errors,
    }
