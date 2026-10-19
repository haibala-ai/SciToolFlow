"""Hash source, data and bundled resources; exclude private runtime files."""

from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]


def main():
    selected = []
    for name in [
        "tasks",
        "evaluation",
        "baselines",
        "tools",
        "scitoolflow",
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
    for name in ["README.md", "pyproject.toml", "cli.py", "LICENSE"]:
        if (ROOT / name).exists():
            selected.append(ROOT / name)
    files = {
        str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest()
        for f in sorted(set(selected))
    }
    manifest = {
        "name": "SciToolFlow",
        "version": "0.3.0",
        "layout": "benchmark-first",
        "public_tasks": "tasks/questions.jsonl",
        "references": "evaluation/references.jsonl",
        "file_identities": "evaluation/file_identities.json",
        "scientific_tool_implementations_included": True,
        "scientific_tools": 546,
        "discovery_tools": 1,
        "private_credentials_excluded": True,
        "models_and_external_binary_resources_hashed_separately": False,
        "mutable_resource_directories": [".local", "results"],
        "requires_original_parent_checkout": False,
        "files": files,
    }
    (ROOT / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps({"hashed_files": len(files), "private_files_included": False}))


if __name__ == "__main__":
    main()
