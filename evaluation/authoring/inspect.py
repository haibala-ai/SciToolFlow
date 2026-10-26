"""Inspect one private reference as a benchmark author; never an actor tool."""

import argparse, json
from pathlib import Path
from src.utils.io import read_jsonl


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--task", required=True)
    p.add_argument(
        "--section",
        choices=["reference", "evaluation", "expected_answer", "review", "trace"],
        default="reference",
    )
    a = p.parse_args()
    root = Path(__file__).resolve().parents[2]
    metadata = json.loads((root / "MANIFEST.json").read_text())
    name = metadata.get("references", "evaluation/data/references.jsonl.gz")
    rows = read_jsonl(root / name)
    reference = next((r for r in rows if r["id"] == a.task), None)
    if reference is None:
        p.error("Unknown task ID")
    value = reference
    if a.section in {"evaluation", "expected_answer"}:
        value = reference[a.section]
    elif a.section == "review":
        value = reference["review"]["record"]
    elif a.section == "trace":
        from evaluation.integrity.traces import read_trajectory

        value = read_trajectory(root / reference["reference_trace"])
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
