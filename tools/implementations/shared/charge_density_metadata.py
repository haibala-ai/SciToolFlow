"""Read genuine legacy file/task metadata from official public CHGCAR object envelopes."""

from scitoolflow.paths import local_root, artifacts_root
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile

import requests

from tools.implementations.shared.materials_api import MissingScientificData

BASE_URL = "https://materialsproject-parsed.s3.amazonaws.com/chgcars/"
LEGACY_BASE_URL = (
    "https://materialsproject-parsed.s3.amazonaws.com/mp-volumetric-chgcars/"
)


def canonical_task(task_id):
    value = task_id.strip(" \"'")
    if value.startswith("task_id="):
        value = value.split("=", 1)[1].strip()
    if re.fullmatch(r"mp-[0-9]+", value):
        return "mp-" + str(int(value[3:]))
    if re.fullmatch(r"[a-z]{1,12}", value):
        from emmet.core.mpid import AlphaID

        return "mp-" + str(int(AlphaID(value)))
    raise ValueError(
        "Expected a numeric mp-task ID or its unprefixed alphabetical task representation"
    )


def cache_directory():
    default = local_root() / "data/mp_charge_density_metadata"
    return Path(os.getenv("SCITOOL_CHARGE_METADATA_CACHE", str(default)))


def digest(record):
    fields = {
        key: record[key]
        for key in ["task_id", "fs_id", "source_url", "sha256_download", "fetched_at"]
    }
    return hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()


def read_verified(path):
    try:
        record = json.loads(path.read_text())
        if (
            re.fullmatch(r"mp-[0-9]+", record["task_id"])
            and re.fullmatch(r"[0-9a-f]{24}", record["fs_id"])
            and record["source_url"] == BASE_URL + record["task_id"] + ".json.gz"
            and record["metadata_sha256"] == digest(record)
            and record["verified_data_class"] == "Chgcar"
        ):
            datetime.fromisoformat(record["fetched_at"])
            return record
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def metadata_for_task(task_id):
    task = canonical_task(task_id)
    path = cache_directory() / (task + ".json")
    cached = read_verified(path)
    if cached:
        age = (
            datetime.now(timezone.utc) - datetime.fromisoformat(cached["fetched_at"])
        ).total_seconds()
        if 0 <= age <= 86400:
            return dict(cached, lookup_mode="verified_cache")
    url = BASE_URL + task + ".json.gz"
    with requests.Session() as session:
        # The public S3 route was verified with the normal environment proxy.
        # Keep this separate from the authenticated REST client's direct route.
        session.trust_env = os.getenv("SCITOOL_MP_OBJECT_USE_PROXY", "1") == "1"
        with session.get(url, timeout=(10, 45), stream=True) as response:
            if response.status_code == 404:
                raise MissingScientificData(
                    f"No published charge-density object for {task}; historical coverage is incomplete"
                )
            response.raise_for_status()
            parts, size = [], 0
            for part in response.iter_content(1024 * 1024):
                size += len(part)
                if size > 64 * 1024 * 1024:
                    raise MissingScientificData(
                        "Public charge-density metadata retrieval exceeds the 64 MiB compressed download budget"
                    )
                parts.append(part)
            content = b"".join(parts)
            sha = hashlib.sha256(content).hexdigest()
            if content[:2] == b"\x1f\x8b":
                with gzip.GzipFile(fileobj=io.BytesIO(content)) as archive:
                    raw = archive.read(512 * 1024 * 1024 + 1)
                if len(raw) > 512 * 1024 * 1024:
                    raise MissingScientificData(
                        "Charge-density envelope exceeds the 512 MiB decompression budget"
                    )
            else:
                raw = content
            envelope = json.loads(raw)
            if canonical_task(str(envelope.get("task_id", ""))) != task:
                raise MissingScientificData(
                    "Published object envelope task_id does not match the requested task"
                )
            file_id = envelope.get("fs_id")
            if not isinstance(file_id, str) or not re.fullmatch(
                r"[0-9a-f]{24}", file_id
            ):
                raise MissingScientificData(
                    "Published charge-density envelope has no valid legacy fs_id"
                )
            if envelope.get("data", {}).get("@class") != "Chgcar":
                raise MissingScientificData(
                    "Published object is not a serialized Chgcar"
                )
            record = {
                "task_id": task,
                "fs_id": file_id,
                "source_url": url,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "sha256_download": sha,
                "object_last_modified": response.headers.get("Last-Modified"),
                "verified_data_class": "Chgcar",
                "metadata_source": "top-level official object envelope",
                "scope": "Public historical object coverage is incomplete; this is the genuine legacy fs_id, not an invented S3 identifier",
            }
    record["metadata_sha256"] = digest(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", dir=path.parent, encoding="utf-8", delete=False
    ) as temporary:
        temporary.write(json.dumps(record, indent=2) + "\n")
        temporary_path = Path(temporary.name)
    temporary_path.replace(path)
    return dict(record, lookup_mode="live_public_object")


def metadata_for_file(fs_id):
    file_id = fs_id.strip(" \"'").lower()
    if not re.fullmatch(r"[0-9a-f]{24}", file_id):
        raise ValueError("Expected a 24-character hexadecimal historical file ID")
    matches = [
        record
        for path in cache_directory().glob("mp-*.json")
        if (record := read_verified(path)) and record["fs_id"] == file_id
    ]
    if len(matches) > 1:
        raise MissingScientificData(
            "Multiple verified task mappings found; refusing to select one arbitrarily"
        )
    if matches:
        return dict(
            matches[0],
            lookup_mode="verified_reverse_cache",
            reverse_lookup_scope="Previously verified official envelope; published historical coverage is incomplete",
        )
    url = LEGACY_BASE_URL + file_id
    with requests.Session() as session:
        session.trust_env = os.getenv("SCITOOL_MP_OBJECT_USE_PROXY", "1") == "1"
        with session.head(url, timeout=(10, 25)) as response:
            if response.status_code == 404:
                raise MissingScientificData(
                    "No published legacy object or verified cached mapping for this fs_id. "
                    "Historical archive coverage is incomplete; this does not prove the ID never existed."
                )
            response.raise_for_status()
            header_file_id = response.headers.get("x-amz-meta-fs_id")
            header_task_id = response.headers.get("x-amz-meta-task_id")
            if header_file_id != file_id or not header_task_id:
                raise MissingScientificData(
                    "Public legacy object has no matching fs_id/task_id header metadata"
                )
            task = canonical_task(header_task_id)
            record = {
                "fs_id": file_id,
                "task_id": task,
                "source_url": url,
                "lookup_mode": "live_legacy_object_headers",
                "metadata_source": "official S3 HEAD response",
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "object_last_modified": response.headers.get("Last-Modified"),
                "object_etag": response.headers.get("ETag"),
                "source_headers": {"fs_id": header_file_id, "task_id": header_task_id},
                "scope": "Verified live legacy-object metadata; public historical coverage is incomplete",
            }
    record["header_metadata_sha256"] = hashlib.sha256(
        json.dumps(record["source_headers"], sort_keys=True).encode()
    ).hexdigest()
    return record
