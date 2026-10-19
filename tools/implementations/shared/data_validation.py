"""Shared bounded JSON and finite numeric contracts for the local data tools."""

import json
import math

import numpy as np

from tools.implementations.shared.common import InputValidationError

MAX_ROWS = 5000
MAX_COLUMNS = 200
MAX_CELLS = 50000
MAX_TEXT = 1000000


def require(condition, message):
    if not condition:
        raise InputValidationError(message)


def integer(value, name, minimum=1, maximum=MAX_ROWS):
    require(
        isinstance(value, int) and not isinstance(value, bool),
        f"{name}: require an integer",
    )
    require(minimum <= value <= maximum, f"{name}: require {minimum}..{maximum}")
    return value


def number(value, name):
    require(
        isinstance(value, (int, float)) and not isinstance(value, bool),
        f"{name}: require a numeric value",
    )
    try:
        result = float(value)
    except (ValueError, OverflowError):
        raise InputValidationError(f"{name}: require a finite floating-point value")
    require(math.isfinite(result), f"{name}: require a finite value")
    return result


def vector(values, name="values", minimum=1):
    require(
        isinstance(values, list) and minimum <= len(values) <= MAX_ROWS,
        f"{name}: require a list with {minimum}..{MAX_ROWS} values",
    )
    return np.array(
        [number(value, f"{name}[{i}]") for i, value in enumerate(values)], dtype=float
    )


def matrix(values, name="features", minimum_rows=1, allow_null=False):
    require(
        isinstance(values, list) and minimum_rows <= len(values) <= MAX_ROWS,
        f"{name}: require {minimum_rows}..{MAX_ROWS} rows",
    )
    require(
        all(isinstance(row, list) for row in values), f"{name}: require a list of rows"
    )
    width = len(values[0])
    require(
        1 <= width <= MAX_COLUMNS and len(values) * width <= MAX_CELLS,
        f"{name}: require 1..{MAX_COLUMNS} columns and at most {MAX_CELLS} cells",
    )
    require(
        all(len(row) == width for row in values),
        f"{name}: all rows must have the same width",
    )
    return np.array(
        [
            [
                (
                    np.nan
                    if allow_null and value is None
                    else number(value, f"{name}[{i},{j}]")
                )
                for j, value in enumerate(row)
            ]
            for i, row in enumerate(values)
        ],
        dtype=float,
    )


def labels(values, name="labels", minimum=1):
    require(
        isinstance(values, list) and minimum <= len(values) <= MAX_ROWS,
        f"{name}: require a nonempty bounded list",
    )
    require(
        all(isinstance(v, str) and bool(v.strip()) for v in values)
        or all(isinstance(v, int) and not isinstance(v, bool) for v in values),
        f"{name}: use nonempty string labels or integer labels, without mixing types",
    )
    return np.asarray(values)


def text(value, name="text", maximum=MAX_TEXT, allow_empty=False):
    require(isinstance(value, str), f"{name}: require text")
    require(
        (allow_empty or bool(value.strip())) and len(value) <= maximum,
        f"{name}: require {'0' if allow_empty else '1'}..{maximum} characters",
    )
    return value


def json_value(value, depth=0):
    require(depth <= 40, "JSON nesting exceeds 40 levels")
    if value is None or isinstance(value, (str, bool)):
        return
    if isinstance(value, (int, float)):
        number(value, "JSON number")
        return
    if isinstance(value, list):
        require(len(value) <= MAX_CELLS, "JSON list is too large")
        for item in value:
            json_value(item, depth + 1)
        return
    if isinstance(value, dict):
        require(
            len(value) <= MAX_CELLS and all(isinstance(k, str) for k in value),
            "JSON object requires bounded string keys",
        )
        for item in value.values():
            json_value(item, depth + 1)
        return
    raise InputValidationError("Require JSON-compatible values")


def records(values, name="records"):
    require(
        isinstance(values, list) and 1 <= len(values) <= MAX_ROWS,
        f"{name}: require 1..{MAX_ROWS} records",
    )
    require(
        all(isinstance(row, dict) and row for row in values),
        f"{name}: require nonempty record objects",
    )
    require(sum(len(row) for row in values) <= MAX_CELLS, f"{name}: too many cells")
    require(
        all(
            len(row) <= MAX_COLUMNS
            and all(isinstance(k, str) and k.strip() for k in row)
            for row in values
        ),
        f"{name}: require nonempty column names and at most {MAX_COLUMNS} columns",
    )
    json_value(values)
    return values


def columns(values, available=None, name="columns"):
    require(
        isinstance(values, list)
        and values
        and all(isinstance(v, str) and v.strip() for v in values),
        f"{name}: require nonempty column names",
    )
    require(
        len(values) <= MAX_COLUMNS and len(set(values)) == len(values),
        f"{name}: column names must be unique",
    )
    if available is not None:
        require(set(values) <= set(available), f"{name}: contains unknown columns")
    return values


def result(**payload):
    def convert(value):
        if isinstance(value, np.ndarray):
            return convert(value.tolist())
        if isinstance(value, np.generic):
            return convert(value.item())
        if isinstance(value, dict):
            return {str(k): convert(v) for k, v in value.items()}
        if isinstance(value, (tuple, list)):
            return [convert(v) for v in value]
        if isinstance(value, float):
            require(
                math.isfinite(value),
                "Computation produced an undefined/nonfinite result; check input scale and variance",
            )
        return value

    output = convert(payload)
    json.dumps(output, allow_nan=False)
    return output
