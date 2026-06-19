"""Integration test: real ClaudeAgentViewProvider banner parsing → handle_dispatch round-trip.

Verifies that a 'backgrounded · <id>' banner emitted by the claude CLI is correctly
parsed by ClaudeAgentViewProvider.dispatch(), and that the extracted session ID is
used correctly throughout the handle_dispatch polling loop.
"""
import asyncio
import json
import os
import sys
import unittest
from unittest.mock import patch

# providers is a top-level package (octowiz root is in pytest path).
# capabilities/dispatch lives under apps/a2a-agent/ — add that to sys.path.
_A2A_AGENT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "apps", "a2a-agent")
if _A2A_AGENT_DIR not in sys.path:
    sys.path.insert(0, _A2A_AGENT_DIR)

import session_owners

_FAST = {"poll_interval": 0.001, "timeout": 5.0}

_STOPPED_SESSION = json.dumps([{
    "id": "bg-xyz",
    "status": "stopped",
    "branch": "main",
    "repoRoot": "/repo",
    "needsInput": False,
    "createdAt": "2026-06-01T00:00:00Z",
}])

_NEEDS_INPUT_SESSION = json.dumps([{
    "id": "bg-xyz",
    "status": "running",
    "branch": "main",
    "repoRoot": "/repo",
    "needsInput": True,
    "createdAt": "2026-06-01T00:00:00Z",
}])


def _run(coro):
    return asyncio.run(coro)


class TestBannerToHandleDispatchRoundTrip(unittest.TestCase):

    def setUp(self):
        session_owners.clear()
        # These tests dispatch with cwd="/repo"; pin the allowlist so the path
        # guard accepts it regardless of the ambient OCTOWIZ_ALLOWED_ROOTS.
        self._env_patch = patch.dict(os.environ, {"OCTOWIZ_ALLOWED_ROOTS": "/repo"})
        self._env_patch.start()

    def tearDown(self):
        self._env_patch.stop()
        session_owners.clear()

    def _make_fake_run_claude(self, banner, agents_json, logs="task output"):
        """Returns a fake _run_claude that serves banner on --bg, agents JSON on agents, logs on logs."""
        calls = []

        def fake_run(args, cwd=None):
            calls.append(list(args))
            if len(args) >= 2 and args[0] == "--bg":
                return banner
            if args == ["agents", "--json"]:
                return agents_json
            if len(args) >= 2 and args[0] == "logs":
                return logs
            return ""

        fake_run.calls = calls
        return fake_run

    def test_banner_session_id_used_for_polling_and_logs(self):
        """Core contract: parsed session ID (not raw banner line) is used throughout dispatch."""
        from capabilities.dispatch import handle_dispatch
        from providers.claude_agent_view.provider import ClaudeAgentViewProvider
        import providers.claude_agent_view.provider as prov_mod

        fake = self._make_fake_run_claude(
            banner="backgrounded · bg-xyz feat/auth-work",
            agents_json=_STOPPED_SESSION,
            logs="build complete",
        )
        with patch.object(prov_mod, "_run_claude", fake):
            provider = ClaudeAgentViewProvider()
            result = _run(handle_dispatch(
                {"task": "run build", "cwd": "/repo", "_principal": "p1"},
                provider=provider, **_FAST,
            ))

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["session_id"], "bg-xyz")
        self.assertEqual(result["output"], "build complete")
        # logs call must use the parsed ID, not the raw banner
        self.assertIn(["logs", "--", "bg-xyz"], fake.calls)

    def test_ansi_banner_is_parsed_correctly(self):
        """ANSI escape codes in the banner are stripped before session ID extraction."""
        from capabilities.dispatch import handle_dispatch
        from providers.claude_agent_view.provider import ClaudeAgentViewProvider
        import providers.claude_agent_view.provider as prov_mod

        ansi_banner = "\x1b[32mbackgrounded · bg-xyz feat/auth-work\x1b[0m"
        fake = self._make_fake_run_claude(banner=ansi_banner, agents_json=_STOPPED_SESSION)
        with patch.object(prov_mod, "_run_claude", fake):
            provider = ClaudeAgentViewProvider()
            result = _run(handle_dispatch(
                {"task": "run build", "cwd": "/repo"},
                provider=provider, **_FAST,
            ))

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["session_id"], "bg-xyz")

    def test_unmatched_banner_surfaces_as_error_not_orphan(self):
        """If the banner doesn't match, dispatch returns an error — no orphaned session."""
        from capabilities.dispatch import handle_dispatch
        from providers.claude_agent_view.provider import ClaudeAgentViewProvider
        import providers.claude_agent_view.provider as prov_mod

        fake = self._make_fake_run_claude(
            banner="unexpected output format",
            agents_json="[]",
        )
        with patch.object(prov_mod, "_run_claude", fake):
            provider = ClaudeAgentViewProvider()
            result = _run(handle_dispatch(
                {"task": "run build", "cwd": "/repo"},
                provider=provider, **_FAST,
            ))

        self.assertEqual(result["status"], "error")
        self.assertIn("session", result["message"].lower())

    def test_successful_dispatch_registers_owner_while_active(self):
        """Successful dispatch registers the principal; ownership persists until terminal state.

        P1 fix: a completed session deregisters the owner. This test uses needs-input
        (non-terminal) so the ownership record is still live after handle_dispatch returns.
        """
        from capabilities.dispatch import handle_dispatch
        from providers.claude_agent_view.provider import ClaudeAgentViewProvider
        import providers.claude_agent_view.provider as prov_mod

        fake = self._make_fake_run_claude(
            banner="backgrounded · bg-xyz feat/auth-work",
            agents_json=_NEEDS_INPUT_SESSION,
        )
        with patch.object(prov_mod, "_run_claude", fake):
            provider = ClaudeAgentViewProvider()
            result = _run(handle_dispatch(
                {"task": "run build", "cwd": "/repo", "_principal": "p-abc"},
                provider=provider, **_FAST,
            ))

        self.assertEqual(result["status"], "needs-input")
        # Non-terminal outcome: owner is still registered.
        self.assertTrue(session_owners.check("bg-xyz", "p-abc"))
        self.assertFalse(session_owners.check("bg-xyz", "other"))

    def test_completed_dispatch_retains_ownership_for_cleanup(self):
        """Completed session keeps ownership so caller can run manage_agents logs/rm (issue #55)."""
        from capabilities.dispatch import handle_dispatch
        from providers.claude_agent_view.provider import ClaudeAgentViewProvider
        import providers.claude_agent_view.provider as prov_mod

        fake = self._make_fake_run_claude(
            banner="backgrounded · bg-xyz feat/auth-work",
            agents_json=_STOPPED_SESSION,
        )
        with patch.object(prov_mod, "_run_claude", fake):
            provider = ClaudeAgentViewProvider()
            _run(handle_dispatch(
                {"task": "run build", "cwd": "/repo", "_principal": "p-abc"},
                provider=provider, **_FAST,
            ))

        # Completed session: ownership is retained until the caller runs rm.
        self.assertTrue(session_owners.check("bg-xyz", "p-abc"))


if __name__ == "__main__":
    unittest.main()
