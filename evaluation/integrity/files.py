"""Package-safe paths and content-verified file identities for scoring."""

from pathlib import Path
import hashlib, json


def safe_file(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if Path(relative).is_absolute() or root not in path.parents:
        raise ValueError("Package file escapes package root")
    return path


def manifest(root):
    return json.loads((Path(root) / "MANIFEST.json").read_text())


def verify_file_identities(root):
    """Validate declared attachment byte sizes and SHA256 identities."""
    root = Path(root).resolve()
    metadata = manifest(root)
    identities = json.loads(safe_file(root, metadata["file_identities"]).read_text())[
        "files"
    ]
    for item in identities.values():
        path = safe_file(root, item["file"])
        if (
            type(item.get("bytes")) is not int
            or item["bytes"] < 0
            or path.stat().st_size != item["bytes"]
        ):
            raise ValueError("Input/artifact identity byte size mismatch")
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError("Input/artifact identity hash mismatch")
    return len(identities)
