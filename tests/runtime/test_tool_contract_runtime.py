"""Tool registration, index boundaries and complete contract enforcement."""

import math
import copy
import unittest
from unittest.mock import patch

from tools.catalog import ToolCatalog
from tools import execute
from tools.runtime.contracts import contract_errors
from scripts.tools.build_graph import make_graph


class ToolContractRuntimeTests(unittest.TestCase):
    def test_full_schema_keywords_and_finite_json_are_enforced(self):
        schema = {
            "type": "object",
            "properties": {"x": {"type": "integer", "minimum": 1, "maximum": 2}},
            "required": ["x"],
            "additionalProperties": False,
        }
        for value in [
            {"x": 0},
            {"x": 3},
            {"x": True},
            {"x": 1, "other": 2},
            {"x": math.nan},
        ]:
            self.assertTrue(contract_errors(value, schema), value)
        self.assertEqual(contract_errors({"x": 1}, schema), [])
        self.assertTrue(contract_errors({1: "x"}, {}))

    def test_every_backend_uses_one_output_validation_policy(self):
        from tools.runtime.dispatch import validate_result

        spec = {
            "output_schema": {
                "type": "object",
                "properties": {"value": {"type": "number"}},
                "required": ["value"],
            }
        }
        for out in [
            {"other": 1},
            {"value": float("nan")},
            {"status": "error", "value": float("inf")},
        ]:
            self.assertEqual(validate_result(out, spec)["error_type"], "InvalidOutput")
        self.assertEqual(validate_result({"value": 2.0}, spec)["status"], "success")
        self.assertEqual(
            validate_result({"status": "queued", "message": "waiting"}, spec)["status"],
            "blocked",
        )
        encoded = {
            "output_schema": {"type": "string"},
            "output_encoding": {
                "decoded_type": "json_object",
                "decoded_schema": spec["output_schema"],
            },
        }
        for text in [
            "plain text",
            '{"other":1}',
            '{"value":NaN}',
            '{"value":1,"value":2}',
        ]:
            self.assertEqual(
                validate_result(text, encoded)["error_type"], "InvalidOutput"
            )
        self.assertEqual(validate_result('{"value":2}', encoded)["status"], "success")

    def test_describe_is_general_tool_and_not_indexed(self):
        catalog = ToolCatalog()
        spec = catalog.tools["DescribeTools"]
        self.assertEqual(spec["kind"], "tool")
        self.assertEqual(spec["domain"], "General")
        self.assertNotIn("DescribeTools", catalog.indexed_tools("graph"))
        self.assertNotIn("DescribeTools", catalog.indexed_tools("embedding"))
        graph = make_graph(catalog)
        self.assertNotIn("DescribeTools", graph)
        self.assertFalse(
            any(
                target == "DescribeTools"
                for pairs in graph.values()
                for _, target in pairs
            )
        )
        row = execute(
            "DescribeTools",
            {"tools": ["DescribeTools", "AdjustPValues"]},
            catalog=catalog,
        )
        self.assertEqual(row["status"], "success")
        self.assertEqual(row["kind"], "tool")
        self.assertEqual(row["output"]["count"], 2)

    def test_retired_call_is_explicit_and_never_dispatched(self):
        catalog = ToolCatalog()
        with patch("tools.runtime.dispatch.execute") as dispatch:
            row = execute("ConvertSmilesToInchi", {"smiles": "CCO"}, catalog=catalog)
        self.assertEqual(row["error_type"], "RetiredTool")
        self.assertTrue(row["replacements"])
        dispatch.assert_not_called()
        found = catalog.describe(["ConvertSmilesToInchi"])["unknown"][0]
        self.assertEqual(found["status"], "retired")
        self.assertTrue(found["replacement_contracts"])

    def test_every_registered_tool_rejects_undeclared_arguments(self):
        catalog = ToolCatalog()
        with patch("tools.runtime.dispatch.execute") as dispatch:
            for name in catalog.tools:
                row = execute(name, {"__undeclared_argument__": 1}, catalog=catalog)
                self.assertEqual(row["status"], "error", name)
                self.assertEqual(row["error_type"], "InvalidInput", name)
        dispatch.assert_not_called()

    def test_one_of_input_transport_is_not_silently_ignored(self):
        row = execute("AdjustPValues", {"p_values": [0.1], "results_file": "a.json"})
        self.assertEqual(row["error_type"], "InvalidInput")

    def test_host_documentation_uses_the_supplied_catalog(self):
        catalog = ToolCatalog()
        catalog.tools = copy.deepcopy(catalog.tools)
        catalog.tools["AdjustPValues"]["description"] = "Custom catalog sentinel."
        row = execute("DescribeTools", {"tools": ["AdjustPValues"]}, catalog=catalog)
        self.assertEqual(
            row["output"]["tools"]["AdjustPValues"]["description"],
            "Custom catalog sentinel.",
        )

    def test_categorical_split_and_constant_polynomial_contract_boundaries(self):
        from tools.implementations.machine_learning.numeric_tools import (
            split_train_test,
            polynomial_least_squares_fit,
        )

        c = ToolCatalog()
        split = split_train_test(
            [[0.0], [1.0], [2.0], [3.0]], ["a", "a", "b", "b"], seed=3
        )
        self.assertEqual(
            contract_errors(split, c.tools["SplitTrainTest"]["output_schema"]), []
        )
        args = {"x": [0.0, 1.0, 2.0], "y": [2.0, 2.0, 2.0], "degree": 0}
        self.assertEqual(
            contract_errors(args, c.tools["PolynomialLeastSquaresFit"]["input_schema"]),
            [],
        )
        self.assertEqual(
            contract_errors(
                polynomial_least_squares_fit(**args),
                c.tools["PolynomialLeastSquaresFit"]["output_schema"],
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
