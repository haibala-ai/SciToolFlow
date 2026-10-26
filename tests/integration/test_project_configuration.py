"""Portable deployment settings and authoritative release metadata."""

import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

from evaluation.integrity.package import validate_tool_counts
from scripts.maintenance import export_environments
from src.models.client import GenerationClient
from src.models.local import LocalRuntime
from tools.catalog.counts import tool_counts


class DeploymentConfigurationTests(unittest.TestCase):
    def test_direct_worker_and_fingerprint_respect_launcher_gpu_allocation(self):
        cases = [
            ({}, "0"),
            ({"CUDA_VISIBLE_DEVICES": "6,7"}, "6,7"),
            ({"CUDA_VISIBLE_DEVICES": "6,7", "SCITOOL_LLM_GPU": "2"}, "2"),
            ({"CUDA_VISIBLE_DEVICES": ""}, ""),
        ]
        for environment, expected in cases:
            with (
                self.subTest(environment=environment),
                tempfile.TemporaryDirectory() as tmp,
            ):
                config = SimpleNamespace(
                    TRACE_DIR=Path(tmp),
                    LLM_PYTHON="python",
                    LOCAL_MODEL_PATH="/models/actor",
                    LOCAL_EMBED_PATH="/models/embed",
                )
                process = Mock(stdout=[], stdin=Mock())
                process.poll.return_value = 0
                runtime = LocalRuntime()
                with (
                    patch.dict(os.environ, environment, clear=True),
                    patch("src.models.local.Config", return_value=config),
                    patch(
                        "src.models.local.subprocess.Popen", return_value=process
                    ) as launch,
                ):
                    runtime._start()
                    self.assertEqual(
                        launch.call_args.kwargs["env"]["CUDA_VISIBLE_DEVICES"], expected
                    )
                    self.assertEqual(
                        GenerationClient("local").public_settings()["gpu_devices"],
                        expected,
                    )
                    runtime.close()

    def test_conda_explicit_override_does_not_fall_back_to_another_installation(self):
        with (
            patch.dict(os.environ, {"CONDA_EXE": "/missing/conda"}, clear=True),
            patch("shutil.which", return_value=None),
        ):
            with self.assertRaisesRegex(ValueError, "Configured Conda"):
                export_environments.resolve_conda()

    def test_conda_can_resolve_active_installation_outside_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            executable = base / "bin/conda"
            executable.parent.mkdir()
            executable.write_text("#!/bin/sh\n")
            executable.chmod(0o755)
            with (
                patch.dict(os.environ, {}, clear=True),
                patch("shutil.which", return_value=None),
                patch(
                    "scripts.maintenance.export_environments.sys.prefix",
                    str(base / "envs/runner"),
                ),
            ):
                self.assertEqual(export_environments.resolve_conda(), executable)

    def test_environment_export_removes_local_prefix_and_retains_version_pins(self):
        export = SimpleNamespace(
            stdout="name: SciTool-Unified\ndependencies:\n  - python=3.10\nprefix: /host/env\n"
        )
        packages = SimpleNamespace(stdout='[{"name":"python"}]')
        with patch(
            "scripts.maintenance.export_environments.subprocess.run",
            side_effect=[export, packages],
        ):
            text, count = export_environments.export_profile(
                Path("/conda"), "SciTool-Unified"
            )
        self.assertNotIn("/host", text)
        self.assertIn("python=3.10", text)
        self.assertEqual(count, 1)

    def test_environment_exports_reject_embedded_credentials_without_echoing_them(self):
        urls = [
            "https://user:SECRET@example.test/pkg",
            "https://example.test/pkg?token=SECRET",
        ]
        for url in urls:
            with (
                self.subTest(url=url),
                patch(
                    "scripts.maintenance.export_environments.subprocess.run",
                    return_value=SimpleNamespace(stdout=f"dependencies:\n  - {url}\n"),
                ),
            ):
                with self.assertRaises(ValueError) as caught:
                    export_environments.export_profile(
                        Path("/conda"), "SciTool-Unified"
                    )
                self.assertNotIn("SECRET", str(caught.exception))

    def test_failed_late_export_preserves_all_existing_environment_profiles(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "configs/environments/SciTool-Unified.yml"
            target.parent.mkdir(parents=True)
            target.write_text("original\n")
            with (
                patch.object(export_environments, "ROOT", root),
                patch.object(
                    export_environments, "resolve_conda", return_value=Path("/conda")
                ),
                patch.object(
                    export_environments,
                    "export_profile",
                    side_effect=[
                        ("replacement\n", 1),
                        ("replacement\n", 1),
                        ValueError("credential URL"),
                    ],
                ),
            ):
                with self.assertRaises(ValueError):
                    export_environments.main([])
            self.assertEqual(target.read_text(), "original\n")
            self.assertEqual(list(target.parent.iterdir()), [target])


class ReleaseCountTests(unittest.TestCase):
    def setUp(self):
        self.catalog = {
            "ScientificTool": {"domain": "Material"},
            "DescribeTools": {
                "domain": "General",
                "indexing": {"graph": False, "embedding": False},
            },
        }
        self.counts = tool_counts(self.catalog)

    def test_all_count_fields_are_required_and_boolean_counts_are_rejected(self):
        self.assertEqual(validate_tool_counts(self.counts, self.catalog), self.counts)
        for key in self.counts:
            for value in (None, True, -1):
                with self.subTest(key=key, value=value):
                    invalid = dict(self.counts)
                    if value is None:
                        del invalid[key]
                    else:
                        invalid[key] = value
                    with self.assertRaisesRegex(ValueError, key):
                        validate_tool_counts(invalid, self.catalog)
        with self.assertRaises(ValueError):
            validate_tool_counts(
                {"scientific_tools": 1, "discovery_tools": 1}, self.catalog
            )

    def test_contract_lookup_cannot_become_a_graph_or_embedding_candidate(self):
        for index in ("graph", "embedding"):
            catalog = json.loads(json.dumps(self.catalog))
            catalog["DescribeTools"]["indexing"][index] = True
            with (
                self.subTest(index=index),
                self.assertRaisesRegex(ValueError, "excluded"),
            ):
                validate_tool_counts(tool_counts(catalog), catalog)


if __name__ == "__main__":
    unittest.main()
