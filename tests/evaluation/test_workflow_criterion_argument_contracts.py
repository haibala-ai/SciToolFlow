"""A branch cannot observe parameters absent from a closed tool contract."""

import unittest
from evaluation.workflow.contracts import (
    invalid_argument_roots,
    invalid_output_roots,
)


class CriterionArgumentContractTests(unittest.TestCase):
    def test_unknown_parameter_is_reported_for_each_affected_tool(self):
        h = {
            "id": "example",
            "evaluation": {
                "nodes": [
                    {
                        "id": "fit",
                        "bindings": [],
                        "alternatives": [
                            {
                                "tools": ["poly"],
                                "input_rules": [
                                    {
                                        "left": {
                                            "operation": "paired_rows",
                                            "args": [
                                                {
                                                    "source": "call_arguments",
                                                    "path": "/training_features",
                                                },
                                                {
                                                    "source": "call_arguments",
                                                    "path": "/y",
                                                },
                                            ],
                                        },
                                        "op": "eq",
                                        "value": [],
                                    }
                                ],
                            }
                        ],
                    }
                ]
            },
        }
        catalog = {
            "poly": {
                "input_schema": {
                    "properties": {"x": {}, "y": {}, "degree": {}},
                    "additionalProperties": False,
                }
            }
        }
        findings = invalid_argument_roots(h, catalog)
        self.assertEqual([f["invalid_path"] for f in findings], ["/training_features"])
        h["evaluation"]["nodes"][0]["alternatives"][0]["input_rules"][0]["left"][
            "args"
        ][0]["path"] = "/x/0"
        self.assertEqual(invalid_argument_roots(h, catalog), [])

    def test_argument_bindings_checked_but_literal_data_not_interpreted(self):
        h = {
            "id": "example",
            "evaluation": {
                "nodes": [
                    {
                        "id": "fit",
                        "bindings": [{"argument": "/missing"}],
                        "alternatives": [
                            {
                                "tools": ["poly"],
                                "input_rules": [
                                    {
                                        "path": "/x",
                                        "op": "eq",
                                        "value": {
                                            "source": "call_arguments",
                                            "path": "/not_a_selector",
                                        },
                                    }
                                ],
                            }
                        ],
                    }
                ]
            },
        }
        cat = {
            "poly": {
                "input_schema": {"properties": {"x": {}}, "additionalProperties": False}
            }
        }
        self.assertEqual(
            [f["invalid_path"] for f in invalid_argument_roots(h, cat)], ["/missing"]
        )
        cat["poly"]["input_schema"]["additionalProperties"] = True
        self.assertEqual(invalid_argument_roots(h, cat), [])

    def test_output_selectors_are_checked_against_closed_result_fields(self):
        h = {
            "id": "example",
            "evaluation": {
                "nodes": [
                    {
                        "id": "fit",
                        "alternatives": [
                            {
                                "tools": ["poly"],
                                "output_rules": [
                                    {"path": "/model/coefficients", "op": "finite"}
                                ],
                            }
                        ],
                    }
                ]
            },
        }
        catalog = {
            "poly": {
                "output_schema": {
                    "type": "object",
                    "properties": {"coefficients": {}},
                    "additionalProperties": False,
                }
            }
        }
        self.assertEqual(
            [f["invalid_path"] for f in invalid_output_roots(h, catalog)],
            ["/model/coefficients"],
        )
        h["evaluation"]["nodes"][0]["alternatives"][0]["output_rules"][0][
            "path"
        ] = "/coefficients/0"
        self.assertEqual(invalid_output_roots(h, catalog), [])


if __name__ == "__main__":
    unittest.main()
