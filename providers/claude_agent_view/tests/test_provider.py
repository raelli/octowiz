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
            mock_run.assert_called_once_with(["logs", "bg-abc"])


class TestStop(unittest.TestCase):

    def test_stop_calls_claude_stop(self):
        with patch("providers.claude_agent_view.provider._run_claude") as mock_run:
            mock_run.return_value = ""
            from providers.claude_agent_view.provider import ClaudeAgentViewProvider
            provider = ClaudeAgentViewProvider()
            provider.stop("bg-abc")
            mock_run.assert_called_once_with(["stop", "bg-abc"])


if __name__ == "__main__":
    unittest.main()
