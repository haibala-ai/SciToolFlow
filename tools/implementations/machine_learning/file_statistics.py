"""File-based statistical transformations preserving complete hypothesis families."""

import hashlib
import json
import math
from pathlib import Path
import uuid

from tools.implementations.general.research_data import (
    _public_source_path,
    _strict_json,
    _task_artifacts_root,
)


def adjust_p_values_file(
    results_file: str,
    method: str = "bh",
    id_field: str = "gene_id",
    p_value_field: str = "p_value",
    eligibility_field: str | None = None,
) -> dict:
    """Adjust an entire file's eligible P-value family without selecting targets.

    Input is a JSON record list or an object with a data record list (1..60000
    rows; at most 25 MiB). IDs must be unique nonempty strings. Every row must
    contain p_value_field, which is null or a finite number in [0,1]. With no
    eligibility_field, every non-null P value is eligible. With an explicitly
    named eligibility_field, every row must contain a strict Boolean; only True
    rows enter the family, and True rows must have non-null valid P values.
    Null/False rows remain in the output with null adjusted_p_value. There is no
    target-ID, threshold, or row-subset argument. Missing hypotheses cannot be
    detected; eligibility must follow the study's predeclared testing policy.

    BH controls FDR under independence/positive dependence, BY is conservative
    under arbitrary dependence, and Bonferroni controls familywise error. All
    operations use the full eligible family and retain source order and fields.
    The complete result is written under the explicit task-local artifact root;
    only paths, SHA256 hashes and family diagnostics enter the model context.
    ReadScientificRecords can retrieve resulting rows by their exact IDs.
    """
    if method not in {"bh", "by", "bonferroni"}:
        raise ValueError("method must be bh, by, or bonferroni")
    for name, value in [("id_field", id_field), ("p_value_field", p_value_field)]:
        if not isinstance(value, str) or not value:
            raise ValueError(name + " must be a nonempty top-level field name")
    if eligibility_field is not None and (
        not isinstance(eligibility_field, str) or not eligibility_field
    ):
        raise ValueError("eligibility_field must be null or a nonempty field name")
    path = _public_source_path(results_file)
    if path.stat().st_size > 25 * 1024 * 1024:
        raise ValueError("Input JSON is limited to 25 MiB")
    artifact_root = _task_artifacts_root()
    raw = path.read_bytes()
    document = _strict_json(raw)
    records = document.get("data") if isinstance(document, dict) else document
    if (
        not isinstance(records, list)
        or not 1 <= len(records) <= 60000
        or any(not isinstance(row, dict) for row in records)
    ):
        raise ValueError(
            "Input requires 1..60000 record objects, optionally under data"
        )
    if isinstance(document, dict) and "adjustment" in document:
        raise ValueError(
            "Input already contains adjustment metadata; use original P-value results"
        )

    seen, valid, eligible_indices = set(), [], []
    null_count, excluded_valid_count = 0, 0
    for index, row in enumerate(records):
        identity = row.get(id_field)
        if not isinstance(identity, str) or not identity or identity in seen:
            raise ValueError("Every record needs a unique nonempty string identity")
        seen.add(identity)
        if "adjusted_p_value" in row:
            raise ValueError(
                "Input already contains adjusted_p_value; no silent overwrite"
            )
        if p_value_field not in row:
            raise ValueError("Missing P-value field: " + p_value_field)
        value = row[p_value_field]
        if value is not None and (
            type(value) not in (int, float)
            or not math.isfinite(value)
            or not 0 <= value <= 1
        ):
            raise ValueError("P values must be null or finite numbers in [0,1]")
        eligible = value is not None
        if eligibility_field is not None:
            flag = row.get(eligibility_field)
            if type(flag) is not bool:
                raise ValueError(
                    "Every eligibility field value must be a strict Boolean"
                )
            if flag and value is None:
                raise ValueError("Eligible records must have non-null valid P values")
            eligible = flag
        if value is None:
            null_count += 1
        elif not eligible:
            excluded_valid_count += 1
        if eligible:
            valid.append(float(value))
            eligible_indices.append(index)

    count = len(valid)
    adjusted = [None] * len(records)
    from .statistical_kernels import adjust_complete_family
    for index, value in zip(eligible_indices, adjust_complete_family(valid, method)):
        adjusted[index] = value

    output_records = [
        dict(row, adjusted_p_value=value) for row, value in zip(records, adjusted)
    ]
    source_sha = hashlib.sha256(raw).hexdigest()
    metadata = {
        "method": method,
        "id_field": id_field,
        "p_value_field": p_value_field,
        "eligibility_field": eligibility_field,
        "input_record_count": len(records),
        "family_size": count,
        "null_p_value_count": null_count,
        "excluded_valid_p_value_count": excluded_valid_count,
        "source_sha256": source_sha,
        "scope": "All eligible P values in the supplied complete file; no target subset or significance filtering",
        "assumptions": {
            "bh": "FDR control requires independence or suitable positive dependence",
            "by": "Conservative FDR control under arbitrary dependence",
            "bonferroni": "Familywise error control by the union bound",
        }[method],
    }
    output = dict(document) if isinstance(document, dict) else {}
    output.update(data=output_records, adjustment=metadata)
    encoded = (
        json.dumps(output, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        + "\n"
    ).encode()
    directory = artifact_root / "p_value_adjustment" / uuid.uuid4().hex
    directory.mkdir(parents=True)
    result_path = directory / "results.json"
    result_path.write_bytes(encoded)
    result_sha = hashlib.sha256(encoded).hexdigest()
    provenance = {
        "raw_sha256": result_sha,
        "source_sha256": source_sha,
        "operation": "AdjustPValuesFile",
        "method": method,
        "family_size": count,
        "eligibility_field": eligibility_field,
        "all_source_rows_retained": True,
    }
    result_path.with_suffix(".provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, allow_nan=False) + "\n"
    )
    return {
        "results_file": str(result_path),
        "results_sha256": result_sha,
        "source_sha256": source_sha,
        "method": method,
        "input_record_count": len(records),
        "family_size": count,
        "null_p_value_count": null_count,
        "excluded_valid_p_value_count": excluded_valid_count,
        "eligibility_field": eligibility_field,
        "record_id_field": id_field,
        "adjusted_p_value_field": "adjusted_p_value",
        "all_source_rows_retained": True,
        "assumptions": metadata["assumptions"],
    }
