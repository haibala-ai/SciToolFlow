"""API-compatible HTTP and local inference across both baselines."""

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

P = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(P))
from baselines.react.runtime import run_react
from baselines.scitoolagent.runtime import run_scitoolagent
from src.models.client import GenerationClient, resolve_api_connection
from tools.catalog import ToolCatalog
from tools import execute
from tests.support.planner import StaticRetriever, PLAN, CALL, FINISH, SCHEMA


@contextmanager
def api_server(replies, **overrides):
    requests = []
    pending = iter(replies)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append({"path": self.path, "payload": payload})
            value = next(pending)
            status = value if isinstance(value, int) else 200
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            response = {
                "id": "transport-control",
                "model": "mock-model",
                "choices": [
                    {"message": {"content": json.dumps(value)}, "finish_reason": "stop"}
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }
            self.wfile.write(json.dumps(response if status == 200 else {}).encode())

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    env = {
        "SCITOOLFLOW_API_BASE": "http://127.0.0.1:%d/v1" % server.server_port,
        "SCITOOLFLOW_API_KEY": "TEST_KEY_DO_NOT_LOG",
        "SCITOOLFLOW_API_MODEL": "mock-model",
        "SCITOOLFLOW_API_TOKEN_PARAMETER": "max_tokens",
        "NO_PROXY": "127.0.0.1,localhost",
        **overrides,
    }
    try:
        with patch.dict(os.environ, env):
            yield requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class ModelBackendTests(unittest.TestCase):
    def test_resident_worker_writes_protocol_to_stdout_not_redirected_logs(self):
        from src.models import local_worker

        output, errors = io.StringIO(), io.StringIO()
        request = io.StringIO(json.dumps({"operation": "chat", "messages": []}) + "\n")
        reply = {"ok": True, "text": '{"finish":{}}'}
        with (
            patch.object(
                sys,
                "argv",
                [
                    "local_worker.py",
                    "--model",
                    "/models/control",
                    "--embedding",
                    "/models/embed",
                ],
            ),
            patch.object(sys, "stdin", request),
            patch.object(sys, "stdout", output),
            patch.object(sys, "stderr", errors),
            patch.object(
                local_worker, "resident_service", return_value="http://127.0.0.1:123/v1"
            ),
            patch.object(local_worker, "forward_to_service", return_value=reply),
        ):
            local_worker.main()
        self.assertEqual(json.loads(output.getvalue())["text"], reply["text"])
        self.assertNotIn('"ok":', errors.getvalue())

    def run_baseline(self, baseline, dataset="full"):
        replies = [CALL, FINISH] if baseline == "react" else [PLAN, CALL, FINISH]
        with api_server(replies) as sent, tempfile.TemporaryDirectory() as directory:
            catalog = ToolCatalog()
            client = GenerationClient("api")
            options = (
                {"retriever": StaticRetriever()} if baseline == "scitoolagent" else {}
            )
            try:
                result = (run_react if baseline == "react" else run_scitoolagent)(
                    "Parse the public JSON and report the observed number.",
                    dataset=dataset,
                    catalog=catalog,
                    client=client,
                    invoke=lambda name, args, **kw: execute(
                        name, args, catalog=catalog, **kw
                    ),
                    trace_dir=directory,
                    inputs={"json_text": '{"value":7}'},
                    answer_schema=SCHEMA,
                    max_iterations=6,
                    **options,
                )
            finally:
                client.close()
            self.assertEqual(
                json.loads(Path(result["trace_path"]).read_text())["dataset"], dataset
            )
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["final_answer"], {"results": {"value": 7}})
            self.assertEqual(len(sent), len(replies))
            self.assertTrue(all(r["path"] == "/v1/chat/completions" for r in sent))
            return sent

    def test_react_api_executes_real_tool_and_cites_its_output(self):
        self.run_baseline("react")

    def test_both_baselines_keep_the_special_namespace_in_actual_trajectories(self):
        for baseline in ("react", "scitoolagent"):
            with self.subTest(baseline=baseline):
                self.run_baseline(baseline, dataset="mini")

    def test_scitoolagent_roles_use_the_api_without_reading_references(self):
        original = Path.read_text

        def guarded(path, *args, **kwargs):
            if P / "evaluation" in path.parents:
                raise AssertionError("actor read private evaluation data")
            return original(path, *args, **kwargs)

        with patch.object(Path, "read_text", guarded):
            self.run_baseline("scitoolagent")

    def test_api_structured_output_is_opt_in_and_uses_the_supplied_public_schema(self):
        with api_server(
            [{"finish": {}}], SCITOOLFLOW_API_STRUCTURED_OUTPUT="1"
        ) as sent:
            client = GenerationClient("api")
            with client.generation_scope():
                client.request([], response_schema={"type": "object"}, max_tokens=123)
            self.assertEqual(sent[0]["payload"]["max_tokens"], 123)
            self.assertEqual(
                sent[0]["payload"]["response_format"]["type"], "json_schema"
            )
            client.close()

    def test_api_authentication_failure_is_not_retried_or_logged_with_key(self):
        with api_server([401]) as sent:
            client = GenerationClient("api")
            with (
                client.generation_scope(),
                self.assertRaisesRegex(RuntimeError, "HTTP 401") as error,
            ):
                client.request([])
            self.assertNotIn("TEST_KEY_DO_NOT_LOG", str(error.exception))
            self.assertEqual(len(sent), 1)
            client.close()

    def test_embedding_credentials_do_not_silently_authorize_generation(self):
        with (
            patch.dict(
                os.environ, {"SCITOOL_EMBEDDING_API_KEY": "embedding-only"}, clear=True
            ),
            patch("src.utils.paths.load_environment"),
        ):
            with self.assertRaisesRegex(ValueError, "SCITOOLFLOW_API_KEY"):
                resolve_api_connection()

    def test_provider_fingerprint_changes_when_generation_settings_change(self):
        with api_server([]):
            client = GenerationClient("api")
            first = client.public_settings()
            with patch.dict(
                os.environ, {"SCITOOLFLOW_API_EXTRA_BODY": '{"temperature":0.4}'}
            ):
                second = client.public_settings()
            self.assertNotEqual(first["extra_body_sha256"], second["extra_body_sha256"])

    def test_local_fingerprint_binds_resident_sampling_and_device_selection(self):
        client = GenerationClient("local")
        first = client.public_settings()
        with patch.dict(
            os.environ,
            {"SCITOOLFLOW_VLLM_TEMPERATURE": "0.8", "SCITOOL_LLM_GPU": "6,7"},
        ):
            second = client.public_settings()
        self.assertNotEqual(
            first["same_weight_resident_settings"],
            second["same_weight_resident_settings"],
        )
        self.assertEqual(second["gpu_devices"], "6,7")


if __name__ == "__main__":
    unittest.main()
