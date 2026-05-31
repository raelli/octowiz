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


SESSIONS_JSON = '[{"sessionId":"s1","name":"feat/auth","status":"idle","cwd":"/repo","pid":1234,"startedAt":1780000000}]'


class TestCliAdapterListSessions(unittest.TestCase):

    def test_list_sessions_returns_typed_session_info_list(self):
        from capabilities.cli_adapter import ClaudeCliAdapter, SessionInfo
        adapter = ClaudeCliAdapter(runner=FakeRunner(stdout=SESSIONS_JSON))
        result = adapter.list_sessions()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        s = result[0]
        self.assertIsInstance(s, SessionInfo)
        self.assertEqual(s.session_id, "s1")
        self.assertEqual(s.name, "feat/auth")
        self.assertEqual(s.status, "idle")
        self.assertEqual(s.cwd, "/repo")
        self.assertEqual(s.pid, 1234)
        self.assertEqual(s.started_at, 1780000000)

    def test_list_sessions_returns_empty_list_on_no_sessions(self):
        from capabilities.cli_adapter import ClaudeCliAdapter
        adapter = ClaudeCliAdapter(runner=FakeRunner(stdout="[]"))
        result = adapter.list_sessions()
        self.assertEqual(result, [])

    def test_list_sessions_returns_cli_error_when_supervisor_down(self):
        from capabilities.cli_adapter import ClaudeCliAdapter, CliError
        adapter = ClaudeCliAdapter(runner=FakeRunner(returncode=1, stderr="supervisor not running"))
        result = adapter.list_sessions()
        self.assertIsInstance(result, CliError)
        self.assertEqual(result.kind, "nonzero_exit")

    def test_list_sessions_passes_cwd_to_cli(self):
        from capabilities.cli_adapter import ClaudeCliAdapter
        runner = FakeRunner(stdout="[]")
        adapter = ClaudeCliAdapter(runner=runner)
        adapter.list_sessions(cwd="/projects/foo")
        self.assertIn("--cwd", runner.calls[0])
        self.assertIn("/projects/foo", runner.calls[0])


class TestCliAdapterControl(unittest.TestCase):

    def test_control_stop_returns_stdout_on_success(self):
        from capabilities.cli_adapter import ClaudeCliAdapter
        adapter = ClaudeCliAdapter(runner=FakeRunner(stdout="session stopped"))
        result = adapter.control("stop", "s1")
        self.assertEqual(result, "session stopped")

    def test_control_logs_returns_log_output(self):
        from capabilities.cli_adapter import ClaudeCliAdapter
        adapter = ClaudeCliAdapter(runner=FakeRunner(stdout="task log output"))
        result = adapter.control("logs", "s1")
        self.assertEqual(result, "task log output")

    def test_control_returns_cli_error_on_nonzero_exit(self):
        from capabilities.cli_adapter import ClaudeCliAdapter, CliError
        adapter = ClaudeCliAdapter(runner=FakeRunner(returncode=1, stderr="session not found"))
        result = adapter.control("stop", "s1")
        self.assertIsInstance(result, CliError)
        self.assertEqual(result.kind, "nonzero_exit")
        self.assertIn("session not found", result.message)

    def test_control_passes_op_and_session_id_to_cli(self):
        from capabilities.cli_adapter import ClaudeCliAdapter
        runner = FakeRunner()
        adapter = ClaudeCliAdapter(runner=runner)
        adapter.control("rm", "abc123")
        self.assertEqual(runner.calls[0], ["claude", "rm", "--", "abc123"])


if __name__ == "__main__":
    unittest.main()
