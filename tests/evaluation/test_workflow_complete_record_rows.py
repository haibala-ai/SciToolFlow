"""Equivalent complete record transports never admit truncated previews."""

import pytest
from evaluation.workflow import MissingEvidence, operand


def resolve(x):
    return operand({"operation": "complete_record_rows", "args": [{"value": x}]}, {})


def read():
    return {
        "records": [{"id": "A", "value": 1.5}],
        "truncated": False,
        "returned_record_count": 1,
        "matching_record_count": 1,
    }


def query():
    return {
        "preview_records": [{"id": "A", "value": 1.5}],
        "preview_truncated": False,
        "limit_applied": False,
        "preview_record_count": 1,
        "output_record_count": 1,
        "matching_record_count": 1,
    }


def test_complete_transports_preserve_exact_values():
    assert resolve(read()) == resolve(query()) == [{"id": "A", "value": 1.5}]


@pytest.mark.parametrize(
    "field,value",
    [
        ("preview_truncated", True),
        ("limit_applied", True),
        ("preview_record_count", 0),
        ("output_record_count", 2),
        ("matching_record_count", 2),
        ("matching_record_count", True),
    ],
)
def test_incomplete_or_inconsistent_query_never_becomes_evidence(field, value):
    x = query()
    x[field] = value
    with pytest.raises(MissingEvidence):
        resolve(x)


def test_incomplete_read_and_nonfinite_values_rejected():
    for x in [
        {**read(), "truncated": True},
        {**read(), "returned_record_count": None},
        {**read(), "records": [{"v": float("nan")}]},
    ]:
        with pytest.raises(MissingEvidence):
            resolve(x)


def test_normalized_records_support_explicit_nested_pointer_without_decoding():
    document = {"operation": "complete_record_rows", "args": [{"value": query()}]}
    assert (
        operand(
            {
                "operation": "value_at_pointer",
                "args": [document, {"value": "/0/value"}],
            },
            {},
        )
        == 1.5
    )


@pytest.mark.parametrize("path", ["0/value", "/bad~2key"])
def test_pointer_syntax_is_not_guessed(path):
    with pytest.raises(MissingEvidence):
        operand(
            {
                "operation": "value_at_pointer",
                "args": [{"value": {"a": 1}}, {"value": path}],
            },
            {},
        )
