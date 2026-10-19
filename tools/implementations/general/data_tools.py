"""Agent data-ingestion, selection, composition and reporting tools; no network or arbitrary code execution."""

import csv
import io
import json
import math
from decimal import Decimal, InvalidOperation
import pandas as pd
import regex
from tools.implementations.shared.common import InputValidationError
from tools.implementations.shared.data_validation import (
    require,
    number,
    matrix,
    vector,
    records,
    columns,
    text,
    json_value,
    result,
    MAX_ROWS,
    MAX_CELLS,
)


def _all_columns(rows):
    return list(dict.fromkeys(key for row in rows for key in row))


def _selected(rows, names):
    columns(names, _all_columns(rows))
    require(
        all(all(name in row for name in names) for row in rows),
        "Selected columns must be present in every record",
    )
    return names


def _key(values):
    require(
        all(v is None or isinstance(v, (str, int, float, bool)) for v in values),
        "Keys/categories must be scalar JSON values",
    )
    # Python numeric equality intentionally joins integer and float equivalents.
    return tuple(values)


def parse_csv_records(csv_text: str, delimiter: str = ",") -> dict:
    """Parse CSV text into records with string cells and explicit column names; reject duplicate headers or inconsistent row widths."""
    text(csv_text, "csv_text")
    require(
        isinstance(delimiter, str) and len(delimiter) == 1 and delimiter not in "\r\n",
        "delimiter must be one non-newline character",
    )
    try:
        parsed = list(
            csv.reader(io.StringIO(csv_text), delimiter=delimiter, strict=True)
        )
    except csv.Error as error:
        raise InputValidationError(str(error))
    require(bool(parsed), "CSV has no header")
    names = columns(parsed[0])
    data = [row for row in parsed[1:] if row]
    require(
        len(data) <= MAX_ROWS and len(data) * len(names) <= MAX_CELLS,
        "CSV exceeds bounded table size",
    )
    require(
        all(len(row) == len(names) for row in data), "CSV rows must match header width"
    )
    return result(
        records=[dict(zip(names, row)) for row in data],
        columns=names,
        row_count=len(data),
        cell_type="string",
    )


def parse_json_document(json_text: str) -> dict:
    """Parse a strict JSON document, rejecting duplicate object keys and nonfinite numbers instead of silently losing information."""
    text(json_text, "json_text")

    def pairs(items):
        require(
            len(dict(items)) == len(items), "Duplicate JSON object keys are not allowed"
        )
        return dict(items)

    def constant(value):
        raise InputValidationError("Nonfinite JSON numeric constant: " + value)

    try:
        value = json.loads(json_text, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, RecursionError) as error:
        raise InputValidationError("Invalid JSON: " + str(error))
    json_value(value)
    return result(document=value)


def get_json_pointer(document: object, pointer: str = "") -> dict:
    """Read a value by RFC 6901 JSON Pointer, including tilde/slash escapes; an empty pointer addresses the root document."""
    json_value(document)
    text(pointer, "pointer", 10000, True)
    require(
        not pointer or pointer.startswith("/"),
        "A nonempty JSON Pointer must start with slash",
    )
    value = document
    for token in pointer.split("/")[1:] if pointer else []:
        require(
            regex.search(r"~(?:[^01]|$)", token) is None, "Invalid JSON Pointer escape"
        )
        key = token.replace("~1", "/").replace("~0", "~")
        if isinstance(value, dict):
            require(key in value, "JSON Pointer object key not found")
            value = value[key]
        elif isinstance(value, list):
            require(
                regex.fullmatch(r"0|[1-9][0-9]*", key) is not None and len(key) <= 10,
                "Invalid JSON Pointer array index",
            )
            index = int(key)
            require(index < len(value), "JSON Pointer array index out of range")
            value = value[index]
        else:
            raise InputValidationError("JSON Pointer traverses a scalar value")
    return result(value=value, pointer=pointer)


