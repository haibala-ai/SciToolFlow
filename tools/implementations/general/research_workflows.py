"""Bounded general record/matrix primitives, independent of scientific domain."""

import math


def _finite_sum(values):
    """Reject an unrepresentable aggregate rather than returning inf/NaN."""
    try:
        total = math.fsum(values)
    except (OverflowError, ValueError) as exc:
        raise ValueError(
            "Numeric aggregate exceeds finite representable range"
        ) from exc
    if not math.isfinite(total):
        raise ValueError("Numeric aggregate exceeds finite representable range")
    return total


def summarize_numeric_table(matrix: list, row_ids: list, column_ids: list) -> dict:
    """Audit finite numeric/null assay cells without inventing missing values.

    Rows and columns require unique string IDs. Reports per-row and per-column
    observed counts, missing counts, observed sums/means and observed minimum/maximum.
    Null cells are excluded from every observed statistic, never zero-filled.
    An all-null row/column has sum 0 (existing empty-sum convention), mean null,
    minimum null and maximum null. A real zero remains an observed value.
    No uncertainty, rank, distribution or differential inference is performed.
    """
    if (
        not isinstance(matrix, list)
        or not matrix
        or len(matrix) > 10000
        or not isinstance(row_ids, list)
        or not isinstance(column_ids, list)
        or len(matrix) != len(row_ids)
        or not column_ids
        or len(column_ids) > 1000
        or len(matrix) * len(column_ids) > 10000
    ):
        raise ValueError("Bounded matrix and aligned row/column IDs required")
    for ids in [row_ids, column_ids]:
        if any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(
            ids
        ):
            raise ValueError("IDs must be distinct nonempty strings")
    if any(not isinstance(row, list) or len(row) != len(column_ids) for row in matrix):
        raise ValueError("Matrix width/column IDs mismatch")
    if any(
        v is not None and (type(v) not in (int, float) or not math.isfinite(v))
        for row in matrix
        for v in row
    ):
        raise ValueError("Only finite numeric/null cells accepted")

    def summary(id, values):
        v = [x for x in values if x is not None]
        return {
            "id": id,
            "observed_count": len(v),
            "missing_count": len(values) - len(v),
            "observed_sum": _finite_sum(v),
            "observed_mean": _finite_sum(v) / len(v) if v else None,
            "observed_minimum": min(v) if v else None,
            "observed_maximum": max(v) if v else None,
            "zero_count": sum(x == 0 for x in v),
            "negative_count": sum(x < 0 for x in v),
            "noninteger_count": sum(x != int(x) for x in v),
        }

    return {
        "row_count": len(row_ids),
        "column_count": len(column_ids),
        "rows": [summary(i, r) for i, r in zip(row_ids, matrix)],
        "columns": [summary(i, list(v)) for i, v in zip(column_ids, zip(*matrix))],
        "missing_cell_count": sum(v is None for row in matrix for v in row),
        "scope": "observed cells only; null is not zero; no normalization or differential inference",
    }


def aggregate_record_groups(
    records: list, group_columns: list, value_column: str, operation: str = "mean"
) -> dict:
    """Aggregate numeric values by explicit string/integer key tuple, no null coercion.

    Null value cells are excluded with missing counts. Every grouping key must
    be a string or an integer; float, bool, null and container keys are rejected.
    String and integer keys remain distinct; True/1 ambiguity cannot enter groups.
    Mean/sum/median supported. Mean and even-size median avoid overflowing
    an otherwise representable average. Unrepresentable sums reject the call.
    Output first-seen group order retains key identity.
    Flat records retain their existing form unless a source group/value column
    collides with observed_count, missing_count, group_key_values or aggregate_value.
    Such records additionally expose group_key_values (the exact original key
    mapping) and aggregate_value (the requested reduction). observed_count and
    missing_count always mean the number of observed and null value cells.
    """
    from statistics import mean

    def median(values):
        ordered = sorted(values)
        n = len(ordered)
        return ordered[n // 2] if n % 2 else mean(ordered[n // 2 - 1 : n // 2 + 1])

    if (
        not isinstance(records, list)
        or not 1 <= len(records) <= 10000
        or not all(isinstance(r, dict) for r in records)
    ):
        raise ValueError("records must contain1..10000 objects")
    if (
        not isinstance(group_columns, list)
        or not group_columns
        or any(not isinstance(k, str) for k in group_columns)
        or len(set(group_columns)) != len(group_columns)
        or value_column in group_columns
    ):
        raise ValueError("Distinct group columns excluding value column required")
    if operation not in {"mean", "sum", "median"}:
        raise ValueError("operation must be mean,sum,median")
    groups = {}
    for row in records:
        if (
            any(k not in row or type(row[k]) not in (str, int) for k in group_columns)
            or value_column not in row
        ):
            raise ValueError(
                "Every record needs the value column and all grouping keys; "
                "group keys must be strings or integers, not float, bool, null or containers"
            )
        value = row[value_column]
        if value is not None and (
            type(value) not in (int, float) or not math.isfinite(value)
        ):
            raise ValueError("Values must be finite numeric/null")
        key = tuple(row[k] for k in group_columns)
        groups.setdefault(key, []).append(value)
    result = []
    for key, values in groups.items():
        observed = [x for x in values if x is not None]
        n = len(observed)
        v = (
            (
                mean(observed)
                if operation == "mean"
                else _finite_sum(observed) if operation == "sum" else median(observed)
            )
            if n
            else None
        )
        item = {
            **dict(zip(group_columns, key)),
            value_column: v,
            "observed_count": n,
            "missing_count": len(values) - n,
        }
        reserved = {
            "observed_count",
            "missing_count",
            "group_key_values",
            "aggregate_value",
        }
        if (set(group_columns) | {value_column}) & reserved:
            item["group_key_values"] = dict(zip(group_columns, key))
            item["aggregate_value"] = v
        result.append(item)
    return {
        "records": result,
        "group_count": len(result),
        "group_columns": group_columns,
        "value_column": value_column,
        "operation": operation,
        "scope": "Explicit keys; null values excluded and reported; independence not inferred",
    }


def normalize_numeric_rows(matrix: list) -> dict:
    """Convert nonnegative rows into sum-one proportions; zero rows remain null.

    Rectangular input contains at most10000 cells. Nonfinite or overflowing
    row totals reject the whole call; no all-zero overflow normalization.
    """
    if (
        not isinstance(matrix, list)
        or not matrix
        or len(matrix) > 10000
        or any(not isinstance(r, list) or not r for r in matrix)
        or len({len(r) for r in matrix}) != 1
        or sum(len(r) for r in matrix) > 10000
    ):
        raise ValueError("Require bounded rectangular nonempty rows")
    for row in matrix:
        if any(
            type(x) not in (int, float) or not math.isfinite(x) or x < 0 for x in row
        ):
            raise ValueError("Only finite nonnegative values accepted")
    totals = [_finite_sum(r) for r in matrix]
    return {
        "proportions": [
            [x / t for x in r] if t else None for r, t in zip(matrix, totals)
        ],
        "row_totals": totals,
        "zero_total_row_indices": [i for i, t in enumerate(totals) if t == 0],
        "scope": "row-sum composition only; no library normalization, rarefaction or detection correction",
    }
