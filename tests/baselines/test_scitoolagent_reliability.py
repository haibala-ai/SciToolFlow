"""Concurrent retrieval cache and bounded, credential-safe embedding failures."""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from baselines.scitoolagent.retrieval import Embeddings, RetrievalError
from src.utils.io import atomic_json


class RetrievalReliabilityTests(unittest.TestCase):
    def test_concurrent_cache_writers_publish_complete_json_without_collisions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "shared-context.json"
            payloads = [{"writer": i, "vector": [i] * 512} for i in range(64)]
            with ThreadPoolExecutor(max_workers=16) as pool:
                list(pool.map(lambda row: atomic_json(path, row), payloads))
            actual = json.loads(path.read_text())
            self.assertIn(actual, payloads)
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def request(self, responses, deadline=None):
        identity = {"dimension": 3, "model": "test"}
        with tempfile.TemporaryDirectory() as directory:
            encoder = Embeddings(identity, directory)
            client = Mock()
            client.post.side_effect = responses
            with patch("baselines.scitoolagent.retrieval.time.sleep") as sleep:
                result = encoder.request_batch(
                    client,
                    "https://example.invalid",
                    "SECRET_TEST_KEY",
                    ["query"],
                    deadline if deadline is not None else time.monotonic() + 60,
                )
            return encoder, client, result, sleep

    def test_transient_failure_recovers_and_counts_attempts(self):
        import requests

        payload = {"data": []}
        encoder, client, result, sleep = self.request(
            [
                requests.Timeout("SECRET_TEST_KEY"),
                Mock(status_code=503),
                Mock(status_code=200, json=lambda: payload),
            ]
        )
        self.assertEqual(result, payload)
        self.assertEqual(client.post.call_count, 3)
        self.assertEqual(encoder.stats["requests"], 3)
        self.assertEqual(encoder.stats["retries"], 2)
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [1, 2])

    def test_authorization_failure_is_not_retried(self):
        with self.assertRaisesRegex(RetrievalError, "^Embedding API HTTP 401$"):
            self.request([Mock(status_code=401)])

    def test_transient_retries_are_bounded(self):
        with self.assertRaisesRegex(RetrievalError, "^Embedding API HTTP 503$"):
            self.request([Mock(status_code=503)] * 3)

    def test_expired_deadline_does_not_dispatch(self):
        with self.assertRaisesRegex(RetrievalError, "Task deadline"):
            self.request([], deadline=time.monotonic() - 1)

    def test_transport_failure_does_not_expose_credentials(self):
        import requests

        with self.assertRaisesRegex(
            RetrievalError, "^Embedding transport failure: Timeout$"
        ):
            self.request([requests.Timeout("SECRET_TEST_KEY")] * 3)


if __name__ == "__main__":
    unittest.main()
