"""Selected source quality cannot be replaced by quota labels or duplicate rows."""
from copy import deepcopy
from pathlib import Path
import json
import pytest
from tasks.datasets import load_dataset
from evaluation.integrity.mini import validate_selection
ROOT=Path(__file__).resolve().parents[2]


def example():return load_dataset('mini'),json.loads((ROOT/'tasks/mini/selection.json').read_text())


def test_delivered_selection():
    data,selection=example();assert validate_selection(ROOT,data,selection)


def test_duplicates_cannot_fill_the_quota():
    data,s=example();s['tasks_review'][101]=deepcopy(s['tasks_review'][100])
    with pytest.raises(ValueError,match='unique'):validate_selection(ROOT,data,s)


def test_wrong_discipline_distribution_is_rejected():
    data,s=example();s['tasks_review'][100]['domain']='Material'
    with pytest.raises(ValueError,match='25 tasks'):validate_selection(ROOT,data,s)


def test_identical_branch_descriptions_are_not_two_workstreams():
    data,s=example();s['tasks_review'][100]['parallel_subtasks']=['one','one']
    with pytest.raises(ValueError,match='distinct'):validate_selection(ROOT,data,s)


def test_source_high_difficulty_cannot_be_hidden_by_a_standard_label():
    data,s=example();high=next(r['id'] for r in json.loads((ROOT/'tasks/full/index.json').read_text())['tasks'] if r['category']=='high_difficulty')
    row=s['tasks_review'][100];row['source_id']=high;row['category']='standard';data.source_ids[row['id']]=high
    with pytest.raises(ValueError,match='High-difficulty'):validate_selection(ROOT,data,s)
