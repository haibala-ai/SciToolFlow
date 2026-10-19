"""End-to-end supervisor routing without needing an external account or GPU."""

import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import run_benchmark


class ExperimentBackendTests(unittest.TestCase):
    def pipeline(self, judge_backend, actor_code=0):
        commands = []

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
                elif command[2] == "judge":
                    output.write_text('{"reviews":[]}')

            def wait(self, **kwargs):
                return self.returncode

        with tempfile.TemporaryDirectory() as directory:
            argv = [
                "run_benchmark.py",
                "--backend",
                "api",
                "--model",
                "actor-control",
                "--baseline",
                "scitoolagent",
                "--tasks",
                "FLOW-0481",
                "--judge",
                "--judge-backend",
                judge_backend,
                "--judge-model",
                "review-control",
                "--output-dir",
                directory,
            ]
            env = {
                "SCITOOLFLOW_API_BASE": "http://127.0.0.1:12345/v1",
                "SCITOOLFLOW_API_KEY": "SECRET_TEST",
            }
            health = MagicMock()
            health.open.return_value.__enter__.return_value.status = 200
            with patch.object(sys, "argv", argv), patch.dict(
                os.environ, env
            ), patch.object(run_benchmark.subprocess, "Popen", Process), patch.object(
                run_benchmark.urllib.request, "build_opener", return_value=health
            ) as opener:
                code = run_benchmark.main()
                calls = opener.call_count
            state = json.loads((Path(directory) / "experiment.json").read_text())
        return code, commands, calls, state

    def test_api_actor_and_api_judge_do_not_wait_for_a_local_model(self):
        code, commands, readiness, state = self.pipeline("api")
        self.assertEqual(code, 0)
        self.assertEqual(readiness, 0)
        self.assertEqual([c[2] for c in commands], ["run", "score", "judge", "score"])
        for command, model in [
            (commands[0], "actor-control"),
            (commands[2], "review-control"),
        ]:
            self.assertEqual(command[command.index("--backend") + 1], "api")
            self.assertEqual(command[command.index("--model") + 1], model)
        self.assertEqual(state["baseline"], "scitoolagent")
        self.assertEqual(state["denominator"], 1)
        self.assertEqual(state["status"], "finished")
        self.assertNotIn("SECRET_TEST", json.dumps(state))

    def test_api_actor_can_use_an_independent_local_judge(self):
        code, commands, readiness, state = self.pipeline("vllm")
        self.assertEqual(code, 0)
        self.assertEqual(readiness, 1)
        self.assertEqual(commands[0][commands[0].index("--backend") + 1], "api")
        self.assertEqual(commands[2][commands[2].index("--backend") + 1], "vllm")
        self.assertEqual(state["judge_model"], "review-control")

    def test_actor_startup_failure_does_not_score_an_old_or_incompatible_checkpoint(
        self,
    ):
        code, commands, _, state = self.pipeline("api", actor_code=1)
        self.assertEqual(code, 1)
        self.assertEqual(len(commands), 1)
        self.assertEqual(state["status"], "failed")


if __name__ == "__main__":
    unittest.main()
