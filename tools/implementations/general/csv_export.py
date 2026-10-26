"""Bounded explicit JSON-table serialization to unique current-task CSV files."""
import json


def save_to_csv_file(input_json: str) -> str:
    """Export a bounded JSON table to a unique current-task CSV artifact, without fixed-file overwrites.

    Accept a JSON list of flat row objects, or a flat object with equal-length
    list columns (a scalar object is one row). Preserve first-row column order;
    every row must have the same columns. Values are JSON scalars only. Empty
    input, nested cells, inconsistent columns/lengths or nonfinite values fail.
    CSV is data serialization only; no scientific analysis or spreadsheet formula
    evaluation is performed. Returns JSON with artifact path/row/column counts.
    """
    import csv
    import math
    import uuid
    from src.utils.paths import artifacts_root
    if not isinstance(input_json, str) or not 1 <= len(input_json) <= 10000000:
        raise ValueError("input_json must contain1..10000000characters")
    data = json.loads(input_json)
    if isinstance(data, dict):
        if data and all(isinstance(value, list) for value in data.values()):
            lengths = {len(value) for value in data.values()}
            if len(lengths) != 1:
                raise ValueError("JSON columns must have equal lengths")
            rows = [dict(zip(data, values)) for values in zip(*data.values())]
        else:
            rows = [data]
    else:
        rows = data
    if not isinstance(rows, list) or not 1 <= len(rows) <= 100000 or not all(isinstance(row, dict) and row for row in rows):
        raise ValueError("Require1..100000 nonempty row objects")
    columns = list(rows[0])
    if any(not isinstance(column, str) or not column for column in columns):
        raise ValueError("Column names must be nonempty strings")
    for row in rows:
        if set(row) != set(columns):
            raise ValueError("Every row must have the same columns")
        for value in row.values():
            if isinstance(value, (dict, list)) or (isinstance(value, float) and not math.isfinite(value)):
                raise ValueError("CSV cells must be finite JSON scalars")
    directory = artifacts_root()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / ("table_" + uuid.uuid4().hex + ".csv")
    with path.open("x", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return json.dumps({"csv_path": str(path), "row_count": len(rows), "columns": columns,
                       "null_encoding": "empty CSV cell; CSV does not preserve null versus empty-string typing"})

