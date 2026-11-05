"""Regression tests for independent scoring, public contracts and resumable execution."""

import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

P = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(P))
from tasks.schema import answer_schema, validation_errors
from evaluation.integrity.package import validate_unit_annotations
from src.models.client import GenerationClient
from baselines.react.context import Context
from tools.catalog import ToolCatalog
from baselines.react import runner as batch


class ContractAndRuntimeTests(unittest.TestCase):
    def test_discovery_exposes_explicit_failure_contract_without_internal_bindings(
        self,
    ):
        result = ToolCatalog().describe(
            ["ReadCrystalStructure", "NumericalTrapezoidIntegration"]
        )["tools"]
        self.assertIn(
            "invalid_input", result["ReadCrystalStructure"]["failure_feedback"]
        )
        self.assertIn(
            "invalid_output",
            result["NumericalTrapezoidIntegration"]["failure_feedback"],
        )
        for value in result.values():
            self.assertNotIn("execution", value)
            self.assertNotIn("source", value)
        integration = result["NumericalTrapezoidIntegration"]
        self.assertEqual(integration["output_schema"]["type"], "object")
        self.assertEqual(
            set(integration["output_schema"]["required"]),
            {"integral", "point_count", "method"},
        )

    def test_schema_has_no_array_cardinality_or_values(self):
        schema = answer_schema(
            {"values": [4, 5, 6], "entities": {"mp-149": {"gap": 1.3}}}
        )
        serialized = json.dumps(schema)
        self.assertNotIn("mp-149", serialized)
        self.assertNotIn("minItems", serialized)
        self.assertNotIn("maxItems", serialized)
        self.assertTrue(validation_errors({}, schema))
        self.assertFalse(
            validation_errors(
                {"values": [9], "entities": {"mp-10": {"gap": 2}}}, schema
            )
        )

    def test_all_public_contracts_are_executable_and_reject_empty(self):
        rows = [
            json.loads(s)
            for s in (P / "tasks/full/questions.jsonl").read_text().splitlines()
        ]
        self.assertEqual(len(rows), 500)
        self.assertTrue(
            all(row["answer_schema"].get("type") == "object" for row in rows)
        )
        self.assertTrue(
            all(validation_errors({}, row["answer_schema"]) for row in rows)
        )

    def test_unit_annotations_resolve(self):

        from src.utils.io import read_jsonl

        refs = {
            r["id"]: r for r in read_jsonl(P / "evaluation/data/references.jsonl.gz")
        }
        schemas = [
            json.loads(s)
            for s in (P / "tasks/full/questions.jsonl").read_text().splitlines()
        ]
        for row in schemas:
            for item in row.get("unit_annotations", []):
                validate_unit_annotations(
                    {"unit_annotations": [item]}, refs[row["id"]]["expected_answer"]
                )

    def test_tools_do_not_load_reference_examples(self):
        expected_tools = json.loads((P / "tools/catalog/catalog.json").read_text())[
            "tools"
        ]
        self.assertTrue(expected_tools)
        self.assertEqual(set(ToolCatalog().tools), set(expected_tools))
        original = Path.read_text

        def guarded(path, *a, **kw):
            if {"reference_traces", "trajectories"} & set(path.parts) or path.name in {
                "references.jsonl",
                "references.jsonl.gz",
            }:
                raise AssertionError("Actor read private reference traces")
            return original(path, *a, **kw)

        with patch.object(Path, "read_text", guarded):
            self.assertEqual(set(ToolCatalog().tools), set(expected_tools))

    def test_vllm_authorization_is_not_sampling_key(self):
        class Response:
            status_code = 200

            def json(self):
                return {
                    "choices": [
                        {
                            "message": {"content": '{"finish":{}}'},
                            "finish_reason": "stop",
                        }
                    ]
                }

        class Session:
            def post(self, *a, **kw):
                self.headers = kw["headers"]
                return Response()

        session = Session()
        with patch.dict(os.environ, {"SCITOOLFLOW_VLLM_KEY": "TEST_PLACEHOLDER"}):
            client = GenerationClient("vllm", session=session)
            with client.generation_scope():
                client.request([{"role": "user", "content": "probe"}], max_tokens=16)
        self.assertEqual(session.headers["Authorization"], "Bearer TEST_PLACEHOLDER")

    def test_sampling_validation(self):
        with patch.dict(os.environ, {"SCITOOLFLOW_VLLM_TOP_P": "nan"}):
            client = GenerationClient("vllm", session=object())
            with client.generation_scope(), self.assertRaises(ValueError):
                client.request([], max_tokens=10)

    def test_checkpoint_resume(self):
        previous = {
            "fingerprint": "same",
            "predictions": [{"id": "A"}],
            "progress": [{"id": "A", "status": "completed"}],
        }
        predictions = batch.resume_rows(previous, "same")
        rows = predictions
        self.assertEqual([r["id"] for r in rows], ["A"])
        self.assertEqual(len(predictions), 1)
        with self.assertRaises(ValueError):
            batch.resume_rows(previous, "changed")
        with self.assertRaises(ValueError):
            batch.resume_rows({"predictions": [{"id": "A"}]}, "same")

    def test_exact_token_budget_in_context(self):
        with self.assertRaises(ValueError):
            Context([{"content": "too much"}], 1000, lambda m: 20, 10)
        context = Context([{"content": "initial"}], 1000, lambda m: len(m) * 10, 25)
        context.append("user", "one")
        context.append("user", "two")
        self.assertLessEqual(len(context.build([])), 2)


if __name__ == "__main__":
    unittest.main()
