"""Exact finite-sample order statistic; no probability or inference policy."""

import math


def select_order_statistic(values: list, rank: int) -> dict:
    """Return the caller-specified 1-based k-th smallest observed numeric value.

    Args:
        values: A nonempty list of 1..10000 finite int/float JSON numbers.
            Booleans, strings, null, nested arrays and nonfinite values fail.
            Repeated values are separate observations and are never deduplicated.
            Input order is irrelevant and the caller's list is never modified.
        rank: Explicit 1-based integer in 1..len(values). Finite mathematically
            integral JSON floats are accepted without rounding. Booleans,
            numeric strings and nonintegral floats fail.

    Returns:
        selected_value (an actual observed number, without interpolation),
        rank, count, less_count, equal_count, greater_count, rank_base and scope.
        A tie spans ranks less_count+1 through less_count+equal_count inclusive.
        rank 1 returns the minimum and rank count the maximum. It does not
        select a probability, compute a conformal rank or infer independence,
        exchangeability, a confidence interval, coverage or a scientific claim.

    Raises:
        ValueError: Invalid data, types, finite-value domain, rank or size.
            Missing/invalid observations are never omitted or imputed.
    """
    if not isinstance(values, list) or not 1 <= len(values) <= 10000:
        raise ValueError("values must contain 1..10000 finite numeric observations")
    for position, value in enumerate(values):
        if type(value) not in (int, float):
            raise ValueError(f"values[{position}] must be numeric, excluding bool")
        try:
            valid = math.isfinite(value)
        except OverflowError:
            valid = False
        if not valid:
            raise ValueError(f"values[{position}] must be finite")
    if type(rank) is int:
        normalized_rank = rank
    elif type(rank) is float and math.isfinite(rank) and rank.is_integer():
        normalized_rank = int(rank)
    else:
        raise ValueError("rank must be a mathematical integer, excluding bool")
    if not 1 <= normalized_rank <= len(values):
        raise ValueError("rank must lie in 1..len(values), with 1-based indexing")
    selected = sorted(values)[normalized_rank - 1]
    less = sum(value < selected for value in values)
    equal = sum(value == selected for value in values)
    return {
        "selected_value": selected,
        "rank": normalized_rank,
        "count": len(values),
        "less_count": less,
        "equal_count": equal,
        "greater_count": len(values) - less - equal,
        "rank_base": 1,
        "scope": "Caller-specified 1-based order statistic of the complete supplied finite sample; repeated observations retained; no interpolation, omission, probability choice or inference policy.",
    }
