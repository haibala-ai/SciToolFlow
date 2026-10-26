"""Bounded file record transformations; no executable query language."""

import functools
import hashlib
import json
import math
from pathlib import Path
import uuid

from tools.implementations.general.research_data import (
    _public_source_path,
    _strict_json,
    _task_artifacts_root,
    _verified_provenance,
)


def _load_records(name, max_rows=60000, max_bytes=25 * 1024 * 1024):
    path = _public_source_path(name)
    if path.stat().st_size > max_bytes:
        raise ValueError("Source record file exceeds its documented byte limit")
    raw = path.read_bytes()
    document = _strict_json(raw)
    records = document.get("data") if isinstance(document, dict) else document
    if (
        not isinstance(records, list)
        or len(records) > max_rows
        or any(not isinstance(r, dict) for r in records)
    ):
        raise ValueError(
            "Expected a bounded JSON object-record list,optionally under data"
        )
    return document, records, hashlib.sha256(raw).hexdigest()


def _write_record_artifact(operation, records, metadata, parent_metadata=None):
    root = _task_artifacts_root()
    directory = root / operation / uuid.uuid4().hex
    # Preserve semantic source metadata at its original top-level position:
    # e.g. a preregistered term_ids family must survive annotation filtering.
    document = dict(parent_metadata) if parent_metadata is not None else {}
    current_metadata = dict(metadata)
    if "operation_metadata" in document:
        current_metadata["parent_operation"] = document.pop("operation_metadata")
    document.update(data=records, operation_metadata=current_metadata)
    raw = (
        json.dumps(document, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        + "\n"
    ).encode()
    if len(raw) > 50 * 1024 * 1024:
        raise ValueError("Result artifact exceeds50MiB")
    directory.mkdir(parents=True)
    target = directory / "records.json"
    temporary = directory / "records.tmp"
    temporary.write_bytes(raw)
    temporary.replace(target)
    digest = hashlib.sha256(raw).hexdigest()
    provenance = {
        "raw_sha256": digest,
        "operation": operation,
        "source_sha256": metadata["source_sha256"],
    }
    temporary = directory / "provenance.tmp"
    temporary.write_text(
        json.dumps(provenance, ensure_ascii=False, allow_nan=False) + "\n"
    )
    temporary.replace(target.with_suffix(".provenance.json"))
    return str(target), digest


def _preview(records, limit):
    if type(limit) is not int or not 0 <= limit <= 100:
        raise ValueError("preview_limit must be an integer in0..100")
    result = []
    size = 0
    for row in records[:limit]:
        encoded = json.dumps(
            row, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        )
        if size + len(encoded) > 20000:
            break
        result.append(row)
        size += len(encoded)
    return result, len(result) < len(records)


def _scalar(value):
    return (
        value is None
        or type(value) in (str, bool, int, float)
        and (type(value) is not float or math.isfinite(value))
    )


def _same(a, b):
    if type(a) in (int, float) and type(b) in (int, float):
        return a == b
    return type(a) is type(b) and a == b


def query_scientific_records_file(
    records_file: str,
    id_field: str,
    predicates: list | None = None,
    fields: list | None = None,
    order_by: list | None = None,
    limit: int | None = None,
    preview_limit: int = 20,
) -> dict:
    """Filter,project and order public/file-artifact records without code execution.

    records_file is uploaded or an explicit current-task artifact JSON record
    list,or an object with data;0..60000 rows,25 MiB maximum. Every record must have
    a unique nonempty string or integer id_field (bool/float rejected). No identifier conversion/deduplication.

    predicates is null or up to32 AND-connected objects with field,op,value.
    Operators:eq,ne,lt,le,gt,ge,in,not_in,is_null,is_not_null,exists,missing.
    eq/ne/in/not_in compare JSON scalar types exactly except numeric1==1.0;
    bool is distinct from number. in/not_in value is1..1000 scalars. Other binary
    operators take a scalar value;numeric operators require finite numbers.
    Unary operators must omit value. Null numeric comparisons return false;
    missing predicate fields raise except for explicit exists/missing tests.
    Nested field paths,regex,arbitrary expressions and OR are not supported.

    fields is null for all fields or up to 256 unique top-level field names;ID
    always retained. Every selected requested field must exist;null is retained.
    order_by is null or up to 8 objects:{field,direction:'ascending'|'descending',
    nulls:'first'|'last'}. Direction defaults ascending,nulls last. Non-null sort
    values per key must be one comparable scalar family(number,string,bool).
    Missing sort fields and mixed scalar families raise. Ties retain source
    order. limit is null or0..60000,applied after filtering and sorting;full
    matching count is always returned independently from output count.

    Full output records and original non-data metadata are written atomically
    under the explicit task-local artifact root,with source/result SHA256 and
    exact query parameters. preview_limit0..100 returns complete projected rows
    up to20000 characters,without altering artifact selection. Empty results are
    valid. No threshold,hypothesis family,background,scientific unit or method
    is inferred,and no sampling or missing-value imputation occurs.
    """
    if not isinstance(id_field, str) or not id_field or len(id_field) > 256:
        raise ValueError("id_field must be a nonempty top-level name of length<=256")
    if limit is not None and (type(limit) is not int or not 0 <= limit <= 60000):
        raise ValueError("limit must be null or integer0..60000")
    if type(preview_limit) is not int or not 0 <= preview_limit <= 100:
        raise ValueError("preview_limit must be integer0..100")
    predicates = [] if predicates is None else predicates
    order_by = [] if order_by is None else order_by
    if not isinstance(predicates, list) or len(predicates) > 32:
        raise ValueError("predicates must be null or at most32AND conditions")
    if not isinstance(order_by, list) or len(order_by) > 8:
        raise ValueError("order_by must be null or at most8sort specifications")
    if fields is not None and (
        not isinstance(fields, list)
        or len(fields) > 256
        or any(not isinstance(k, str) or not k for k in fields)
        or len(set(fields)) != len(fields)
    ):
        raise ValueError("fields must be null or unique nonempty top-level names")
    binary = {"eq", "ne", "lt", "le", "gt", "ge", "in", "not_in"}
    unary = {"is_null", "is_not_null", "exists", "missing"}
    for p in predicates:
        if (
            not isinstance(p, dict)
            or set(p) - {"field", "op", "value"}
            or not isinstance(p.get("field"), str)
            or not p["field"]
            or p.get("op") not in binary | unary
        ):
            raise ValueError("Every predicate needs field and a documented op")
        op = p["op"]
        if (op in binary) != ("value" in p):
            raise ValueError(
                "Binary predicates require value;unary predicates must omit value"
            )
        if op in {"in", "not_in"}:
            if (
                not isinstance(p["value"], list)
                or not 1 <= len(p["value"]) <= 1000
                or not all(_scalar(v) for v in p["value"])
            ):
                raise ValueError("in/not_in needs1..1000JSON scalars")
        elif op in binary and not _scalar(p["value"]):
            raise ValueError("Binary predicate value must be a JSON scalar")
        if op in {"lt", "le", "gt", "ge"} and type(p["value"]) not in (int, float):
            raise ValueError("Ordered numeric predicates require finite numeric values")
    for key in order_by:
        if (
            not isinstance(key, dict)
            or set(key) - {"field", "direction", "nulls"}
            or not isinstance(key.get("field"), str)
            or not key["field"]
            or key.get("direction", "ascending") not in {"ascending", "descending"}
            or key.get("nulls", "last") not in {"first", "last"}
        ):
            raise ValueError("Invalid bounded sort specification")
    if len({k["field"] for k in order_by}) != len(order_by):
        raise ValueError("Sort keys must be distinct")
    document, records, digest = _load_records(records_file)
    verified_provenance = _verified_provenance(_public_source_path(records_file), digest)
    seen = set()
    for record in records:
        identity = record.get(id_field)
        if type(identity) not in (str, int) or identity == "" or identity in seen:
            raise ValueError("Every record requires a unique string or integer identity; no bool, float, null or implicit conversion")
        seen.add(identity)
        # Validation does not depend on AND predicate ordering. Explicit missing
        # discovery can be a separate query; missing is never silently null.
        for predicate in predicates:
            key, op = predicate["field"], predicate["op"]
            if op in {"exists", "missing"}:
                continue
            if key not in record:
                raise ValueError("Missing predicate field:" + key)
            value = record[key]
            if not _scalar(value):
                raise ValueError("Predicate fields must be scalar or explicit null")
            if (
                op in {"lt", "le", "gt", "ge"}
                and value is not None
                and type(value) not in (int, float)
            ):
                raise ValueError(
                    "Numeric comparison field must be numeric or null:" + key
                )

    def matches(row):
        for p in predicates:
            key, op = p["field"], p["op"]
            if op == "exists":
                passed = key in row
            elif op == "missing":
                passed = key not in row
            else:
                if key not in row:
                    raise ValueError(
                        "Missing predicate field:"
                        + key
                        + ";use explicit exists/missing if intended"
                    )
                value = row[key]
                if not _scalar(value):
                    raise ValueError("Predicate fields must be scalar or explicit null")
                if op == "is_null":
                    passed = value is None
                elif op == "is_not_null":
                    passed = value is not None
                elif op == "eq":
                    passed = _same(value, p["value"])
                elif op == "ne":
                    passed = not _same(value, p["value"])
                elif op in {"in", "not_in"}:
                    passed = any(_same(value, v) for v in p["value"])
                    passed = not passed if op == "not_in" else passed
                elif value is None:
                    passed = False
                else:
                    if type(value) not in (int, float):
                        raise ValueError(
                            "Numeric comparison field must be numeric or null:" + key
                        )
                    other = p["value"]
                    passed = {
                        "lt": lambda: value < other,
                        "le": lambda: value <= other,
                        "gt": lambda: value > other,
                        "ge": lambda: value >= other,
                    }[op]()
            if not passed:
                return False
        return True

    matching = [r for r in records if matches(r)]
    for key in order_by:
        name = key["field"]
        families = set()
        for r in matching:
            if name not in r:
                raise ValueError("Missing sort field:" + name)
            value = r[name]
            if not _scalar(value):
                raise ValueError("Sort fields must be scalar or null")
            if value is not None:
                families.add(
                    "number" if type(value) in (int, float) else type(value).__name__
                )
        if len(families) > 1:
            raise ValueError(
                "Non-null sort values must have one comparable JSON scalar type"
            )

    def compare(a, b):
        for key in order_by:
            x, y = a[key["field"]], b[key["field"]]
            if x is None and y is None:
                continue
            if x is None:
                return -1 if key.get("nulls", "last") == "first" else 1
            if y is None:
                return 1 if key.get("nulls", "last") == "first" else -1
            direction = -1 if key.get("direction", "ascending") == "descending" else 1
            if x < y:
                return -direction
            if x > y:
                return direction
        return 0

    ordered = (
        sorted(matching, key=functools.cmp_to_key(compare)) if order_by else matching
    )
    selected = ordered if limit is None else ordered[:limit]
    identity_set_sha256 = hashlib.sha256(
        json.dumps(
            sorted((row[id_field] for row in selected), key=lambda value: (type(value).__name__, str(value))),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    if fields is not None:
        requested = list(dict.fromkeys([id_field, *fields]))
        for row in selected:
            if any(k not in row for k in requested):
                raise ValueError("Selected record lacks a requested projection field")
        selected = [{key: r[key] for key in requested} for r in selected]
    query = {
        "source_sha256": digest,
        "id_field": id_field,
        "predicates": predicates,
        "fields": fields,
        "order_by": order_by,
        "limit": limit,
        "input_record_count": len(records),
        "matching_record_count": len(matching),
        "output_record_count": len(selected),
        "output_identity_set_sha256": identity_set_sha256,
    }
    parent = (
        {key: value for key, value in document.items() if key != "data"}
        if isinstance(document, dict)
        else None
    )
    output, output_sha = _write_record_artifact("record_query", selected, query, parent)
    preview, truncated = _preview(selected, preview_limit)
    return {
        "results_file": output,
        "results_sha256": output_sha,
        "source_sha256": digest,
        "verified_provenance": verified_provenance,
        "input_record_count": len(records),
        "matching_record_count": len(matching),
        "output_record_count": len(selected),
        "output_identity_set_sha256": identity_set_sha256,
        "limit_applied": len(selected) < len(matching),
        "record_id_field": id_field,
        "preview_records": preview,
        "preview_record_count": len(preview),
        "preview_truncated": truncated,
        "query": {
            "predicates": predicates,
            "fields": fields,
            "order_by": order_by,
            "limit": limit,
        },
        "scope": "Explicit record transformation only;null is distinct from missing;no inferred scientific selection or hypothesis family",
    }
