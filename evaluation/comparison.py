"""Presentation normalization and exact typed argument comparison."""

from pathlib import Path
import os, json, math, re
from scitoolflow.paths import project_root

ROOT = project_root()
DATA = Path(os.getenv("SCITOOLFLOW_DATA_ROOT", str(ROOT)))
ASSETS = DATA / "tasks/assets"
WORK = ROOT / "results"


def canonical(value):
    """Normalize presentation only; preserve data, units and full precision."""
    if isinstance(value, dict):
        return {k: canonical(v) for k, v in value.items()}
    if isinstance(value, list):
        return [canonical(v) for v in value]
    if isinstance(value, str):
        try:
            return canonical(json.loads(value))
        except (ValueError, TypeError):
            value = value.replace(str(ASSETS), "<ASSET_ROOT>")
            value = re.sub(
                re.escape(str(WORK)) + r"/[^/\s]+/files", "<ASSET_ROOT>", value
            )
            value = value.replace(str(ROOT), "<PROJECT_ROOT>")
            # Unit powers and chemical bond symbols are data, not Markdown.
            if re.search(r"(?m)^\s*(?:#{1,6}|\*\*[^*\n]+\*\*)", value):
                value = re.sub(r"(?m)^\s*#{1,6}\s*", "", value)
                value = value.replace("**", "").replace("`", "")
            return re.sub(r"\s+", " ", value).strip()
    return value


def arguments_equal(tool, expected, actual):
    """Exact typed arguments; semantic rewordings/conversions need independent review.

    Never equate programs/questions by their numeric tokens or omit a limit/default
    merely because it is optional. File identities are normalized before this function.
    """

    def equal(a, b):
        if isinstance(a, bool) or a is None:
            return type(a) is type(b) and a == b
        if isinstance(a, (int, float)):
            return (
                not isinstance(b, bool)
                and isinstance(b, (int, float))
                and math.isfinite(a)
                and math.isfinite(b)
                and a == b
            )
        if isinstance(a, dict):
            return (
                isinstance(b, dict)
                and set(a) == set(b)
                and all(equal(a[k], b[k]) for k in a)
            )
        if isinstance(a, list):
            return (
                isinstance(b, list)
                and len(a) == len(b)
                and all(equal(x, y) for x, y in zip(a, b))
            )
        if isinstance(a, str):
            return isinstance(b, str) and a == b
        return type(a) is type(b) and a == b

    return equal(expected, actual)
