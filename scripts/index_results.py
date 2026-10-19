"""Index current trajectory locations without rewriting historical run evidence."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    experiments = []
    for file in sorted((ROOT / "results").glob("*/predictions.json")):
        data = json.loads(file.read_text())
        rows = []
        for row in data["predictions"]:
            original = row.get("trace_path")
            trace = None
            if original:
                suffix = (
                    original.split("/runs/", 1)[-1]
                    if "/runs/" in original
                    else original.split("/results/", 1)[-1]
                )
                candidate = ROOT / "results" / suffix
                if candidate.is_file():
                    digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
                    if row.get("trace_sha256") and digest != row["trace_sha256"]:
                        raise ValueError(
                            "Historical trajectory hash changed: " + row["id"]
                        )
                    trace = str(candidate.relative_to(ROOT))
            rows.append(
                {"id": row["id"], "completed": row["completed"], "trajectory": trace}
            )
        experiments.append(
            {
                "experiment": file.parent.name,
                "predictions": str(file.relative_to(ROOT)),
                "tasks": rows,
            }
        )
    index = {"historical_raw_paths_unchanged": True, "experiments": experiments}
    (ROOT / "results/index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "experiments": len(experiments),
                "indexed_predictions": sum(len(e["tasks"]) for e in experiments),
            }
        )
    )


if __name__ == "__main__":
    main()
