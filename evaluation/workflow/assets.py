"""Resolve a declared public asset without conflating equal basenames elsewhere."""
import hashlib
import json
import re
from pathlib import Path
from .values import MissingEvidence

ROOT = Path(__file__).resolve().parents[2]


def public_asset_paths(name, expected_sha256, historical_paths):
    """Return exact accepted spellings only after checking the released file bytes.

    Scientific identity is the declared content hash. Historical absolute paths
    remain explicit reviewed aliases; arbitrary directories are never stripped.
    """
    if (not isinstance(name, str) or not name or '/' in name or '\\' in name
        or name in {'.', '..'} or not isinstance(expected_sha256, str)
        or re.fullmatch('[0-9a-f]{64}', expected_sha256) is None
        or not isinstance(historical_paths, list) or len(historical_paths) > 32
        or any(not isinstance(p, str) or not p or len(p) > 4096 for p in historical_paths)):
        raise MissingEvidence('Public asset identity needs a filename, SHA256 and bounded reviewed aliases')
    try:
        root = ROOT.resolve()
        asset = (root/'tasks/assets'/name).resolve()
        inventory = json.loads((root/'tasks/asset_manifest.json').read_text())['files']
        if (asset.parent != root/'tasks/assets'
            or inventory[name]['sha256'] != expected_sha256
            or hashlib.sha256(asset.read_bytes()).hexdigest() != expected_sha256):
            raise MissingEvidence('Public asset content differs from the reviewed source')
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise MissingEvidence('Missing or invalid published asset identity') from error
    return list(dict.fromkeys([name, 'asset://'+name, 'tasks/assets/'+name,
                              str(asset)] + historical_paths))
