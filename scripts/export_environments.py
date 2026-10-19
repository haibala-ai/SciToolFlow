"""Save reproducible environment snapshots without account-specific credentials."""

from pathlib import Path
import json
import subprocess
import re
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
CONDA = Path("/data/wuchenmin/Application/anaconda3/bin/conda")


def main():
    summary = []
    for name in [
        "SciTool-Unified",
        "SciTool-LLM",
        "SciTool-RXN-Local",
        "SciTool-Chroma",
    ]:
        result = subprocess.run(
            [str(CONDA), "env", "export", "--name", name, "--no-builds"],
            capture_output=True,
            text=True,
            timeout=120,
            check=True,
        )
        lines = [
            line
            for line in result.stdout.splitlines()
            if not line.startswith("prefix:")
        ]
        # This machine's legacy environments contain no private pip index lines.
        urls = [
            urlsplit(url)
            for line in lines
            for url in re.findall(r"https?://[^\s]+", line)
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
        (ROOT / "configs/environments" / f"{name}.yml").write_text(
            "\n".join(lines) + "\n"
        )
        packages = subprocess.run(
            [str(CONDA), "list", "-n", name, "--json"],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )
        rows = json.loads(packages.stdout)
        summary.append(
            {
                "name": name,
                "packages": len(rows),
                "file": "configs/environments/" + name + ".yml",
            }
        )
    (ROOT / "configs/environments/manifest.json").write_text(
        json.dumps({"profiles": summary, "new_environment_created": False}, indent=2)
        + "\n"
    )
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
