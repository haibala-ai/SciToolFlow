"""Install the bundled resource snapshot offline without replacing local changes."""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            value.update(block)
    return value.hexdigest()


def safe_path(base, relative):
    name = PurePosixPath(relative)
    if (
        name.is_absolute()
        or not name.parts
        or any(p in {"..", "."} for p in name.parts)
        or "\\" in relative
    ):
        raise ValueError("Invalid resource path: " + relative)
    path = base.joinpath(*name.parts)
    for parent in [base, *path.relative_to(base).parents]:
        candidate = parent if parent == base else base / parent
        if candidate.is_symlink():
            raise ValueError("Resource parent is a symlink: " + str(candidate))
    if path.is_symlink():
        raise ValueError("Resource is a symlink: " + str(path))
    return path


def source_parts(bundle, relative, record):
    """Resolve raw files or ordered chunks; verify every stored byte first."""
    parts = record.get("parts")
    if parts is None:
        parts = [
            {"path": relative, "bytes": record["bytes"], "sha256": record["sha256"]}
        ]
    if not parts or sum(part["bytes"] for part in parts) != record["bytes"]:
        raise ValueError("Invalid resource part sizes: " + relative)
    paths, whole = [], hashlib.sha256()
    for part in parts:
        path = safe_path(bundle, part["path"])
        if not path.is_file() or path.stat().st_size != part["bytes"]:
            raise ValueError(
                "Bundled resource failed SHA256 verification: " + part["path"]
            )
        checksum = hashlib.sha256()
        with path.open("rb") as stream:
            while block := stream.read(1024 * 1024):
                checksum.update(block)
                whole.update(block)
        if checksum.hexdigest() != part["sha256"]:
            raise ValueError(
                "Bundled resource failed SHA256 verification: " + part["path"]
            )
        paths.append(path)
    if whole.hexdigest() != record["sha256"]:
        raise ValueError("Reassembled resource failed SHA256 verification: " + relative)
    return paths


def prepare(bundle, destination, selected=None, check=False):
    bundle, destination = Path(bundle).absolute(), Path(destination).absolute()
    manifest = json.loads((bundle / "manifest.json").read_text())
    if manifest.get("schema_version") not in {
        "scitoolflow.resources.v1",
        "scitoolflow.resources.v2",
    }:
        raise ValueError("Unsupported resource manifest")
    available = {c["id"] for c in manifest["components"]}
    chosen = set(selected) if selected else available
    if chosen - available:
        raise ValueError(
            "Unknown resource components: " + ", ".join(sorted(chosen - available))
        )
    pending, conflicts, unchanged = [], [], 0
    # Validate the complete selection before writing any file.
    for relative, record in manifest["files"].items():
        if record["component"] not in chosen:
            continue
        sources = source_parts(bundle, relative, record)
        target = safe_path(destination, relative)
        if target.exists():
            if (
                target.is_file()
                and target.stat().st_size == record["bytes"]
                and digest(target) == record["sha256"]
            ):
                unchanged += 1
            else:
                conflicts.append(relative)
        else:
            pending.append((relative, sources, target, record))
    result = {
        "components": sorted(chosen),
        "destination": str(destination),
        "verified_existing": unchanged,
        "missing": len(pending),
        "conflicts": conflicts,
        "installed": 0,
        "network_requests": 0,
    }
    if check or conflicts:
        result["ready"] = not pending and not conflicts
        return result
    for relative, sources, target, record in pending:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=target.parent, prefix=".resource-", delete=False
            ) as output:
                temporary = Path(output.name)
                for source in sources:
                    with source.open("rb") as stream:
                        while block := stream.read(1024 * 1024):
                            output.write(block)
            if digest(temporary) != record["sha256"]:
                raise ValueError("Resource changed while copying: " + relative)
            temporary.chmod(0o755 if record.get("executable") else 0o644)
            # Git does not retain mtimes. Give copied build inputs the same
            # timestamp so Autotools does not regenerate a newer/older template
            # merely because files were copied in lexical order.
            epoch = int(manifest.get("install_mtime_epoch", 1700000000))
            os.utime(temporary, (epoch, epoch))
            # The temporary file shares the target filesystem. Linking creates
            # the destination atomically and fails if another writer got there.
            os.link(temporary, target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        result["installed"] += 1
    result.update(ready=True, missing=0)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=ROOT / ".local")
    parser.add_argument(
        "--component",
        action="append",
        help="Optional component ID; repeat for multiple selections",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify the installed snapshot without copying files",
    )
    args = parser.parse_args()
    result = prepare(ROOT / "resources", args.destination, args.component, args.check)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
