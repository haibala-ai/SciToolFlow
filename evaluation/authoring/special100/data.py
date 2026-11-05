"""Load only public Special-100 questions and hash-verified input assets."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
BASE=Path(__file__).resolve().parent
from tasks.assets import load_agent_input
from tasks.datasets import select_tasks


def load_tasks(selection='all',*,resolve=True):
    tasks=[json.loads(line) for line in (BASE/'questions.jsonl').read_text().splitlines() if line]
    selected=select_tasks(tasks,selection)
    return [load_agent_input(t,BASE) for t in selected] if resolve else selected
