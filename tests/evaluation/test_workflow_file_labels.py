"""Source-grounded file representation equivalence, without basename guessing."""

import pytest
from evaluation.workflow import MissingEvidence, operand


def labels(requested, paths=None, names=None):
    return operand(
        {
            "operation": "source_file_labels",
            "args": [
                {"value": requested},
                {"value": paths or ["/release/a.qout", "/release/b.qout"]},
                {"value": names or ["a.qout", "b.qout"]},
            ],
        },
        {},
    )


def test_only_observed_paths_and_declared_portable_labels_are_equivalent():
    assert labels(["/release/b.qout", "asset://a.qout", "a.qout"]) == [
        "b.qout",
        "a.qout",
        "a.qout",
    ]
    assert labels(["/other/b.qout", "asset://../a.qout", "B.qout"]) == [
        "/other/b.qout",
        "asset://../a.qout",
        "B.qout",
    ]
    assert labels([]) == []


@pytest.mark.parametrize(
    "paths,names",
    [
        (["/one/a", "/two/a"], ["a", "a"]),
        (["/one/a", "/one/a"], ["a", "b"]),
        (["/one/a"], ["../a"]),
        (["/one/a"], ["a", "b"]),
        (["b", "/two/b"], ["a", "b"]),
    ],
)
def test_ambiguous_or_malformed_source_mapping_is_rejected(paths, names):
    with pytest.raises(MissingEvidence):
        labels(["a"], paths, names)


def test_non_string_answer_labels_are_not_coerced():
    with pytest.raises(MissingEvidence):
        labels([True])
