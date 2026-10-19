"""Bounded model context and inspection of actual stored observations."""

import json
import math
import hashlib


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def finite(value):
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, dict):
        return all(finite(v) for v in value.values())
    if isinstance(value, list):
        return all(finite(v) for v in value)
    return True


def preview(value, limit=1000):
    rendered = encode(value)
    if len(rendered) <= limit:
        return value
    return {
        "preview": rendered[: limit // 2] + " ... " + rendered[-limit // 2 :],
        "truncated": True,
        "characters": len(rendered),
        "structure": structure_summary(value),
        "sha256": hashlib.sha256(rendered.encode()).hexdigest(),
    }


def structure_summary(value, depth=0):
    """Expose observed cardinality without copying a large scientific array."""
    if isinstance(value, list):
        shape = []
        level = [value]
        for _ in range(8):
            if (
                not level
                or len(level) > 50000
                or not all(isinstance(v, list) for v in level)
            ):
                break
            lengths = {len(v) for v in level}
            if len(lengths) != 1:
                break
            shape.append(next(iter(lengths)))
            if sum(len(row) for row in level) > 50000:
                break
            level = [child for row in level for child in row]
        return {"type": "array", "length": len(value), "uniform_shape_prefix": shape}
    if isinstance(value, dict):
        result = {"type": "object", "key_count": len(value), "keys": list(value)[:20]}
        if depth < 1:
            result["fields"] = {
                k: structure_summary(v, depth + 1) for k, v in list(value.items())[:20]
            }
        return result
    if isinstance(value, str):
        return {"type": "string", "characters": len(value)}
    return {"type": type(value).__name__}


class Context:
    """Preserve a stable prefix; compact only when the char budget is exceeded."""

    def __init__(self, initial, limit, token_counter=None, token_limit=None):
        self.initial = initial
        self.limit = limit
        self.history = []
        self.compactions = 0
        self.token_counter = token_counter
        self.token_limit = token_limit
        if not self.fits(initial):
            raise ValueError("Question and tool contracts exceed the context budget")

    def fits(self, messages):
        return len(encode(messages)) <= self.limit and (
            self.token_counter is None
            or self.token_counter(messages) <= self.token_limit
        )

    def append(self, role, content):
        self.history.append({"role": role, "content": content})

    def build(self, summaries, state=None):
        tail = [{"role": "user", "content": encode(state)}] if state is not None else []
        full = self.initial + self.history + tail
        if self.fits(full):
            return full
        self.compactions += 1
        ledger = [
            {
                "role": "user",
                "content": "Earlier actual observations; use inspect for full fields:\n"
                + encode(summaries),
            }
        ]
        if not self.fits(self.initial + ledger + tail):
            ledger[0]["content"] = (
                "Actual observation IDs; use inspect for full fields:\n"
                + encode(
                    [
                        {k: row[k] for k in ["observation_id", "tool", "status"]}
                        for row in summaries
                    ]
                )
            )
        if not self.fits(self.initial + ledger + tail):
            raise ValueError("Observation index exceeds the context budget")
        recent = []
        for item in reversed(self.history):
            candidate = [item] + recent
            if len(candidate) > 6 or not self.fits(
                self.initial + ledger + candidate + tail
            ):
                break
            recent = candidate
        return self.initial + ledger + recent + tail


def _inspect(request, observations, limit):
    if not isinstance(request, dict):
        raise ValueError("inspect must be an object")
    identifier = request.get("observation_id")
    row = observations.get(identifier)
    if row is None or row["status"] != "success":
        raise ValueError("inspect requires a successful actual observation")
    part = request.get("part", "output")
    if part not in {"output", "arguments"}:
        raise ValueError("inspect part must be output or arguments")
    value = row[part]
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            pass
    path = request.get("field", [])
    if not isinstance(path, list) or any(
        not isinstance(k, (str, int)) or isinstance(k, bool) for k in path
    ):
        raise ValueError("field must be a list of object keys or array indices")
    for key in path:
        value = value[key]
    offset = request.get("offset", 0)
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ValueError("offset must be a nonnegative integer")
    rendered = encode(value)
    if offset == 0 and len(rendered) <= limit:
        return {
            "observation_id": identifier,
            "part": part,
            "field": path,
            "value": value,
        }
    return {
        "observation_id": identifier,
        "part": part,
        "field": path,
        "offset": offset,
        "structure": structure_summary(value),
        "text_window": rendered[offset : offset + limit],
        "next_offset": offset + limit if offset + limit < len(rendered) else None,
    }
