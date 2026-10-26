"""Offline protocol fixtures: queued PPI3D pages never become scientific negatives.

These synthetic HTML responses and virtual clock do not establish service
availability or describe an observed current server template.
"""

import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from tools.implementations.biology import ppi3d_current as ppi
from tools.catalog import ToolCatalog
from tools.runtime.dispatch import validate_result


QUEUED = "<h1>Summary of results</h1><p>No results yet.</p><p>Query queued</p>"
PROCESSING = (
    "<h1>Summary of results</h1><p>No matches yet.</p><p>Processing your query</p>"
)
NEGATIVE = "<h1>Summary of results</h1><p>No protein-protein interactions found.</p>"
POSITIVE = "<h1>Summary of results</h1><table><tr><th>Chain</th><th>Partner</th></tr><tr><td>A</td><td>B</td></tr></table>"


class PPI3DAsyncStatusTests(unittest.TestCase):
    def test_explicit_pending_overrides_result_heading_and_negative_phrase(self):
        with tempfile.TemporaryDirectory() as directory:
            for html in [QUEUED, PROCESSING, QUEUED.lower()]:
                with (
                    self.subTest(html=html),
                    self.assertRaisesRegex(TimeoutError, "queued/processing"),
                ):
                    ppi._report(
                        html,
                        "https://fixture.invalid/result",
                        Path(directory),
                        "offline fixture",
                    )

    def test_completed_zero_interfaces_remain_a_successful_negative(self):
        with tempfile.TemporaryDirectory() as directory:
            output = ppi._report(
                NEGATIVE,
                "https://fixture.invalid/result",
                Path(directory),
                "offline fixture",
            )
        data = json.loads(output)
        self.assertTrue(data["completed"])
        self.assertTrue(data["negative_result"])
        self.assertEqual(data["tables"], [])
        self.assertEqual(
            validate_result(output, ToolCatalog().tools["PPI3DPDB"])["status"],
            "success",
        )

    def test_completed_positive_interface_table_remains_a_success(self):
        with tempfile.TemporaryDirectory() as directory:
            output = ppi._report(
                POSITIVE,
                "https://fixture.invalid/result",
                Path(directory),
                "offline fixture",
            )
        data = json.loads(output)
        self.assertFalse(data["negative_result"])
        self.assertEqual(data["tables"][0]["rows"], [["A", "B"]])
        self.assertEqual(
            validate_result(output, ToolCatalog().tools["PPI3DPDB"])["status"],
            "success",
        )

    def run_poll_fixture(self, pages, wait_seconds):
        clock = [0.0]
        gets = []

        def request(_session, method, _url, **_kwargs):
            if method == "POST":
                return SimpleNamespace(
                    url=ppi.BASE + "site/results/fixture_job",
                    text="submitted",
                    raise_for_status=lambda: None,
                )
            html = pages[min(len(gets), len(pages) - 1)]
            gets.append(html)
            return SimpleNamespace(text=html, raise_for_status=lambda: None)

        def sleep(duration):
            clock[0] += duration

        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.object(ppi, "artifacts_root", return_value=Path(directory)),
                patch.object(ppi.requests, "Session", return_value=object()),
                patch.object(ppi, "request_with_retries", side_effect=request),
                patch.object(ppi.time, "monotonic", side_effect=lambda: clock[0]),
                patch.object(ppi.time, "sleep", side_effect=sleep),
            ):
                try:
                    output = ppi.search_ppi3d_interfaces(
                        "ACDE", wait_seconds=wait_seconds
                    )
                except TimeoutError:
                    self.assertTrue(list(Path(directory).rglob("request.json")))
                    self.assertFalse(list(Path(directory).rglob("results.html")))
                    raise
        return output, gets

    def test_polling_continues_past_pending_then_returns_true_negative(self):
        output, gets = self.run_poll_fixture([QUEUED, NEGATIVE], 20)
        self.assertEqual(len(gets), 2)
        self.assertTrue(json.loads(output)["negative_result"])
        self.assertNotIn("queued", json.loads(output)["source_report"].lower())
        self.assertEqual(
            validate_result(output, ToolCatalog().tools["SearchPPI3DInterfaces"])[
                "status"
            ],
            "success",
        )

    def test_pending_only_exhausts_budget_without_a_scientific_result(self):
        with self.assertRaisesRegex(TimeoutError, "remains queued"):
            self.run_poll_fixture([PROCESSING], 20)


if __name__ == "__main__":
    unittest.main()
