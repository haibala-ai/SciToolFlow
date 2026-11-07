"""Manifest-verified public attachments for planning and scientific grounding."""

import hashlib
import json
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from src.utils.paths import project_root

PUBLIC_ASSET_ROOT = ContextVar("scimas_public_asset_root", default=None)


@contextmanager
def public_asset_scope(root):
    """Bind an explicitly selected, manifest-verified public task package."""
    token = PUBLIC_ASSET_ROOT.set(Path(root).resolve())
    try:
        yield
    finally:
        PUBLIC_ASSET_ROOT.reset(token)


def asset_previews(task, asset_root, *, limit=12000):
    """Read only manifest-verified, explicitly attached public assets; label truncation."""
    asset_root = PUBLIC_ASSET_ROOT.get() or Path(asset_root)
    result = []
    manifest = json.loads((asset_root / "asset_manifest.json").read_text())["files"]
    directory = (asset_root / "assets").resolve()
    for name in task.get("files", []):
        path = Path(name).resolve()
        if path.parent != directory or path.name not in manifest:
            raise ValueError("Planner attachment is outside the public release")
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != manifest[path.name]["sha256"]:
            raise ValueError("Public asset changed")
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            result.append(
                {
                    "path": str(path),
                    "format": "binary",
                    "bytes": len(content),
                    "sha256": manifest[path.name]["sha256"],
                    "instruction": "If data are sourced from this binary file, use a documented scientific/file tool to read it. Complete values independently supplied in task.inputs may be used directly unless the task explicitly requires the file as the source.",
                }
            )
        else:
            result.append(
                {
                    "path": str(path),
                    "text": text[:limit],
                    "truncated": limit is not None and len(text) > limit,
                    "sha256": manifest[path.name]["sha256"],
                    "instruction": "Planning preview only, not an executed observation. If scientific data are sourced from this file, read it through a real tool and bind consumers to its output. Complete values independently supplied in task.inputs may be used directly unless the task explicitly requires the file as the source.",
                }
            )
    return result


def evidence_sources(task):
    sources = [
        task.get("question", ""),
        json.dumps(task.get("inputs", {}), ensure_ascii=False),
    ]
    if task.get("files"):
        sources.extend(
            a["text"]
            for a in asset_previews(task, project_root() / "tasks/full", limit=None)
            if "text" in a
        )
    return sources
