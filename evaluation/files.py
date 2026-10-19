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


def normalizer(root):
    """Only equal, hash-verified declared input/artifact bytes share an identity."""
    root = Path(root).resolve()
    metadata = manifest(root)
    identities = json.loads(safe_file(root, metadata["file_identities"]).read_text())[
        "files"
    ]
    replacements = {}
    by_digest = {}
    sizes = set()
    for uri, item in identities.items():
        path = safe_file(root, item["file"])
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError("Input/artifact identity hash mismatch")
        identity = "sha256:" + item["sha256"]
        replacements[str(path)] = identity
        replacements[uri] = identity
        by_digest[item["sha256"]] = identity
        sizes.add(item["bytes"])
        for origin in item.get("origin_paths", []):
            replacements[origin] = identity
    ordered = sorted(replacements, key=len, reverse=True)

    def normalize(value):
        if isinstance(value, dict):
            return {k: normalize(v) for k, v in value.items()}
        if isinstance(value, list):
            return [normalize(v) for v in value]
        if not isinstance(value, str):
            return value
        for origin in ordered:
            value = value.replace(origin, replacements[origin])
        # A driver may copy an explicitly supplied input to its own workdir.
        # Compare its actual bytes; a shared basename never establishes identity.
        prefix = "qchem:" if value.startswith("qchem:") else ""
        candidate = value[len(prefix) :]
        if len(candidate) < 4096 and candidate.startswith("/"):
            path = Path(candidate)
            try:
                if path.is_file() and path.stat().st_size in sizes:
                    identity = by_digest.get(
                        hashlib.sha256(path.read_bytes()).hexdigest()
                    )
                    if identity:
                        return prefix + identity
            except OSError:
                pass
        return value

    return normalize
