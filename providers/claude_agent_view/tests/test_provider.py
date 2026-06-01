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


def _make_dispatch_mock(banner, session_id_in_agents):
    """Return a _run_claude side-effect that serves a banner on --bg and a session list on agents."""
    sessions_json = json.dumps([
        {"id": session_id_in_agents, "status": "running", "branch": "main",
         "repoRoot": "/repo", "needsInput": False, "createdAt": "2026-05-30T00:00:00Z"}
    ])
    def fake(args, cwd=None):
        if len(args) >= 2 and args[0] == "--bg":
            return banner
        if args == ["agents", "--json"]:
            return sessions_json
        return ""
    return fake


class TestDispatch(unittest.TestCase):

    def test_dispatch_passes_cwd_to_subprocess_not_argv(self):
        from providers.claude_agent_view.provider import ClaudeAgentViewProvider
        with patch("providers.claude_agent_view.provider._run_claude",
                   side_effect=_make_dispatch_mock("backgrounded · bg-xyz feat/my-work", "bg-xyz")) as mock_run:
            session_id = ClaudeAgentViewProvider().dispatch("do something", "/some/repo")
            mock_run.assert_any_call(["--bg", "--", "do something"], cwd="/some/repo")
            self.assertEqual(session_id, "bg-xyz")

    def test_dispatch_parses_session_id_from_banner(self):
        from providers.claude_agent_view.provider import ClaudeAgentViewProvider
        with patch("providers.claude_agent_view.provider._run_claude",
                   side_effect=_make_dispatch_mock("backgrounded • s-abc123 some-name", "s-abc123")):
            session_id = ClaudeAgentViewProvider().dispatch("run tests", "/repo")
            self.assertEqual(session_id, "s-abc123")

    def test_dispatch_strips_ansi_before_parsing(self):
        from providers.claude_agent_view.provider import ClaudeAgentViewProvider
        with patch("providers.claude_agent_view.provider._run_claude",
                   side_effect=_make_dispatch_mock(
                       "\x1b[32mbackgrounded · ansi-id work-name\x1b[0m", "ansi-id")):
            session_id = ClaudeAgentViewProvider().dispatch("run tests", "/repo")
            self.assertEqual(session_id, "ansi-id")

    def test_dispatch_returns_empty_string_when_banner_not_matched(self):
        from providers.claude_agent_view.provider import ClaudeAgentViewProvider
        with patch("providers.claude_agent_view.provider._run_claude", return_value="unexpected output format"):
            session_id = ClaudeAgentViewProvider().dispatch("run tests", "/repo")
            self.assertEqual(session_id, "")

    def test_dispatch_resolves_short_banner_prefix_to_full_uuid(self):
        """Core fix: banner emits 8-char prefix; dispatch must return the full UUID."""
        from providers.claude_agent_view.provider import ClaudeAgentViewProvider
        full_uuid = "e5694b8e-934e-4818-aeff-747298d771d3"
        with patch("providers.claude_agent_view.provider._run_claude",
                   side_effect=_make_dispatch_mock(
                       "backgrounded · e5694b8e echo-task", full_uuid)):
            session_id = ClaudeAgentViewProvider().dispatch("echo-task", "/tmp")
            self.assertEqual(session_id, full_uuid)

    def test_dispatch_falls_back_to_short_id_when_resolution_fails(self):
        """If the session does not appear in agents --json within retries, return short id."""
        from providers.claude_agent_view.provider import ClaudeAgentViewProvider
        def fake(args, cwd=None):
            if len(args) >= 2 and args[0] == "--bg":
                return "backgrounded · shortid session-name"
            if args == ["agents", "--json"]:
                return "[]"  # session not yet visible
            return ""
        with patch("providers.claude_agent_view.provider._run_claude", side_effect=fake):
            with patch("providers.claude_agent_view.provider.time") as mock_time:
                mock_time.sleep = lambda _: None  # skip real sleeps in test
                session_id = ClaudeAgentViewProvider().dispatch("task", "/repo")
            self.assertEqual(session_id, "shortid")


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
