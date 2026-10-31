import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("run_codex", Path(__file__).resolve().parents[1] / "scripts/run_codex.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class TestCodexRunner(unittest.TestCase):
    def test_success_requires_completed_turn_and_zero_exit(self):
        event = {"type": "turn.completed", "usage": {"input_tokens": 30, "cached_input_tokens": 10, "output_tokens": 5}}
        result = runner.summarize([event], 0, 123)
        self.assertFalse(result["is_error"])
        self.assertEqual(result["usage"]["cache_read_input_tokens"], 10)
        self.assertIsNone(result["total_cost_usd"])
        self.assertTrue(runner.summarize([event], 1, 123)["is_error"])
        self.assertTrue(runner.summarize([], 0, 123)["is_error"])
        self.assertTrue(runner.summarize([event, {"type": "turn.failed"}], 0, 123)["is_error"])

    def test_auth_error_reports_action_without_publishing_raw_error(self):
        result = runner.summarize([{"type": "error", "message": "401 Unauthorized secret-value"}], 1, 12)
        self.assertIn("CODEX_AUTH_JSON", result["result"])
        self.assertNotIn("secret-value", json.dumps(result))

    def test_missing_auth_emits_failure_for_health_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = Path(tmp) / "result.json"
            with patch.dict("os.environ", {}, clear=True), patch.object(sys, "argv", ["run_codex.py", "digest", "--result", str(result)]):
                with self.assertRaises(SystemExit):
                    runner.main()
            self.assertTrue(json.loads(result.read_text())["is_error"])

    def test_credentials_are_private_and_removed_after_run(self):
        auth = {"tokens": {"access_token": "test-access", "refresh_token": "test-refresh"}}
        observed = []

        def fake_run(command, **kwargs):
            home = Path(kwargs["env"]["CODEX_HOME"])
            observed.append(home)
            self.assertNotIn("CODEX_AUTH_JSON", kwargs["env"])
            self.assertEqual((home / "auth.json").stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads((home / "auth.json").read_text()), auth)
            return subprocess.CompletedProcess(command, 0, '{"type":"turn.completed","usage":{}}\n')

        with tempfile.TemporaryDirectory() as tmp:
            result = Path(tmp) / "result.json"
            with patch.dict("os.environ", {"CODEX_AUTH_JSON": json.dumps(auth)}), patch.object(sys, "argv", ["run_codex.py", "digest", "--result", str(result)]), patch.object(runner.subprocess, "run", side_effect=fake_run):
                runner.main()
            self.assertFalse(json.loads(result.read_text())["is_error"])
            self.assertNotIn("test-access", result.read_text())
        self.assertFalse(observed[0].exists())
