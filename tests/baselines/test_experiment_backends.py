"""End-to-end supervisor routing without needing an external account or GPU."""

import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.benchmark import run_benchmark


class ExperimentBackendTests(unittest.TestCase):
    def pipeline(self, backend, actor_code=0, dataset="full", tasks=None):
        commands = []
        tasks = tasks or ("all" if dataset == "mini" else "FLOW-0481")

        class Process:
            def __init__(self, command, **kwargs):
                commands.append(command)
                self.stdout = io.StringIO("")
                self.returncode = actor_code if command[2] == "run" else 0
                output = Path(command[command.index("--output") + 1])
                if command[2] == "run":
                    output.write_text(
                        json.dumps(
                            {"predictions": [{"id": "FLOW-0481", "completed": True}]}
                        )
                    )
                elif command[2] == "score":
                    output.write_text(json.dumps({"summary": {}}))
                    output.with_name("scores_review_requests.json").write_text(
                        '{"tasks":[]}'
                    )

            def wait(self, **kwargs):
                return self.returncode

        with tempfile.TemporaryDirectory() as directory:
            argv = [
                "run_benchmark.py",
                "--backend",
                backend,
                "--model",
                "actor-control",
                "--baseline",
                "scitoolagent",
                "--tasks",
                tasks,
                "--dataset",
                dataset,
                "--output-dir",
                directory,
            ]
            env = {
                "SCITOOLFLOW_API_BASE": "http://127.0.0.1:12345/v1",
                "SCITOOLFLOW_API_KEY": "SECRET_TEST",
            }
            health = MagicMock()
            health.open.return_value.__enter__.return_value.status = 200
            with (
                patch.object(sys, "argv", argv),
                patch.dict(os.environ, env),
                patch.object(run_benchmark.subprocess, "Popen", Process),
                patch.object(
                    run_benchmark.urllib.request, "build_opener", return_value=health
                ) as opener,
            ):
                code = run_benchmark.main()
                calls = opener.call_count
            state = json.loads((Path(directory) / "experiment.json").read_text())
        return code, commands, calls, state

    def test_api_actor_scores_without_a_local_model(self):
        code, commands, readiness, state = self.pipeline("api")
        self.assertEqual(code, 0)
        self.assertEqual(readiness, 0)
        self.assertEqual([c[2] for c in commands], ["run", "score"])
        self.assertEqual(commands[0][commands[0].index("--backend") + 1], "api")
        self.assertEqual(commands[0][commands[0].index("--model") + 1], "actor-control")
        self.assertEqual(state["baseline"], "scitoolagent")
        self.assertEqual(state["denominator"], 1)
        self.assertEqual(state["status"], "finished")
        self.assertNotIn("SECRET_TEST", json.dumps(state))

    def test_mini_pipeline_passes_dataset_to_run_and_score_and_uses_200_denominator(
        self,
    ):
        code, commands, readiness, state = self.pipeline("api", dataset="mini")
        self.assertEqual(code, 0)
        self.assertEqual(readiness, 0)
        self.assertEqual(state["dataset"], "mini")
        self.assertEqual(state["denominator"], 200)
        self.assertEqual(
            [c[c.index("--dataset") + 1] for c in commands], ["mini", "mini"]
        )
        self.assertTrue(all(c[c.index("--tasks") + 1] == "all" for c in commands))

    def test_local_service_actor_waits_for_readiness_before_scoring(self):
        code, commands, readiness, state = self.pipeline("vllm")
        self.assertEqual(code, 0)
        self.assertEqual(readiness, 1)
        self.assertEqual([c[2] for c in commands], ["run", "score"])
        self.assertEqual(commands[0][commands[0].index("--backend") + 1], "vllm")
        self.assertEqual(state["model"], "actor-control")
        self.assertEqual(state["status"], "finished")

    def test_actor_startup_failure_does_not_score_an_old_or_incompatible_checkpoint(
        self,
    ):
        code, commands, _, state = self.pipeline("api", actor_code=1)
        self.assertEqual(code, 1)
        self.assertEqual(len(commands), 1)
        self.assertEqual(state["status"], "failed")


if __name__ == "__main__":
    unittest.main()
