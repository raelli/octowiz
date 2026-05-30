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


if __name__ == "__main__":
    unittest.main()
