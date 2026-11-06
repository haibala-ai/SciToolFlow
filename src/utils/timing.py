"""Wall-clock interval accounting without double-counting overlapping work."""
import math


def merge_intervals(intervals, *, bounds=None):
    merged = []
    for start, stop in sorted(intervals):
        if any(type(x) not in (int, float) or not math.isfinite(x) for x in (start, stop)):
            raise ValueError("Timing intervals must be finite monotonic timestamps")
        if stop < start:
            raise ValueError("Timing interval ends before it starts")
        if bounds is not None:
            start, stop = max(start, bounds[0]), min(stop, bounds[1])
            if stop <= start:
                continue
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(stop, merged[-1][1])
        else:
            merged.append([start, stop])
    return merged


def interval_seconds(intervals, *, bounds=None):
    return sum(stop - start for start, stop in merge_intervals(intervals, bounds=bounds))


def subtract_intervals(intervals, covered, *, bounds=None):
    """Return time in intervals that is not already covered by other work."""
    work = merge_intervals(covered, bounds=bounds)
    result = []
    for start, stop in merge_intervals(intervals, bounds=bounds):
        cursor = start
        for left, right in work:
            if right <= cursor:
                continue
            if left >= stop:
                break
            if left > cursor:
                result.append([cursor, min(left, stop)])
            cursor = max(cursor, right)
            if cursor >= stop:
                break
        if cursor < stop:
            result.append([cursor, stop])
    return result
