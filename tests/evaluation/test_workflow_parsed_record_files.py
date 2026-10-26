import copy
import pytest
from evaluation.workflow import MissingEvidence, operand


def resolve(value):
    return operand(
        {"operation": "complete_record_rows", "args": [{"value": value}]}, {}
    )


def parsed():
    return {
        "document": {
            "metadata": {"scope": "public observations"},
            "data": [{"id": "x", "value": 1}, {"id": "y", "value": None}],
        },
        "source_file": "/public/study.json",
        "source_sha256": "a" * 64,
    }


def test_full_source_bound_parsed_file_retains_null_and_order():
    assert resolve(parsed()) == [{"id": "x", "value": 1}, {"id": "y", "value": None}]


@pytest.mark.parametrize(
    "change",
    [
        {"source_file": ""},
        {"source_file": None},
        {"source_sha256": None},
        {"source_sha256": "not-a-hash"},
        {"source_sha256": "A" * 64},
        {"document": {"records": [{"id": "x"}]}},
        {"document": {"data": {"id": "x"}}},
        {"document": {"data": [1]}},
        {"document": {"data": [{"id": "x", "value": float("nan")}]}},
        {
            "records": [{"id": "x"}],
            "truncated": False,
            "returned_record_count": 1,
            "matching_record_count": 1,
        },
        {
            "preview_records": [],
            "preview_truncated": False,
            "limit_applied": False,
            "preview_record_count": 0,
            "output_record_count": 0,
            "matching_record_count": 0,
        },
    ],
)
def test_incomplete_ambiguous_or_nonfinite_file_envelope_rejected(change):
    x = copy.deepcopy(parsed())
    x.update(change)
    with pytest.raises(MissingEvidence):
        resolve(x)


def test_inline_json_is_not_claimed_as_a_source_hashed_file():
    with pytest.raises(MissingEvidence):
        resolve({"document": {"data": [{"id": "x"}]}})


def test_complete_empty_file_is_distinct_from_missing_data():
    x = parsed()
    x["document"]["data"] = []
    assert resolve(x) == []


def test_size_limit_preserved_for_full_file_route():
    x = parsed()
    x["document"]["data"] = [{"id": str(i)} for i in range(1001)]
    with pytest.raises(MissingEvidence):
        resolve(x)
