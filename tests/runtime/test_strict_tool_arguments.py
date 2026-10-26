"""Raw typed contracts must survive dispatch without changing legacy codecs."""

import json
import unittest
from unittest.mock import patch

from tools.catalog import ToolCatalog
from tools.implementations.shared.common import InputValidationError, parse_parameters
from tools.runtime.dispatch import REGISTRY, invoke_here
from tasks.schema import validation_errors


class StrictToolArgumentsTests(unittest.TestCase):
    def test_every_registered_tool_has_a_discoverable_public_contract(self):
        catalog = ToolCatalog()
        names = list(catalog.tools)
        for offset in range(0, len(names), 20):
            batch = names[offset : offset + 20]
            result = catalog.describe(batch)
            self.assertEqual(result["unknown"], [])
            self.assertEqual(result["count"], len(batch))

    def test_catalog_carries_raw_schema_to_dispatch(self):
        catalog = ToolCatalog()
        name = "NumericRangeMask"
        self.assertTrue(catalog.registry()["tools"][name]["strict_arguments"])
        self.assertEqual(
            catalog.registry()["tools"][name]["input_schema"],
            catalog.tools[name]["input_schema"],
        )

    def test_actual_registered_typed_mask_rejects_coercion(self):
        for changed in (
            {"upper_inclusive": "false"},
            {"lower_inclusive": "true"},
            {"upper_inclusive": 1},
            {"lower_bound": "0"},
            {"lower_bound": True},
            {"UpperInclusive": False},
        ):
            with self.subTest(changed=changed), self.assertRaises(InputValidationError):
                invoke_here(
                    "NumericRangeMask", json.dumps({"values": [0, 1], **changed})
                )
        actual = invoke_here(
            "NumericRangeMask",
            json.dumps({"values": [0, 1], "upper_bound": 1, "upper_inclusive": False}),
        )
        self.assertEqual(actual["values"], [1, 0])

    def test_raw_schema_rejects_before_a_function_can_have_side_effects(self):
        spec = {
            "strict_arguments": True,
            "input_schema": {
                "type": "object",
                "properties": {"count": {"type": "integer"}},
                "required": ["count"],
                "additionalProperties": False,
            },
        }
        called = []

        def fake(count: int):
            called.append(count)
            return count

        with (
            patch.dict(REGISTRY["tools"], {"TypedControl": spec}),
            patch("tools.runtime.dispatch.resolve_function", return_value=fake),
        ):
            for arguments in ({"count": True}, {"count": "2"}, {"Count": 2}, [2]):
                with (
                    self.subTest(arguments=arguments),
                    self.assertRaises(InputValidationError),
                ):
                    invoke_here("TypedControl", json.dumps(arguments))
            self.assertEqual(called, [])
            self.assertEqual(invoke_here("TypedControl", '{"count": 2}'), 2)
            self.assertEqual(called, [2])

    def test_legacy_coercion_still_works_when_not_opted_in(self):
        def legacy(count: int, enabled: bool):
            return count, enabled

        args, kwargs = parse_parameters(legacy, '{"count":"2","enabled":"false"}')
        self.assertEqual(legacy(*args, **kwargs), (2, False))
        with self.assertRaises(InputValidationError):
            parse_parameters(
                legacy,
                '{"count":"2","enabled":"false"}',
                coerce_scalar_strings=False,
            )
        with (
            patch.dict(REGISTRY["tools"], {"LegacyControl": {}}),
            patch("tools.runtime.dispatch.resolve_function", return_value=legacy),
        ):
            self.assertEqual(
                invoke_here("LegacyControl", '{"Count":"2","enabled":"false"}'),
                (2, False),
            )

    def test_integer_answer_schema_uses_json_mathematical_integer_semantics(self):
        schema = {"type": "integer"}
        for value in [24, 24.0, 0.0, -2.0]:
            self.assertEqual(validation_errors(value, schema), [])
        for value in [24.1, True, "24", float("inf"), float("nan")]:
            self.assertTrue(validation_errors(value, schema))

    def test_strict_integer_scalar_accepts_lossless_numeric_handoff_only(self):
        spec = {
            "strict_arguments": True,
            "input_schema": {
                "type": "object",
                "properties": {"count": {"type": "integer"}},
                "required": ["count"],
                "additionalProperties": False,
            },
        }

        def counter(count: int):
            return type(count).__name__, count

        with (
            patch.dict(REGISTRY["tools"], {"IntegerControl": spec}),
            patch("tools.runtime.dispatch.resolve_function", return_value=counter),
        ):
            self.assertEqual(
                invoke_here("IntegerControl", '{"count":448.0}'), ("int", 448)
            )
            for value in [448.5, True, "448"]:
                with self.subTest(value=value), self.assertRaises(InputValidationError):
                    invoke_here("IntegerControl", json.dumps({"count": value}))

        with self.assertRaises(InputValidationError):
            parse_parameters(counter, '{"count":448.0}')


if __name__ == "__main__":
    unittest.main()
