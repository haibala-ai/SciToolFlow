"""Read public structured source records without exposing private project files."""

import hashlib
import json
import math
import os
from pathlib import Path


def read_scientific_records(
    snapshot_file: str,
    identifiers: list[str] | None = None,
    id_field: str = "material_id",
    fields: list[str] | None = None,
    max_records: int = 100,
) -> dict:
    """Read selected records/fields from a genuine frozen JSON source response.

    Args:
        snapshot_file (str): Uploaded JSON file containing a list of records or an
            object with a ``data`` record list. Relative paths use upload context
            or the explicitly configured task-local artifact directory.
        identifiers (list[str] | None): Exact values of id_field to retain; null
            reads all records. No approximate identifiers or live API fallback.
        id_field (str): Explicit top-level record identity field, for example
            material_id or an explicitly declared local snapshot key. Duplicate selected identities are errors.
        fields (list[str] | None): Exact top-level keys to include; missing keys
            are reported, never silently converted to zero. Null retains all keys.
        max_records (int): Maximum output records in [1,1000]; truncation explicit.

    Returns:
        dict: Records, count/truncation, missing IDs/fields, observed top-level
            available_fields and field_types (including null), local source SHA256,
            and optional verified sibling provenance (``*.provenance.json``).
            Provenance is accepted only when its raw_sha256 matches this file.
            Units and calculation methods remain those of original record fields;
            no method or experimental status is inferred from numeric values.
    """
    if not isinstance(snapshot_file, str) or not snapshot_file:
        raise ValueError("snapshot_file must be a nonempty path string")
    path = _public_source_path(snapshot_file)
    if path.stat().st_size > 25 * 1024 * 1024:
        raise ValueError("Snapshot JSON is limited to 25 MiB")
    if type(max_records) is not int or not 1 <= max_records <= 1000:
        raise ValueError("max_records must be an integer in [1,1000]")
    if not isinstance(id_field, str) or not id_field:
        raise ValueError("id_field must be a nonempty top-level field name")
    for value, label in [(identifiers, "identifiers"), (fields, "fields")]:
        if value is not None and (
            not isinstance(value, list)
            or not all(isinstance(v, str) and v for v in value)
        ):
            raise ValueError(label + " must be null or a list of nonempty strings")
    raw = path.read_bytes()
    document = _strict_json(raw)
    records = document.get("data") if isinstance(document, dict) else document
    if not isinstance(records, list) or not all(
        isinstance(record, dict) for record in records
    ):
        raise ValueError(
            "Snapshot must contain a list of record objects or a data list"
        )

    def json_type(value):
        if value is None:
            return "null"
        if type(value) is bool:
            return "boolean"
        if type(value) is int:
            return "integer"
        if type(value) is float:
            return "number"
        if isinstance(value, str):
            return "string"
        if isinstance(value, list):
            return "array"
        return "object"

    observed_types = {}
    for record in records:
        for field, value in record.items():
            observed_types.setdefault(field, set()).add(json_type(value))
    if len(observed_types) > 4096:
        raise ValueError("Snapshot schema exceeds 4096 observed top-level fields")
    available_fields = sorted(observed_types)
    field_types = {field: sorted(observed_types[field]) for field in available_fields}
    wanted = set(identifiers) if identifiers is not None else None
    selected, seen = [], set()
    for record in records:
        identity = record.get(id_field)
        if identity is None:
            # Report only public schema, never record values or inferred IDs.
            # The generic default is an MP key; other disciplines must be able
            # to recover the real source key without repeatedly guessing.
            preview = repr(available_fields[:16])[:1200]
            raise ValueError(
                "Source record lacks explicit identity field: " + id_field
                + ". Set id_field to an actual source key. Available top-level fields: "
                + preview
                + (" (schema truncated)" if len(available_fields) > 16 else "")
            )
        identity = str(identity)
        if wanted is not None and identity not in wanted:
            continue
        if identity in seen:
            raise ValueError(
                "Snapshot contains duplicate selected identity: " + identity
            )
        seen.add(identity)
        selected.append(record)
    output_records, missing_fields = [], {}
    for record in selected[:max_records]:
        if fields is None:
            output_records.append(record)
        else:
            output_records.append(
                {
                    k: record[k]
                    for k in dict.fromkeys([id_field] + fields)
                    if k in record
                }
            )
            absent = [k for k in fields if k not in record]
            if absent:
                missing_fields[str(record[id_field])] = absent
    sha = hashlib.sha256(raw).hexdigest()
    provenance_path = path.with_suffix(".provenance.json")
    provenance = None
    if provenance_path.is_file() and _is_public_source(provenance_path):
        if provenance_path.stat().st_size > 1024 * 1024:
            raise ValueError("Provenance metadata exceeds 1 MiB")
        provenance = _strict_json(provenance_path.read_text())
        if not isinstance(provenance, dict) or provenance.get("raw_sha256") != sha:
            raise ValueError("Snapshot/provenance SHA256 mismatch")
    return {
        "records": output_records,
        "available_fields": available_fields,
        "field_types": field_types,
        "matching_record_count": len(selected),
        "returned_record_count": len(output_records),
        "truncated": len(selected) > max_records,
        "missing_identifiers": sorted(wanted - seen) if wanted is not None else [],
        "missing_fields": missing_fields,
        "source_file": path.name,
        "source_sha256": sha,
        "verified_provenance": provenance,
        "limitations": [
            "Frozen records are not a live API result",
            "No missing value, units, method, or experimental status is inferred",
        ],
    }


