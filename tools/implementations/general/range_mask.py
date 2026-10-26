"""Bounded finite numerical range indicators without data deletion or repair."""

import math


def numeric_range_mask(
    values: list,
    lower_bound: float | None = None,
    upper_bound: float | None = None,
    lower_inclusive: bool = True,
    upper_inclusive: bool = True,
) -> dict:
    """Return an ordered 0/1 indicator for a declared finite numeric range.

    Accept a nonempty finite 1D vector or rectangular 2D matrix, with at most
    10000 total cells. Boolean/null cells, ragged or higher-dimensional input
    are rejected. Bounds are finite numbers or null; null is unbounded, never
    a missing-cell replacement. Inclusive flags must be actual booleans.
    A reversed range is an error. Equal endpoints with either endpoint open
    produce a valid all-zero mask. Two null bounds produce an all-one mask.
    Output numeric 0/1 preserves every input position and shape. No rows are
    deleted and no values are imputed. It does not infer a scientific cutoff,
    establish statistical significance, or correct sampling/measurement bias.
    """
    if not isinstance(values, list) or not values or len(values) > 10000:
        raise ValueError(
            "values must be a nonempty numeric vector or rectangular matrix"
        )
    is_matrix = isinstance(values[0], list)
    if is_matrix:
        if (
            not values[0]
            or len(values) * len(values[0]) > 10000
            or any(not isinstance(r, list) or len(r) != len(values[0]) for r in values)
        ):
            raise ValueError("Matrix rows must be nonempty and rectangular")
        flat = [v for row in values for v in row]
        shape = [len(values), len(values[0])]
    else:
        flat = values
        shape = [len(values)]
    if len(flat) > 10000 or any(
        type(v) not in (int, float) or not math.isfinite(v) for v in flat
    ):
        raise ValueError(
            "At most 10000 finite numeric cells; boolean/null/nested values are rejected"
        )
    for bound in [lower_bound, upper_bound]:
        if bound is not None and (
            type(bound) not in (int, float) or not math.isfinite(bound)
        ):
            raise ValueError("Bounds must be finite numbers or null, not booleans")
    if type(lower_inclusive) is not bool or type(upper_inclusive) is not bool:
        raise ValueError("Inclusive flags must be actual booleans")
    if (
        lower_bound is not None
        and upper_bound is not None
        and lower_bound > upper_bound
    ):
        raise ValueError("lower_bound must not exceed upper_bound")

    def accepted(v):
        lower = lower_bound is None or (
            v >= lower_bound if lower_inclusive else v > lower_bound
        )
        upper = upper_bound is None or (
            v <= upper_bound if upper_inclusive else v < upper_bound
        )
        return int(lower and upper)

    mask = [accepted(v) for v in flat]
    output = (
        [mask[i * shape[1] : (i + 1) * shape[1]] for i in range(shape[0])]
        if is_matrix
        else mask
    )
    return {
        "values": output,
        "shape": shape,
        "selected_count": sum(mask),
        "element_count": len(flat),
        "lower_bound": lower_bound,
        "upper_bound": upper_bound,
        "lower_inclusive": lower_inclusive,
        "upper_inclusive": upper_inclusive,
        "scope": "Ordered numeric range indicator only; no dropped rows, imputation, inferred cutoff or statistical conclusion.",
    }
