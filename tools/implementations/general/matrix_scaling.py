"""Explicit bounded row/column numeric scaling without scientific inference."""

import math


def scale_numeric_matrix(
    values: list, row_factors: list | None = None, column_factors: list | None = None
) -> dict:
    """Return row_factors[i] * values[i][j] * column_factors[j].

    values is a nonempty rectangular finite real matrix, outer length<=10000,
    width<=1000 and total cells<=10000. Booleans, strings, null and nested cells
    fail. Each supplied factor vector has exactly the corresponding axis length
    and finite real entries; null means all ones,never data-derived normalization.
    Signed and zero factors are supported. Values and factors use ordinary float64
    arithmetic in the stated left-to-right multiplication order. Invalid shape,
    overflow/nonfinite result or nonzero multiplication underflow rejects the
    entire call rather than clipping,imputing or returning partial rows. No unit,
    mass weighting,coordinate alignment,normalization or scientific validity is
    inferred. Explicit source row/column order is preserved.
    """

    def finite(value, label):
        if type(value) not in (int, float):
            raise ValueError(
                label + " must be finite real,excluding boolean/string/null"
            )
        try:
            number = float(value)
        except (OverflowError, ValueError):
            raise ValueError(label + " cannot be represented as float64") from None
        if not math.isfinite(number):
            raise ValueError(label + " must be finite")
        return number

    if (
        not isinstance(values, list)
        or not 1 <= len(values) <= 10000
        or not all(isinstance(row, list) and row for row in values)
    ):
        raise ValueError("values must be a nonempty rectangular numeric matrix")
    nrows, ncols = len(values), len(values[0])
    if (
        ncols > 1000
        or nrows * ncols > 10000
        or any(len(row) != ncols for row in values)
    ):
        raise ValueError(
            "matrix width<=1000,total cells<=10000 and rectangular rows required"
        )
    matrix = [
        [finite(v, f"values[{i}][{j}]") for j, v in enumerate(row)]
        for i, row in enumerate(values)
    ]

    def factors(value, size, label):
        if value is None:
            return [1.0] * size
        if not isinstance(value, list) or len(value) != size:
            raise ValueError(
                label
                + " must be null or a vector of exactly the corresponding axis length"
            )
        return [finite(v, f"{label}[{i}]") for i, v in enumerate(value)]

    rows = factors(row_factors, nrows, "row_factors")
    columns = factors(column_factors, ncols, "column_factors")
    result = []
    for i, row in enumerate(matrix):
        selected = []
        for j, value in enumerate(row):
            intermediate = rows[i] * value
            out = intermediate * columns[j]
            if not math.isfinite(intermediate) or not math.isfinite(out):
                raise ValueError(
                    f"float64 overflow/nonfinite product at row{i},column{j}"
                )
            if (rows[i] != 0 and value != 0 and intermediate == 0) or (
                intermediate != 0 and columns[j] != 0 and out == 0
            ):
                raise ValueError(
                    f"nonzero float64 multiplication underflow at row{i},column{j}"
                )
            selected.append(out)
        result.append(selected)
    return {
        "values": result,
        "shape": [nrows, ncols],
        "element_count": nrows * ncols,
        "row_factors_applied": row_factors is not None,
        "column_factors_applied": column_factors is not None,
        "row_factors_used": rows,
        "column_factors_used": columns,
        "scope": "Explicit row_i*value_ij*column_j scaling only;source axis order retained. No unit,mass,normalization or coordinate interpretation inferred.",
    }
