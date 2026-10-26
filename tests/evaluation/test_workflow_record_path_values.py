import pytest

from evaluation.workflow import MissingEvidence, operand


def values(
    records,
    identity="CC.O",
    identity_path="/arcs/0/metadata/reactants",
    value_path="/score",
):
    return operand(
        {
            "operation": "record_values_by_path",
            "args": [
                {"value": records},
                {"value": identity_path},
                {"value": identity},
                {"value": value_path},
            ],
        },
        {},
    )


def row(identity, score):
    return {"arcs": [{"metadata": {"reactants": identity}}], "score": score}


def test_all_actual_matching_proposals_preserve_order_and_multiplicity():
    assert values(
        [row("CC.O", -0.4), row("C.O", -0.1), row("CC.O", -0.2), row("CC.O", -0.2)]
    ) == [-0.4, -0.2, -0.2]


def test_no_graph_normalization_or_string_numeric_coercion():
    with pytest.raises(MissingEvidence):
        values([row("O.CC", -0.1)])
    assert values([row(True, 1), row(1, 2), row("1", 3)], 1) == [2]
    assert values([row(1.0, 2)], 1) == [2]  # Both are exact JSON-number identities.
    assert values([row(None, 0)], None) == [0]


@pytest.mark.parametrize(
    "records",
    [
        [],
        {},
        [1],
        [row("other", 1), {"score": 2}],
        [row("CC.O", 1), {"arcs": [{"metadata": {"reactants": "other"}}]}],
        [row("CC.O", float("nan"))],
        [row("other", float("inf"))],
        [row({"id": "CC.O"}, 1)],
        [row("CC.O", "a" * 2000001)],
        [row("CC.O", 1)] * 1001,
    ],
)
def test_incomplete_nonfinite_or_oversized_source_fails_closed(records):
    with pytest.raises(MissingEvidence):
        values(records)


@pytest.mark.parametrize(
    "pointer", ["score", "/bad~2key", "/bad~", None, 1, "/" + "a" * 1001]
)
def test_strict_pointer_contract(pointer):
    with pytest.raises(MissingEvidence):
        values([row("CC.O", 1)], value_path=pointer)


def test_escaped_keys_and_null_are_actual_values_not_missing_fallbacks():
    assert values([{"a/b": {"~key": "x"}, "score": None}], "x", "/a~1b/~0key") == [None]


def test_no_match_or_container_identity_is_not_invented():
    with pytest.raises(MissingEvidence):
        values([row("other", 1)])
    with pytest.raises(MissingEvidence):
        values([row("CC.O", 1)], ["CC.O"])
