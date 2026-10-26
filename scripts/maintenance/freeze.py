"""Hash source, data and bundled resources; exclude private runtime files."""

from pathlib import Path
import hashlib
import json
from src import __version__
from tools.catalog.counts import tool_counts

ROOT = Path(__file__).resolve().parents[2]


def main():
    catalog = json.loads((ROOT / "tools/catalog/catalog.json").read_text())["tools"]
    selected = []
    for name in [
        "tasks",
        "evaluation",
        "baselines",
        "tools",
        "src",
        "configs",
        "tests",
        "scripts",
        "docs",
        "resources",
    ]:
        for file in (ROOT / name).rglob("*"):
            relative = file.relative_to(ROOT)
            generated = any(part.endswith(".egg-info") for part in relative.parts)
            if (
                file.is_file()
                and not file.is_symlink()
                and not generated
                and "__pycache__" not in file.parts
                and file.suffix != ".pyc"
                and not file.name.startswith(".")
            ):
                selected.append(file)
    for name in [
        "README.md",
        "pyproject.toml",
        "cli.py",
        "LICENSE",
        ".gitignore",
        ".gitattributes",
        "results/README.md",
    ]:
        if (ROOT / name).exists():
            selected.append(ROOT / name)
    files = {
        str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest()
        for f in sorted(set(selected))
    }
    manifest = {
        "name": "SciToolFlow",
        "version": __version__,
        "layout": "benchmark-first-modular",
        "public_tasks": "tasks/questions.jsonl",
        "references": "evaluation/data/references.jsonl.gz",
        "file_identities": "evaluation/data/file_identities.json",
        "scientific_tool_implementations_included": True,
        **tool_counts(catalog),
        "private_credentials_excluded": True,
        "mutable_resource_directories": [".local", "results"],
        "files": files,
    }
    (ROOT / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps({"hashed_files": len(files), "private_files_included": False}))


if __name__ == "__main__":
    main()
