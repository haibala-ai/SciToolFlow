"""Bounded outer-axis selection of explicit numeric arrays without computation."""

import math


def slice_numeric_array(
    values: list, start: int = 0, stop: int | None = None, step: int = 1
) -> dict:
    """Select existing rows/elements, preserving supplied values and order.

    values is a nonempty finite real vector or rectangular matrix, excluding
    booleans/strings/null, with outer length and total cells <=10000 and matrix
    width <=1000. A matrix must have at least one column. Select only along the
    outer axis: start/stop are nonnegative integers <= original outer length,
    stop is exclusive (null means length), step is an integer1..10000. Negative
    indexing, clipping out-of-bounds indices and reverse order are unsupported.
    stop<=start yields a valid empty selection. Explicit output_shape preserves
    a matrix's column width even when values is empty. No arithmetic, imputation,
    sorting, unit inference, file I/O or code execution occurs.
    """
    if not isinstance(values, list) or not 1 <= len(values) <= 10000:
        raise ValueError(
            "values must be a nonempty numeric vector or matrix, outer length1..10000"
        )
    matrix = any(isinstance(row, list) for row in values)
    if matrix:
        if (
            not all(isinstance(row, list) and row for row in values)
            or len(values[0]) > 1000
            or any(len(row) != len(values[0]) for row in values)
            or len(values) * len(values[0]) > 10000
        ):
            raise ValueError(
                "matrix must be rectangular, width1..1000 and total cells<=10000"
            )
        flat = (v for row in values for v in row)
        source_shape = [len(values), len(values[0])]
    else:
        flat = iter(values)
        source_shape = [len(values)]
    for value in flat:
        if type(value) not in (int, float):
            raise ValueError(
                "all source cells must be finite real numbers; booleans/strings/null are rejected"
            )
        try:
            finite = math.isfinite(value)
        except (OverflowError, TypeError):
            finite = False
        if not finite:
            raise ValueError(
                "all source cells must be finite representable real numbers"
            )
    size = len(values)
    if type(start) is not int or not 0 <= start <= size:
        raise ValueError("start must be a nonnegative integer <= outer-axis length")
    if stop is None:
        stop = size
    if type(stop) is not int or not 0 <= stop <= size:
        raise ValueError(
            "stop must be null or a nonnegative integer <= outer-axis length"
        )
    if type(step) is not int or not 1 <= step <= 10000:
        raise ValueError(
            "step must be an integer1..10000; reverse or zero step is unsupported"
        )
    indices = list(range(start, stop, step))
    selected = [list(values[i]) if matrix else values[i] for i in indices]
    shape = [len(indices), source_shape[1]] if matrix else [len(indices)]
    return {
        "values": selected,
        "source_shape": source_shape,
        "output_shape": shape,
        "selected_indices": indices,
        "start": start,
        "stop": stop,
        "step": step,
        "scope": "Outer-axis selection only; original values and order retained. No arithmetic, sorting, unit inference or scientific decision.",
    }
