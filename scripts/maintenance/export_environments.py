"""Export the four Conda profiles without local paths or embedded credentials."""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
ENVIRONMENTS = (
    "SciTool-Unified",
    "SciTool-LLM",
    "SciTool-RXN-Local",
    "SciTool-Chroma",
)


def resolve_conda(explicit=None):
    """Resolve Conda from a CLI override, the active installation or PATH."""
    configured = explicit or os.getenv("CONDA_EXE")
    if configured:
        candidate = shutil.which(str(configured)) or str(Path(configured).expanduser())
        path = Path(candidate)
        if not path.is_file() or not os.access(path, os.X_OK):
            raise ValueError("Configured Conda executable is unavailable")
        return path.resolve()
    found = shutil.which("conda")
    if found:
        return Path(found).resolve()
    prefix = Path(sys.prefix)
    base = prefix.parent.parent if prefix.parent.name == "envs" else prefix
    candidate = base / "bin/conda"
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return candidate.resolve()
    raise ValueError(
        "Conda was not found; activate Conda or supply --conda /path/to/conda"
    )


def export_profile(conda, name):
    result = subprocess.run(
        [str(conda), "env", "export", "--name", name, "--no-builds"],
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    lines = [
        line for line in result.stdout.splitlines() if not line.startswith("prefix:")
    ]
    urls = [
        urlsplit(url) for line in lines for url in re.findall(r"https?://[^\s]+", line)
    ]
    if any(
        url.username
        or url.password
        or re.search(r"(token|key|secret)=", url.query, re.I)
        for url in urls
    ):
        raise ValueError(
            "Credential-bearing URL in environment export requires redaction"
        )
    packages = subprocess.run(
        [str(conda), "list", "-n", name, "--json"],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return "\n".join(lines) + "\n", len(json.loads(packages.stdout))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--conda", help="Conda executable; otherwise use CONDA_EXE or PATH"
    )
    args = parser.parse_args(argv)
    conda = resolve_conda(args.conda)
    # Collect and check every export before replacing any checked-in profile.
    exports = [(name, *export_profile(conda, name)) for name in ENVIRONMENTS]
    summary = []
    for name, text, packages in exports:
        relative = f"configs/environments/{name}.yml"
        (ROOT / relative).write_text(text)
        summary.append({"name": name, "packages": packages, "file": relative})
    (ROOT / "configs/environments/manifest.json").write_text(
        json.dumps({"profiles": summary}, indent=2) + "\n"
    )
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
