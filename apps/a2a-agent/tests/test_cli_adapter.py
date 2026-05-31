"""Tests for ClaudeCliAdapter — single seam for all `claude` CLI invocations."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.pop("OCTOWIZ_INBOUND_SECRET", None)

import unittest
from typing import List, Tuple


class FakeRunner:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.calls: list = []

    def __call__(self, args: List[str]) -> Tuple[int, str, str]:
        self.calls.append(list(args))
        return self.returncode, self.stdout, self.stderr


PLAIN_OUTPUT = "backgrounded · b188cbb0 (idle — send a prompt to start)"
ANSI_OUTPUT = "backgrounded · \x1b[36mb188cbb0\x1b[39m (idle — send a prompt to start)"
MIDDLE_DOT_OUTPUT = "backgrounded • b188cbb0 (idle — send a prompt to start)"


class TestCliAdapterStartSession(unittest.TestCase):

    def test_start_session_returns_session_started_on_success(self):
        from capabilities.cli_adapter import ClaudeCliAdapter, SessionStarted
        adapter = ClaudeCliAdapter(runner=FakeRunner(stdout=PLAIN_OUTPUT))
        result = adapter.start_session(task="fix the bug", cwd="/repo")
        self.assertIsInstance(result, SessionStarted)
        self.assertEqual(result.session_id, "b188cbb0")

    def test_start_session_strips_ansi_before_parsing(self):
        from capabilities.cli_adapter import ClaudeCliAdapter, SessionStarted
        adapter = ClaudeCliAdapter(runner=FakeRunner(stdout=ANSI_OUTPUT))
        result = adapter.start_session(task="fix the bug", cwd="/repo")
        self.assertIsInstance(result, SessionStarted)
        self.assertEqual(result.session_id, "b188cbb0")

    def test_start_session_accepts_middle_dot_separator(self):
        from capabilities.cli_adapter import ClaudeCliAdapter, SessionStarted
        adapter = ClaudeCliAdapter(runner=FakeRunner(stdout=MIDDLE_DOT_OUTPUT))
        result = adapter.start_session(task="fix the bug", cwd="/repo")
        self.assertIsInstance(result, SessionStarted)
        self.assertEqual(result.session_id, "b188cbb0")

    def test_start_session_returns_cli_error_on_nonzero_exit(self):
        from capabilities.cli_adapter import ClaudeCliAdapter, CliError
        adapter = ClaudeCliAdapter(runner=FakeRunner(returncode=1, stderr="permission denied"))
        result = adapter.start_session(task="fix the bug", cwd="/repo")
        self.assertIsInstance(result, CliError)
        self.assertEqual(result.kind, "nonzero_exit")
        self.assertIn("permission denied", result.message)

    def test_start_session_returns_cli_error_on_parse_failure(self):
        from capabilities.cli_adapter import ClaudeCliAdapter, CliError
        adapter = ClaudeCliAdapter(runner=FakeRunner(stdout="unexpected output"))
        result = adapter.start_session(task="fix the bug", cwd="/repo")
        self.assertIsInstance(result, CliError)
        self.assertEqual(result.kind, "parse_failure")


if __name__ == "__main__":
    unittest.main()
