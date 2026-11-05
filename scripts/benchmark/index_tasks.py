"""Build a lightweight public task index; never read answers or reference paths."""

from collections import Counter
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def task_categories(root=ROOT):
    labels = {
        "高难度题": "high_difficulty",
        "工具组合题": "tool_composition",
        "正常题": "standard",
    }
    result = {}
    category = None
    for line in (root / "tasks/full/CATEGORIES.md").read_text().splitlines():
        if line.startswith("## "):
            category = labels.get(line[3:].strip())
        match = re.match(r"\| (FLOW-\d{4}) \|", line)
        if match:
            if category is None or match[1] in result:
                raise ValueError("Missing/duplicate task category")
            result[match[1]] = category
    return result


def main():
    tasks = [
        json.loads(line)
        for line in (ROOT / "tasks/full/questions.jsonl").read_text().splitlines()
        if line.strip()
    ]
    categories = task_categories()
    if set(categories) != {r["id"] for r in tasks}:
        raise ValueError("Category document must list every public task exactly once")
    entries = [
        {
            "id": row["id"],
            "domain": row["domain"],
            "category": categories[row["id"]],
            "line": line,
            "question_preview": row["question"][:160],
            "has_files": bool(row.get("files")),
        }
        for line, row in enumerate(tasks, 1)
    ]
    result = {
        "canonical_source": "tasks/full/questions.jsonl",
        "count": len(tasks),
        "categories": dict(sorted(Counter(categories.values()).items())),
        "domains": dict(sorted(Counter(row["domain"] for row in tasks).items())),
        "references_visible_to_agent": False,
        "tasks": entries,
    }
    (ROOT / "tasks/full/index.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps({"public_tasks": len(tasks), "domains": result["domains"]}))


if __name__ == "__main__":
    main()
