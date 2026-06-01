"""Tests for AgentSession parser."""
import json
import unittest

FIXTURE_RUNNING = json.dumps([
    {
        "id": "bg-abc123",
        "status": "running",
        "branch": "feat/my-feature",
        "repoRoot": "/Users/dev/myrepo",
        "needsInput": False,
        "createdAt": "2026-05-30T08:00:00Z",
    }
])

FIXTURE_NEEDS_INPUT = json.dumps([
    {
        "id": "bg-def456",
        "status": "waiting_for_input",
        "branch": "main",
        "repoRoot": "/Users/dev/myrepo",
        "needsInput": True,
        "createdAt": "2026-05-30T09:00:00Z",
    }
])

FIXTURE_EMPTY = json.dumps([])
FIXTURE_MALFORMED = "this is not json {"
FIXTURE_WRONG_TYPE = json.dumps({"not": "a list"})


class TestParseSessions(unittest.TestCase):

    def test_parses_running_session(self):
        from providers.claude_agent_view.parser import parse_sessions
        sessions = parse_sessions(FIXTURE_RUNNING)
        self.assertEqual(len(sessions), 1)
        s = sessions[0]
        self.assertEqual(s.id, "bg-abc123")
        self.assertEqual(s.status, "running")
        self.assertEqual(s.branch, "feat/my-feature")
        self.assertFalse(s.needs_input)
        self.assertFalse(s.ready_for_review)

    def test_parses_needs_input_session(self):
        from providers.claude_agent_view.parser import parse_sessions
        sessions = parse_sessions(FIXTURE_NEEDS_INPUT)
        self.assertEqual(len(sessions), 1)
        s = sessions[0]
        self.assertEqual(s.id, "bg-def456")
        self.assertEqual(s.status, "waiting")
        self.assertTrue(s.needs_input)

    def test_returns_empty_list_for_empty_array(self):
        from providers.claude_agent_view.parser import parse_sessions
        self.assertEqual(parse_sessions(FIXTURE_EMPTY), [])

    def test_returns_empty_list_on_malformed_json(self):
        from providers.claude_agent_view.parser import parse_sessions
        self.assertEqual(parse_sessions(FIXTURE_MALFORMED), [])

    def test_returns_empty_list_when_output_is_not_a_list(self):
        from providers.claude_agent_view.parser import parse_sessions
        self.assertEqual(parse_sessions(FIXTURE_WRONG_TYPE), [])

    def test_never_raises_on_unknown_status_value(self):
        fixture = json.dumps([{"id": "x", "status": "some_future_status", "branch": None,
                               "repoRoot": None, "needsInput": False, "createdAt": None}])
        from providers.claude_agent_view.parser import parse_sessions
        sessions = parse_sessions(fixture)
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].status, "some_future_status")


class TestParseSessionsRealCliFormat(unittest.TestCase):
    """Tests using the real `claude agents --json` field names (sessionId, cwd, startedAt)."""

    REAL_SESSION = json.dumps([{
        "pid": 12345,
        "cwd": "/projects/myapp",
        "kind": "background",
        "startedAt": 1780281968489,
        "sessionId": "e5694b8e-934e-4818-aeff-747298d771d3",
        "name": "refactor auth",
        "status": "idle",
    }])

    REAL_BUSY_SESSION = json.dumps([{
        "sessionId": "abcd1234-0000-0000-0000-000000000000",
        "status": "busy",
        "cwd": "/repo",
        "startedAt": 1780000000000,
    }])

    def test_parses_real_cli_session_id(self):
        from providers.claude_agent_view.parser import parse_sessions
        sessions = parse_sessions(self.REAL_SESSION)
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].id, "e5694b8e-934e-4818-aeff-747298d771d3")

    def test_parses_idle_status(self):
        from providers.claude_agent_view.parser import parse_sessions
        sessions = parse_sessions(self.REAL_SESSION)
        self.assertEqual(sessions[0].status, "idle")

    def test_parses_busy_status_as_running(self):
        from providers.claude_agent_view.parser import parse_sessions
        sessions = parse_sessions(self.REAL_BUSY_SESSION)
        self.assertEqual(sessions[0].status, "running")

    def test_parses_cwd_as_repo(self):
        from providers.claude_agent_view.parser import parse_sessions
        sessions = parse_sessions(self.REAL_SESSION)
        self.assertEqual(sessions[0].repo, "/projects/myapp")

    def test_parses_started_at_as_created_at(self):
        from providers.claude_agent_view.parser import parse_sessions
        sessions = parse_sessions(self.REAL_SESSION)
        self.assertEqual(sessions[0].created_at, "1780281968489")

    def test_legacy_id_field_still_works(self):
        """Mocked tests use 'id' not 'sessionId' — both must work."""
        from providers.claude_agent_view.parser import parse_sessions
        legacy = json.dumps([{"id": "bg-abc", "status": "running", "repoRoot": "/repo",
                               "needsInput": False, "createdAt": "2026-05-30T08:00:00Z"}])
        sessions = parse_sessions(legacy)
        self.assertEqual(sessions[0].id, "bg-abc")
        self.assertEqual(sessions[0].repo, "/repo")

    def test_idle_session_is_ready_for_review(self):
        """idle is the real CLI terminal state — must set ready_for_review=True."""
        from providers.claude_agent_view.parser import parse_sessions
        sessions = parse_sessions(self.REAL_SESSION)
        self.assertEqual(sessions[0].status, "idle")
        self.assertTrue(sessions[0].ready_for_review)

    def test_stopped_session_is_ready_for_review(self):
        from providers.claude_agent_view.parser import parse_sessions
        fixture = json.dumps([{"id": "s1", "status": "stopped", "needsInput": False}])
        sessions = parse_sessions(fixture)
        self.assertTrue(sessions[0].ready_for_review)

    def test_needs_input_session_is_not_ready_for_review(self):
        from providers.claude_agent_view.parser import parse_sessions
        fixture = json.dumps([{"id": "s1", "status": "idle", "needsInput": True}])
        sessions = parse_sessions(fixture)
        self.assertFalse(sessions[0].ready_for_review)

    def test_running_session_is_not_ready_for_review(self):
        from providers.claude_agent_view.parser import parse_sessions
        sessions = parse_sessions(self.REAL_BUSY_SESSION)
        self.assertFalse(sessions[0].ready_for_review)


if __name__ == "__main__":
    unittest.main()