def filter_records(
    record_table: list, column: str, operator: str, value: object = None
) -> dict:
    """Filter table rows by eq/ne/lt/le/gt/ge/contains/in/is_null/not_null; no matches is a valid empty result."""
    rows = records(record_table)
    _selected(rows, [column])
    json_value(value)
    require(
        operator
        in {
            "eq",
            "ne",
            "lt",
            "le",
            "gt",
            "ge",
            "contains",
            "in",
            "is_null",
            "not_null",
        },
        "Unsupported filter operator",
    )
    if operator == "in":
        require(isinstance(value, list), "in requires a list value")

    def accept(item):
        try:
            if operator == "is_null":
                return item is None
            if operator == "not_null":
                return item is not None
            if operator == "eq":
                return item == value
            if operator == "ne":
                return item != value
            if operator == "contains":
                require(
                    isinstance(item, (str, list)),
                    "contains requires text or list cells",
                )
                return value in item
            if operator == "in":
                return item in value
            if item is None:
                return False
            if operator == "lt":
                return item < value
            if operator == "le":
                return item <= value
            if operator == "gt":
                return item > value
            return item >= value
        except TypeError:
            raise InputValidationError("Filter value has an incompatible cell type")

    chosen = [dict(row) for row in rows if accept(row[column])]
    return result(records=chosen, matched_count=len(chosen), input_count=len(rows))


def join_record_tables(
    left_records: list,
    right_records: list,
    on_columns: list,
    how: str = "inner",
    cardinality: str = "one_to_one",
) -> dict:
    """Join record tables on non-null scalar keys with declared cardinality and a bounded output; overlapping value columns receive suffixes."""
    left, right = records(left_records, "left_records"), records(
        right_records, "right_records"
    )
    _selected(left, on_columns)
    _selected(right, on_columns)
    require(how in {"inner", "left", "right", "outer"}, "Unsupported join type")
    require(
        cardinality in {"one_to_one", "one_to_many", "many_to_one", "many_to_many"},
        "Unsupported cardinality",
    )
    from collections import Counter

    def counts(rows):
        require(
            all(all(row[k] is not None for k in on_columns) for row in rows),
            "Join keys must not be null",
        )
        return Counter(_key([row[k] for k in on_columns]) for row in rows)

    lc, rc = counts(left), counts(right)
    estimate = sum(count * rc.get(k, 0) for k, count in lc.items())
    if how in {"left", "outer"}:
        estimate += sum(v for k, v in lc.items() if k not in rc)
    if how in {"right", "outer"}:
        estimate += sum(v for k, v in rc.items() if k not in lc)
    require(estimate <= MAX_ROWS, "Join would exceed 5000 output rows")
    overlap = (set(_all_columns(left)) & set(_all_columns(right))) - set(on_columns)
    generated = (
        set(on_columns)
        | {
            k + "_left" if k in overlap else k
            for k in _all_columns(left)
            if k not in on_columns
        }
        | {
            k + "_right" if k in overlap else k
            for k in _all_columns(right)
            if k not in on_columns
        }
    )
    expected = (
        len(set(on_columns))
        + len(_all_columns(left))
        + len(_all_columns(right))
        - 2 * len(set(on_columns))
    )
    require(
        len(generated) == expected, "Join suffixes would collide with existing columns"
    )
    try:
        joined = pd.DataFrame(left, dtype=object).merge(
            pd.DataFrame(right, dtype=object),
            on=on_columns,
            how=how,
            suffixes=("_left", "_right"),
            validate=cardinality,
        )
    except (ValueError, TypeError, pd.errors.MergeError) as error:
        raise InputValidationError("Join contract failed: " + str(error))
    require(
        len(joined) * len(joined.columns) <= MAX_CELLS,
        "Join would exceed output cell limit",
    )
    clean = [
        {
            key: None if isinstance(value, float) and math.isnan(value) else value
            for key, value in row.items()
        }
        for row in joined.to_dict(orient="records")
    ]
    return result(
        records=clean,
        columns=list(joined.columns),
        row_count=len(clean),
        cardinality=cardinality,
    )