def _strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key: " + key)
            result[key] = value
        return result

    def constant(value):
        raise ValueError("Nonfinite/nonstandard JSON number: " + value)

    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("Nonfinite JSON numeric value")
        return number

    return json.loads(
        raw, object_pairs_hook=pairs, parse_constant=constant, parse_float=finite_float
    )


def _is_public_source(path):
    from src.utils.paths import project_root
    from tools.runtime.config import Config

    resolved = path.resolve()
    assets = (project_root() / "tasks/full/assets").resolve()
    explicit_uploads = {
        Path(item).resolve() for item in Config().ALL_UPLOAD_FILES_PATHS
    }
    artifact_root = _task_artifacts_root(required=False)
    return (
        resolved in explicit_uploads
        or resolved.is_relative_to(assets)
        or (artifact_root is not None and resolved.is_relative_to(artifact_root))
    )


def _task_artifacts_root(required=True):
    """Return only an explicit, bounded task directory, never a shared fallback.

    The harness controls this environment variable per task/process. Model input
    cannot choose a read root. Real-path containment prevents symlink escapes.
    Do not use artifacts_root(): its default is shared across tasks.
    """
    from src.utils.paths import project_root

    value = os.getenv("SCITOOLFLOW_ARTIFACTS_DIR")
    if not value:
        if required:
            raise ValueError(
                "An explicit task-local SCITOOLFLOW_ARTIFACTS_DIR is required"
            )
        return None
    original = Path(value).expanduser()
    if not original.is_absolute():
        raise ValueError(
            "SCITOOLFLOW_ARTIFACTS_DIR must be an absolute task-local directory"
        )
    root = original.resolve()
    project = project_root().resolve()
    shared = (project / "results/tool_artifacts").resolve()
    forbidden = {
        Path("/"),
        Path("/tmp"),
        Path("/var/tmp"),
        Path.home().resolve(),
        project,
        project / "results",
        project / ".local",
        shared,
    }
    if root in forbidden or project.is_relative_to(root):
        raise ValueError(
            "SCITOOLFLOW_ARTIFACTS_DIR must not be a shared or broad filesystem root"
        )
    if not root.is_dir():
        raise ValueError(
            "SCITOOLFLOW_ARTIFACTS_DIR must be an existing task-local directory"
        )
    return root


def _public_source_path(name):
    from tools.runtime.config import Config

    if not isinstance(name, str) or not name:
        raise ValueError("Source path must be a nonempty string")
    path = Path(name)
    if not path.is_absolute():
        matches = [
            Path(item)
            for item in Config().ALL_UPLOAD_FILES_PATHS
            if Path(item).name == name
        ]
        if len(matches) > 1:
            raise ValueError("Ambiguous uploaded basename; use an explicit path")
        if matches:
            path = matches[0]
        else:
            candidates = [Path(Config().UPLOAD_FILES_BASE_PATH) / path]
            artifact_root = _task_artifacts_root(required=False)
            if artifact_root is not None:
                candidates.append(artifact_root / path)
            existing = {
                candidate.resolve()
                for candidate in candidates
                if candidate.is_file() and _is_public_source(candidate)
            }
            if len(existing) > 1:
                raise ValueError("Ambiguous source path; use an explicit path")
            path = next(iter(existing)) if existing else candidates[0]
    if not _is_public_source(path):
        raise PermissionError(
            "Only public task assets, explicitly uploaded files, and explicit task-local artifacts may be read"
        )
    if not path.is_file():
        raise FileNotFoundError(str(path))
    return path.resolve()


def _verified_provenance(path, sha):
    """Verify a readable public sibling without accepting unbound provenance."""
    sibling = path.with_suffix('.provenance.json')
    if not sibling.is_file() or not _is_public_source(sibling):
        return None
    if sibling.stat().st_size > 1024 * 1024:
        raise ValueError('Provenance metadata exceeds1MiB')
    record = _strict_json(sibling.read_bytes())
    if not isinstance(record, dict) or record.get('raw_sha256') != sha:
        raise ValueError('Snapshot/provenance SHA256 mismatch')
    return record
