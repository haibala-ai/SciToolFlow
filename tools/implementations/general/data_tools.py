"""Agent data-ingestion, selection, composition and reporting tools; no network or arbitrary code execution."""

import csv
import io
import json
import math
from decimal import Decimal, InvalidOperation
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
    MAX_COLUMNS,
    MAX_TEXT,
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
    # JSON Booleans are not numeric IDs; integer/float numeric equivalents match.
    return tuple(("number" if type(v) in (int, float) else type(v).__name__, v) for v in values)


def _same_json(a, b):
    if type(a) in (int, float) and type(b) in (int, float):
        return a == b
    if type(a) is not type(b):
        return False
    if isinstance(a, list):
        return len(a) == len(b) and all(_same_json(x, y) for x, y in zip(a, b))
    if isinstance(a, dict):
        return set(a) == set(b) and all(_same_json(a[k], b[k]) for k in a)
    return a == b


def parse_csv_records(csv_text: str | None = None, delimiter: str = ",", csv_file: str | None = None) -> dict:
    """Parse CSV text into records with string cells and explicit column names; reject duplicate headers or inconsistent row widths."""
    if (csv_text is None) == (csv_file is None):
        raise InputValidationError("Supply exactly one of csv_text or csv_file")
    source_metadata = {}
    if csv_file is not None:
        from .research_data import _public_source_path
        import hashlib
        path = _public_source_path(csv_file)
        if path.stat().st_size > 1000000:
            raise InputValidationError("CSV source exceeds1000000 bytes")
        raw = path.read_bytes()
        try:
            csv_text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise InputValidationError("CSV source requires UTF-8 text") from error
        source_metadata = dict(source_file=path.name, source_sha256=hashlib.sha256(raw).hexdigest())
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
        **source_metadata,
    )


def parse_json_document(json_text: str | None = None, json_file: str | None = None) -> dict:
    """Parse a strict JSON document, rejecting duplicate object keys and nonfinite numbers instead of silently losing information."""
    if (json_text is None) == (json_file is None):
        raise InputValidationError("Supply exactly one of json_text or json_file")
    source_metadata = {}
    if json_file is not None:
        from .research_data import _public_source_path
        import hashlib
        path = _public_source_path(json_file)
        if path.stat().st_size > 1000000:
            raise InputValidationError("JSON source exceeds1000000 bytes; use file query for large record sets")
        raw = path.read_bytes()
        try:
            json_text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise InputValidationError("JSON source requires UTF-8 text") from error
        source_metadata = dict(source_file=path.name, source_sha256=hashlib.sha256(raw).hexdigest())
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
    return result(document=value, **source_metadata)


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
                return _same_json(item, value)
            if operator == "ne":
                return not _same_json(item, value)
            if operator == "contains":
                require(
                    isinstance(item, (str, list)),
                    "contains requires text or list cells",
                )
                if isinstance(item, str):
                    require(isinstance(value, str), "Text containment requires a string value")
                    return value in item
                return any(_same_json(value, part) for part in item)
            if operator == "in":
                return any(_same_json(item, part) for part in value)
            if item is None:
                return False
            require(type(item) is not bool and type(value) is not bool, "Boolean values have no numeric ordering")
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
    if cardinality in {"one_to_one", "one_to_many"}:
        require(all(count == 1 for count in lc.values()), "Declared cardinality requires unique left keys")
    if cardinality in {"one_to_one", "many_to_one"}:
        require(all(count == 1 for count in rc.values()), "Declared cardinality requires unique right keys")
    left_names, right_names = _all_columns(left), _all_columns(right)
    left_values = [k for k in left_names if k not in on_columns]
    right_values = [k for k in right_names if k not in on_columns]
    def name_for(key, side):
        return key + "_" + side if key in overlap else key
    out_columns = list(on_columns) + [name_for(k, "left") for k in left_values] + [name_for(k, "right") for k in right_values]
    require(estimate * len(out_columns) <= MAX_CELLS, "Join exceeds output cell limit")
    def identity(row):
        return _key([row[k] for k in on_columns])
    def emit(lrow, rrow):
        source = rrow if how == "right" else lrow if lrow is not None else rrow
        item = {k: source[k] for k in on_columns}
        for row, keys, side in [(lrow, left_values, "left"), (rrow, right_values, "right")]:
            for key in keys:
                if row is None:
                    item[name_for(key, side)] = None
                elif key in row:
                    item[name_for(key, side)] = row[key]
        return item
    clean = []
    if how == "right":
        indexed = {}
        for row in left:
            indexed.setdefault(identity(row), []).append(row)
        for row in right:
            matches = indexed.get(identity(row))
            clean.extend(emit(lrow, row) for lrow in matches or [None])
    else:
        indexed = {}
        for index, row in enumerate(right):
            indexed.setdefault(identity(row), []).append((index, row))
        seen_right = set()
        for row in left:
            matches = indexed.get(identity(row), [])
            if matches:
                clean.extend(emit(row, rrow) for _, rrow in matches)
                seen_right.update(index for index, _ in matches)
            elif how in {"left", "outer"}:
                clean.append(emit(row, None))
        if how == "outer":
            clean.extend(emit(None, row) for index, row in enumerate(right) if index not in seen_right)
    return result(records=clean, columns=out_columns, row_count=len(clean), cardinality=cardinality,
                  key_semantics="JSON types preserved; numeric integer/float equivalents match; bool is distinct; null keys rejected",
                  missing_policy="Unmatched side becomes null; absent fields inside a present source record remain absent")


def convert_record_column_types(record_table: list, column_types: dict) -> dict:
    """Parse explicitly selected scalar columns, preserving rows and null cells.

    Destination aliases int/integer, float/number, str/string and bool/boolean
    are case-insensitive after trimming. Every selected column must exist in
    every input record. Unselected columns and row order remain unchanged.
    Integer parsing requires a finite exact integral value within the numeric
    range; no fractional truncation. Numeric destinations reject boolean cells.
    Boolean parsing accepts bool, numeric0/1, or case-insensitive strings
    true/false/0/1; it does not trim cell strings or infer arbitrary truthiness.
    String conversion uses Python scalar spelling (True/False for booleans),
    not JSON serialization. Lists and objects cannot be converted to strings
    or other scalar types. Null remains null for every requested destination.
    Return records and normalized column_types; no in-place mutation, dropped
    records, repair of missing columns or inference of scientific units.
    """
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
        except InputValidationError:
            raise
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
    require(len(names) <= MAX_COLUMNS and len(rows) * len(names) <= MAX_CELLS,
            "Rendered table exceeds200 columns or50000 cells; select fewer columns/rows")
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
    characters = sum(len(line) + 1 for line in lines)
    for row in rows:
        line = "| " + " | ".join(escape(row.get(k)) for k in names) + " |"
        characters += len(line) + 1
        require(characters <= MAX_TEXT, "Rendered table exceeds1000000 characters")
        lines.append(line)
    return result(markdown="\n".join(lines), columns=names, row_count=len(rows))
