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
        root = ROOT.resolve(); accepted=[]
        for release in [root/'tasks/full',root/'tasks/mini']:
            manifest=release/'asset_manifest.json'
            if not manifest.is_file():continue
            inventory=json.loads(manifest.read_text())['files']
            if name not in inventory or inventory[name]['sha256']!=expected_sha256:continue
            asset=(release/'assets'/name).resolve()
            if (asset.parent!=release/'assets'
                or hashlib.sha256(asset.read_bytes()).hexdigest()!=expected_sha256):
                raise MissingEvidence('Public asset content differs from the reviewed source')
            relative=str((release/'assets'/name).relative_to(root))
            accepted.extend([relative,str(asset)])
            if release == root/'tasks/full':
                previous = root/'tasks/assets'/name
                accepted.extend([str(previous.relative_to(root)),str(previous)])
        if not accepted:raise MissingEvidence('Missing matching published asset identity')
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise MissingEvidence('Missing or invalid published asset identity') from error
    return list(dict.fromkeys([name,'asset://'+name]+accepted+historical_paths))