def convert_record_column_types(record_table: list, column_types: dict) -> dict:
    """Explicitly convert record columns to int/float/str/bool (also integer/number/string/boolean), preserving nulls and rejecting fractional integers or ambiguous booleans."""
    rows = records(record_table)
    require(
        isinstance(column_types, dict) and column_types,
        "column_types must be a nonempty mapping",
    )
    _selected(rows, list(column_types))
    aliases = {
        "int": "int",
        "integer": "int",
        "float": "float",
        "number": "float",
        "str": "str",
        "string": "str",
        "bool": "bool",
        "boolean": "bool",
    }
    require(
        all(
            isinstance(v, str) and v.strip().lower() in aliases
            for v in column_types.values()
        ),
        "Destination types must be int/integer, float/number, str/string or bool/boolean",
    )
    column_types = {
        key: aliases[value.strip().lower()] for key, value in column_types.items()
    }

    def convert(value, kind):
        if value is None:
            return None
        require(
            not isinstance(value, (list, dict)), "Type conversion requires scalar cells"
        )
        try:
            if kind == "str":
                return str(value)
            if kind == "bool":
                if isinstance(value, bool):
                    return value
                if isinstance(value, str) and value.lower() in {
                    "true",
                    "false",
                    "1",
                    "0",
                }:
                    return value.lower() in {"true", "1"}
                if isinstance(value, (int, float)) and value in {0, 1}:
                    return bool(value)
                raise InputValidationError(
                    "Boolean conversion requires true/false or 0/1"
                )
            require(
                not isinstance(value, bool),
                "Boolean cells cannot be converted implicitly to numbers",
            )
            if kind == "float":
                parsed = float(value)
                require(
                    math.isfinite(parsed), "Numeric conversion requires finite values"
                )
                return parsed
            parsed = Decimal(str(value))
            require(
                parsed.is_finite() and parsed == parsed.to_integral_value(),
                "Integer conversion requires a finite integral value",
            )
            require(
                parsed.adjusted() <= 308,
                "Integer conversion exceeds supported numeric range",
            )
            return int(parsed)
        except (ValueError, OverflowError, TypeError, InvalidOperation):
            raise InputValidationError("Cell cannot be converted to " + kind)

    return result(
        records=[
            {
                k: convert(v, column_types[k]) if k in column_types else v
                for k, v in row.items()
            }
            for row in rows
        ],
        column_types=column_types,
    )


def extract_numeric_matrix(record_table: list, feature_columns: list) -> dict:
    """Extract selected finite numeric table columns as a feature matrix; convert string cells explicitly before extraction."""
    rows = records(record_table)
    _selected(rows, feature_columns)
    data = matrix([[r[k] for k in feature_columns] for r in rows])
    return result(features=data, columns=feature_columns, row_count=len(rows))


def extract_numeric_vector(record_table: list, column: str) -> dict:
    """Extract one finite numeric table column as a vector; reject null, textual or nonnumeric cells."""
    rows = records(record_table)
    _selected(rows, [column])
    return result(values=vector([r[column] for r in rows]), column=column)


def format_markdown_table(record_table: list, selected_columns: list = None) -> dict:
    """Render scalar record cells as a Markdown table with escaped pipes and line breaks, preserving a declared column order."""
    rows = records(record_table)
    names = (
        _selected(rows, selected_columns)
        if selected_columns is not None
        else _all_columns(rows)
    )
    require(
        all(not isinstance(r.get(k), (dict, list)) for r in rows for k in names),
        "Markdown table cells must be scalar",
    )

    def escape(value):
        return (
            ("" if value is None else str(value))
            .replace("\\", "\\\\")
            .replace("|", "\\|")
            .replace("\r\n", " ")
            .replace("\n", " ")
            .replace("\r", " ")
        )

    lines = [
        "| " + " | ".join(escape(k) for k in names) + " |",
        "| " + " | ".join("---" for k in names) + " |",
    ]
    lines += [
        "| " + " | ".join(escape(row.get(k)) for k in names) + " |" for row in rows
    ]
    return result(markdown="\n".join(lines), columns=names, row_count=len(rows))
