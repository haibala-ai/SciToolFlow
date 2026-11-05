"""Small JSON I/O helpers shared by the benchmark components."""

from pathlib import Path
import json, os
import gzip
import tempfile


def read_jsonl(path):
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def atomic_json(path, value, *, indent=2):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Independent tasks may encode the same retrieval context concurrently.
    # Each writer needs its own staging file even when the final key is shared.
    descriptor, name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=path.parent
    )
    temp = Path(name)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(
                value,
                stream,
                ensure_ascii=False,
                indent=indent,
                allow_nan=False,
                separators=(",", ":") if indent is None else None,
            )
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)
