"""Find or restore one historical file from the deduplicated local archive."""

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path", help="Original path relative to the former ToolKG workspace"
    )
    parser.add_argument(
        "--output", type=Path, help="Restore bytes to a new file; never overwrite"
    )
    args = parser.parse_args()
    archive_dir = ROOT / ".local/archive"
    index = json.loads((archive_dir / "history_index.json").read_text())
    record = index["files"].get(args.path)
    if record is None:
        parser.error("No retained historical file with that exact path")
    if args.output is None:
        print(
            json.dumps(
                {"original_path": args.path, **record}, ensure_ascii=False, indent=2
            )
        )
        return
    if args.output.exists():
        parser.error("Output exists; choose a new file")
    if "duplicate_of" in record:
        source = ROOT / record["duplicate_of"].removeprefix("SciToolFlow/")
        data = source.read_bytes()
    else:
        with tarfile.open(archive_dir / index["archive"], "r:gz") as archive:
            data = archive.extractfile(record["archive_member"]).read()
    if hashlib.sha256(data).hexdigest() != record["sha256"]:
        raise ValueError("History content hash differs")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as stream:
        stream.write(data)
    args.output.chmod(0o600)
    print(json.dumps({"restored": str(args.output), "sha256": record["sha256"]}))


if __name__ == "__main__":
    main()
