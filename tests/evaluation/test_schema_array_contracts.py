"""Position tuples and array bounds follow their declared JSON Schema dialect."""

import pytest

from tasks.schema import validation_errors


TUPLE = {
    "type": "array",
    "prefixItems": [{"type": "integer"}, {"type": "string"}],
    "items": False,
    "minItems": 2,
    "maxItems": 2,
}


@pytest.mark.parametrize(
    "value, valid",
    [([4, "atom"], True), ([4.0, "atom"], True), ([True, "atom"], False),
     ([4.5, "atom"], False), ([4, 2], False), ([4], False),
     ([4, "atom", 3], False), ([], False)],
)
def test_positional_tuple_contract(value, valid):
    assert (not validation_errors(value, TUPLE)) is valid


@pytest.mark.parametrize("tail, valid", [({}, True), (False, False), (True, True)])
def test_legacy_additional_items(tail, valid):
    schema = {"type": "array", "items": [{"type": "integer"}],
              "additionalItems": tail}
    assert (not validation_errors([1, "extra"], schema)) is valid


def test_prefix_then_homogeneous_tail():
    schema = {"type": "array", "prefixItems": [{"type": "string"}],
              "items": {"type": "integer"}}
    assert not validation_errors(["row", 1, 2], schema)
    assert validation_errors(["row", 1, False], schema)


def test_nested_arrays_keep_all_length_and_type_constraints():
    schema = {"type": "array", "minItems": 1, "maxItems": 2, "items": TUPLE}
    assert not validation_errors([[1, "a"], [2, "b"]], schema)
    for value in [[], [[1, "a"], [2, "b"], [3, "c"]], [[1]], [[1, "a", 2]]]:
        assert validation_errors(value, schema)
