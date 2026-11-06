"""Scientific dependency checks using observed execution, not log serialization."""

import math


def _times(call):
    start, finish = call.get("started_seconds"), call.get("finished_seconds")
    if start is None and finish is None:
        return None
    if start is None or finish is None:
        raise ValueError('Incomplete observed scientific-call timing')
    if (any(type(t) not in (int, float) or not math.isfinite(t) for t in (start, finish))
            or start < 0 or finish < start):
        raise ValueError("Invalid observed scientific-call timing")
    return start, finish


def observed_before(parent, child):
    """A real dependency consumes an available result; independent calls need no edge.

    Legacy sequential ReAct traces do not contain dispatcher intervals, so their
    authenticated call order remains the evidence. Timed parallel traces use the
    producer's finish and consumer's start, irrespective of result collection order.
    """
    a, b = _times(parent), _times(child)
    if a is not None and b is not None:
        return a[1] <= b[0]
    return parent["_index"] < child["_index"]
