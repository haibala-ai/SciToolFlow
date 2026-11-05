"""Portable public input assets; reference answers/traces are never bundled."""

import copy
import hashlib
import json
from pathlib import Path

from src.utils.paths import project_root


def load_agent_input(record, release=None):
    """Resolve an exported public row with strict path/hash checks; no tools/API."""
    release = Path(release or project_root() / "tasks/full").resolve()
    manifest = json.loads((release / "asset_manifest.json").read_text())["files"]

    def resolve(value):
        if isinstance(value, str):
            prefix = "qchem:" if value.startswith("qchem:asset://") else ""
            uri = value[len(prefix) :]
            if not uri.startswith("asset://"):
                return value
            name = uri[8:]
            if name not in manifest or Path(name).name != name:
                raise ValueError("Unknown or unsafe public asset")
            path = (release / "assets" / name).resolve()
            if path.parent != release / "assets":
                raise ValueError("Asset escapes release directory")
            if (
                hashlib.sha256(path.read_bytes()).hexdigest()
                != manifest[name]["sha256"]
            ):
                raise ValueError("Public asset hash mismatch")
            return prefix + str(path)
        if isinstance(value, list):
            return [resolve(v) for v in value]
        if isinstance(value, dict):
            return {k: resolve(v) for k, v in value.items()}
        return value

    result = resolve(copy.deepcopy(record))
    result["Parameter"] = json.dumps(
        result["inputs"], ensure_ascii=False, sort_keys=True, allow_nan=False
    )
    return result
