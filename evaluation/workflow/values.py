"""Typed JSON values, numeric boundaries and scientific representation comparison."""

import json
import math
import re
from collections import Counter


class MissingEvidence(ValueError):
    """A declared value cannot be resolved from this execution."""


def pointer(value, path=""):
    """Resolve an exact RFC 6901 pointer; no heuristic key or unit conversions."""
    if path == "":
        return value
    if not isinstance(path, str) or not path.startswith("/"):
        raise ValueError("Paths must be JSON pointers")
    for part in path[1:].split("/"):
        if re.search(r"~(?:[^01]|$)", part):
            raise ValueError("Invalid JSON pointer escape")
        key = part.replace("~1", "/").replace("~0", "~")
        try:
            if isinstance(value, list):
                if not re.fullmatch(r"0|[1-9][0-9]*", key):
                    raise MissingEvidence(path)
                value = value[int(key)]
            else:
                value = value[key]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise MissingEvidence(path) from exc
    return value


def _number(value):
    if type(value) not in (float, int):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _equal(left, right, atol=0.0, rtol=0.0, casefold=False):
    if type(left) in (int, float) and type(right) in (int, float):
        return (
            _number(left)
            and _number(right)
            and abs(left - right) <= atol + rtol * abs(right)
        )
    if type(left) is not type(right):
        return False
    if isinstance(left, str):
        left, right = left.strip(), right.strip()
        return left.casefold() == right.casefold() if casefold else left == right
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _equal(a, b, atol, rtol, casefold) for a, b in zip(left, right)
        )
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(
            _equal(left[k], right[k], atol, rtol, casefold) for k in left
        )
    return left == right


def _unordered(left, right, rule, deduplicate=False):
    if not isinstance(left, list) or not isinstance(right, list):
        return False
    if deduplicate:

        def unique(items):
            result = []
            for item in items:
                if not any(_equal(item, old) for old in result):
                    result.append(item)
            return result

        left, right = unique(left), unique(right)
    if len(left) != len(right):
        return False

    # Most table handoffs are exact source copies under one joint permutation.
    # Hash those complete typed rows before constructing a quadratic graph.
    def exact_key(value):
        if type(value) in (int, float):
            if not _number(value):
                raise MissingEvidence("Nonfinite unordered evidence")
            return ("number", value)
        if isinstance(value, str):
            text = value.strip()
            return ("string", text.casefold() if rule.get("casefold", False) else text)
        if isinstance(value, list):
            return ("list", tuple(exact_key(v) for v in value))
        if isinstance(value, dict):
            return ("object", frozenset((k, exact_key(v)) for k, v in value.items()))
        return (type(value).__name__, value)

    try:
        identical = Counter(map(exact_key, left)) == Counter(map(exact_key, right))
    except (TypeError, MissingEvidence):
        identical = False
    if identical:
        return True
    if not rule.get("atol", 0) and not rule.get("rtol", 0):
        return False
    # Bipartite matching avoids greedy errors with overlapping numeric tolerances.
    edges = [
        [
            j
            for j, item in enumerate(right)
            if _equal(
                value,
                item,
                rule.get("atol", 0),
                rule.get("rtol", 0),
                rule.get("casefold", False),
            )
        ]
        for value in left
    ]
    assigned = {}

    def augment(i, seen):
        for j in edges[i]:
            if j in seen:
                continue
            seen.add(j)
            if j not in assigned or augment(assigned[j], seen):
                assigned[j] = i
                return True
        return False

    return all(augment(i, set()) for i in range(len(left)))


def _contains_nonfinite(value):
    if type(value) in (int, float):
        return not _number(value)
    if isinstance(value, dict):
        return any(_contains_nonfinite(v) for v in value.values())
    if isinstance(value, list):
        return any(_contains_nonfinite(v) for v in value)
    return False


def _valid_curve(x, y):
    return (
        isinstance(x, list)
        and isinstance(y, list)
        and len(x) >= 2
        and len(x) == len(y)
        and all(_number(v) for v in x + y)
        and all(a < b for a, b in zip(x, x[1:]))
    )


def _curve_equivalent(actual, expected, rule):
    """Exact piecewise-linear path, with declared numerical comparison tolerances.

    Retaining every source knot prevents a different trapezoid area from passing
    merely because clipped endpoints agree. Additional interpolated grid points
    are harmless; no implicit fitting, extrapolation or baseline estimation occurs.
    """
    from bisect import bisect_left

    if not isinstance(actual, dict) or not isinstance(expected, dict):
        return False
    x, y = actual.get("x"), actual.get("y")
    sx, sy = expected.get("source_x"), expected.get("source_y")
    bounds, baseline = expected.get("interval"), expected.get("baseline")
    if (
        not _valid_curve(x, y)
        or not _valid_curve(sx, sy)
        or not _number(baseline)
        or not isinstance(bounds, list)
        or len(bounds) != 2
        or not all(_number(v) for v in bounds)
    ):
        return False
    lo, hi = bounds
    if not sx[0] <= lo < hi <= sx[-1]:
        return False
    close_x = lambda a, b: _equal(a, b, rule.get("x_atol", 0), rule.get("x_rtol", 0))
    if not close_x(x[0], lo) or not close_x(x[-1], hi):
        return False
    if any(
        (v < lo and not close_x(v, lo)) or (v > hi and not close_x(v, hi)) for v in x
    ):
        return False
    for knot in sx:
        if lo < knot < hi and not any(close_x(v, knot) for v in x):
            return False
    for v, value in zip(x, y):
        # Only roundoff-sized deviations at declared interval boundaries are
        # clamped. Every interior coordinate is evaluated on its actual grid.
        q = lo if v < lo else hi if v > hi else v
        j = bisect_left(sx, q)
        if j < len(sx) and sx[j] == q:
            expected_y = sy[j] - baseline
        else:
            if j == 0 or j == len(sx):
                return False
            fraction = (q - sx[j - 1]) / (sx[j] - sx[j - 1])
            expected_y = sy[j - 1] + fraction * (sy[j] - sy[j - 1]) - baseline
        if not _number(expected_y) or not _equal(
            value, expected_y, rule.get("atol", 0), rule.get("rtol", 0)
        ):
            return False
    return True


def _json_size(value, context):
    """Check each immutable evidence object once within one scoring invocation.

    Repeated scalar lookups otherwise serialize the whole source table each
    time. No cache survives a score, and standalone operand calls stay uncached.
    Strong references prevent object identity reuse from bypassing validation.
    """
    cache = context.get("_json_sizes")
    entry = cache.get(id(value)) if cache is not None else None
    if entry is not None and entry[0] is value:
        return entry[1]
    size = len(json.dumps(value, allow_nan=False, ensure_ascii=False))
    if cache is not None and len(cache) < 4096:
        cache[id(value)] = (value, size)
    return size
