"""Tests for ClaudeAgentViewProvider — mocks _run_claude at the subprocess seam."""
import json
import unittest
from unittest.mock import patch

FIXTURE_SESSIONS = json.dumps([
    {"id": "bg-abc", "status": "running", "branch": "main",
     "repoRoot": "/repo", "needsInput": False, "createdAt": "2026-05-30T08:00:00Z"}
])


class TestListSessions(unittest.TestCase):

    def test_returns_sessions_from_cli(self):
        with patch("providers.claude_agent_view.provider._run_claude") as mock_run:
            mock_run.return_value = FIXTURE_SESSIONS
            from providers.claude_agent_view.provider import ClaudeAgentViewProvider
            provider = ClaudeAgentViewProvider()
            sessions = provider.list_sessions()
            self.assertEqual(len(sessions), 1)
            self.assertEqual(sessions[0].id, "bg-abc")
            mock_run.assert_called_once_with(["agents", "--json"])

    def test_returns_empty_list_when_cli_absent(self):
        with patch("providers.claude_agent_view.provider._run_claude") as mock_run:
            mock_run.return_value = ""
            from providers.claude_agent_view.provider import ClaudeAgentViewProvider
            provider = ClaudeAgentViewProvider()
            sessions = provider.list_sessions()
            self.assertEqual(sessions, [])

    def test_returns_empty_list_when_cli_errors(self):
        with patch("providers.claude_agent_view.provider._run_claude") as mock_run:
            mock_run.side_effect = FileNotFoundError("claude not found")
            from providers.claude_agent_view.provider import ClaudeAgentViewProvider
            provider = ClaudeAgentViewProvider()
            sessions = provider.list_sessions()
            self.assertEqual(sessions, [])


class TestGetLogs(unittest.TestCase):

    def test_get_logs_calls_claude_logs(self):
        with patch("providers.claude_agent_view.provider._run_claude") as mock_run:
            mock_run.return_value = "log output here"
            from providers.claude_agent_view.provider import ClaudeAgentViewProvider
            provider = ClaudeAgentViewProvider()
            logs = provider.get_logs("bg-abc")
            self.assertEqual(logs, "log output here")
            mock_run.assert_called_once_with(["logs", "--", "bg-abc"])


class TestStop(unittest.TestCase):

    def test_stop_calls_claude_stop(self):
        with patch("providers.claude_agent_view.provider._run_claude") as mock_run:
            mock_run.return_value = ""
            from providers.claude_agent_view.provider import ClaudeAgentViewProvider
            provider = ClaudeAgentViewProvider()
            provider.stop("bg-abc")
            mock_run.assert_called_once_with(["stop", "--", "bg-abc"])


class TestDispatch(unittest.TestCase):

    def test_dispatch_passes_cwd_to_subprocess_not_argv(self):
        with patch("providers.claude_agent_view.provider._run_claude") as mock_run:
            mock_run.return_value = "backgrounded · bg-xyz feat/my-work"
            from providers.claude_agent_view.provider import ClaudeAgentViewProvider
            session_id = ClaudeAgentViewProvider().dispatch("do something", "/some/repo")
            mock_run.assert_called_once_with(["--bg", "--", "do something"], cwd="/some/repo")
            self.assertEqual(session_id, "bg-xyz")

    def test_dispatch_parses_session_id_from_banner(self):
        with patch("providers.claude_agent_view.provider._run_claude") as mock_run:
            mock_run.return_value = "backgrounded • s-abc123 some-name"
            from providers.claude_agent_view.provider import ClaudeAgentViewProvider
            session_id = ClaudeAgentViewProvider().dispatch("run tests", "/repo")
            self.assertEqual(session_id, "s-abc123")

    def test_dispatch_strips_ansi_before_parsing(self):
        with patch("providers.claude_agent_view.provider._run_claude") as mock_run:
            mock_run.return_value = "\x1b[32mbackgrounded · ansi-id work-name\x1b[0m"
            from providers.claude_agent_view.provider import ClaudeAgentViewProvider
            session_id = ClaudeAgentViewProvider().dispatch("run tests", "/repo")
            self.assertEqual(session_id, "ansi-id")

    def test_dispatch_returns_empty_string_when_banner_not_matched(self):
        with patch("providers.claude_agent_view.provider._run_claude") as mock_run:
            mock_run.return_value = "unexpected output format"
            from providers.claude_agent_view.provider import ClaudeAgentViewProvider
            session_id = ClaudeAgentViewProvider().dispatch("run tests", "/repo")
            self.assertEqual(session_id, "")


class TestValidation(unittest.TestCase):

    def test_dispatch_rejects_repo_starting_with_dash(self):
        from providers.claude_agent_view.provider import ClaudeAgentViewProvider
        with self.assertRaises(ValueError):
            ClaudeAgentViewProvider().dispatch("do something", "-malicious")

    def test_dispatch_rejects_task_starting_with_dash(self):
        from providers.claude_agent_view.provider import ClaudeAgentViewProvider
        with self.assertRaises(ValueError):
            ClaudeAgentViewProvider().dispatch("--inject", "/valid/repo")

    def test_get_logs_rejects_invalid_run_id(self):
        from providers.claude_agent_view.provider import ClaudeAgentViewProvider
        with self.assertRaises(ValueError):
            ClaudeAgentViewProvider().get_logs("--json")

    def test_stop_rejects_invalid_run_id(self):
        from providers.claude_agent_view.provider import ClaudeAgentViewProvider
        with self.assertRaises(ValueError):
            ClaudeAgentViewProvider().stop("../../etc/passwd")


if __name__ == "__main__":
    unittest.main()
