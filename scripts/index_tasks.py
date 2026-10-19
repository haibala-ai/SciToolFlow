"""Build a lightweight public task index; never read answers or reference paths."""

from collections import Counter
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    tasks = [
        json.loads(line)
        for line in (ROOT / "tasks/questions.jsonl").read_text().splitlines()
        if line.strip()
    ]
    entries = [
        {
            "id": row["id"],
            "domain": row["domain"],
            "line": line,
            "question_preview": row["question"][:160],
            "max_tool_calls": row["max_tool_calls"],
            "has_files": bool(row.get("files")),
        }
        for line, row in enumerate(tasks, 1)
    ]
    result = {
        "canonical_source": "tasks/questions.jsonl",
        "count": len(tasks),
        "domains": dict(sorted(Counter(row["domain"] for row in tasks).items())),
        "references_visible_to_agent": False,
        "tasks": entries,
    }
    (ROOT / "tasks/index.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps({"public_tasks": len(tasks), "domains": result["domains"]}))


if __name__ == "__main__":
    main()
