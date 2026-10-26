"""Package boundaries preserve offline scoring and executable maintenance roots."""

import importlib
import inspect
import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]


class ImportBoundaryTests(unittest.TestCase):
    def test_offline_scoring_imports_no_scientific_implementation_or_model_client(self):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import evaluation.runner,sys,json; "
                "print(json.dumps([n for n in sys.modules if "
                "n.startswith('tools.implementations') or "
                "n=='src.models.client']))",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(json.loads(result.stdout), [])

    def test_root_cli_executes_one_command_once(self):
        result = subprocess.run(
            [sys.executable, "cli.py", "describe", "ParseJSONDocument"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        document = json.loads(result.stdout)
        self.assertEqual(document["count"], 1)

    def test_public_tool_api_matches_the_registered_discovery_implementation(self):
        from tools import ToolCatalog, execute
        from tools.runtime.executor import execute as runtime_execute

        self.assertIs(execute, runtime_execute)
        spec = ToolCatalog(ROOT).tools["DescribeTools"]
        module = importlib.import_module(spec["execution"]["module"])
        function = getattr(module, spec["execution"]["function"])
        self.assertEqual(
            Path(inspect.getsourcefile(function)), ROOT / spec["source"]["file"]
        )
        result = execute("DescribeTools", {"tools": ["ParseJSONDocument"]})
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["output"]["count"], 1)

    def test_grouped_maintenance_commands_expose_working_cli_entrypoints(self):
        for name in (
            "tools.build_graph",
            "tools.audit_tool_overlap",
            "benchmark.run_benchmark",
            "references.native_reference_session",
            "services.model_service",
            "maintenance.prepare_resources",
        ):
            with self.subTest(command=name):
                result = subprocess.run(
                    [sys.executable, "-m", "scripts." + name, "--help"],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                self.assertIn("usage:", result.stdout.lower())


if __name__ == "__main__":
    unittest.main()
