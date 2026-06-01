"""Tests for octowiz.dispatch capability — fire-and-observe session wrapper."""
import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest

# A minimal stand-in for AgentSession without importing the providers package.
from dataclasses import dataclass
from typing import Optional


@dataclass
class _Session:
    id: str
    status: str
    needs_input: bool = False
    branch: Optional[str] = None
    repo: Optional[str] = None
    ready_for_review: bool = False
    created_at: Optional[str] = None


class _MockProvider:
    """Simulates ClaudeAgentViewProvider for capability tests."""

    def __init__(self, session_id="s1", dispatch_exc=None, status_sequence=(), log_output="task output"):
        self._session_id = session_id
        self._dispatch_exc = dispatch_exc
        self._status_iter = iter(status_sequence)
        self._log_output = log_output
        self.dispatched_task = None
        self.dispatched_cwd = None
        self.logs_calls = []

    def dispatch(self, task, cwd):
        if self._dispatch_exc:
            raise self._dispatch_exc
        self.dispatched_task = task
        self.dispatched_cwd = cwd
        return self._session_id

    def get_status(self, session_id):
        try:
            return next(self._status_iter)
        except StopIteration:
            return None

    def get_logs(self, session_id):
        self.logs_calls.append(session_id)
        return self._log_output


def _run(coro):
    return asyncio.run(coro)


_FAST = {"poll_interval": 0.001, "timeout": 5.0}
_INSTANT_TIMEOUT = {"poll_interval": 0.001, "timeout": 0.005}


class TestDispatchHappyPaths(unittest.TestCase):

    def test_session_completes_returns_completed_artifact(self):
        from capabilities.dispatch import handle_dispatch
        provider = _MockProvider(
            status_sequence=[
                _Session("s1", "running"),
                _Session("s1", "stopped"),
            ]
        )
        result = _run(handle_dispatch(
            {"task": "add tests", "cwd": "/repo"},
            provider=provider, **_FAST,
        ))
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["session_id"], "s1")
        self.assertEqual(result["output"], "task output")

    def test_session_needs_input_returns_needs_input_artifact(self):
        from capabilities.dispatch import handle_dispatch
        provider = _MockProvider(
            status_sequence=[
                _Session("s1", "running"),
                _Session("s1", "running", needs_input=True),
            ]
        )
        result = _run(handle_dispatch(
            {"task": "do something", "cwd": "/repo"},
            provider=provider, **_FAST,
        ))
        self.assertEqual(result["status"], "needs-input")
        self.assertEqual(result["session_id"], "s1")
        self.assertIn("output", result)

    def test_session_errors_returns_error_artifact_with_output(self):
        from capabilities.dispatch import handle_dispatch
        provider = _MockProvider(
            status_sequence=[
                _Session("s1", "running"),
                _Session("s1", "error"),
            ],
            log_output="crash traceback here",
        )
        result = _run(handle_dispatch(
            {"task": "do something", "cwd": "/repo"},
            provider=provider, **_FAST,
        ))
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["session_id"], "s1")
        self.assertEqual(result["output"], "crash traceback here")

    def test_session_not_yet_in_list_then_completes(self):
        from capabilities.dispatch import handle_dispatch
        provider = _MockProvider(
            status_sequence=[
                None,
                None,
                _Session("s1", "stopped"),
            ]
        )
        result = _run(handle_dispatch(
            {"task": "add tests", "cwd": "/repo"},
            provider=provider, **_FAST,
        ))
        self.assertEqual(result["status"], "completed")

    def test_logs_fetched_with_correct_session_id(self):
        from capabilities.dispatch import handle_dispatch
        provider = _MockProvider(
            session_id="bg-abc",
            status_sequence=[_Session("bg-abc", "stopped")],
        )
        _run(handle_dispatch(
            {"task": "add tests", "cwd": "/repo"},
            provider=provider, **_FAST,
        ))
        self.assertEqual(provider.logs_calls, ["bg-abc"])

    def test_task_and_cwd_forwarded_to_provider(self):
        from capabilities.dispatch import handle_dispatch
        provider = _MockProvider(status_sequence=[_Session("s1", "stopped")])
        _run(handle_dispatch(
            {"task": "refactor auth", "cwd": "/projects/myapp"},
            provider=provider, **_FAST,
        ))
        self.assertEqual(provider.dispatched_task, "refactor auth")
        self.assertEqual(provider.dispatched_cwd, "/projects/myapp")


class TestDispatchIdleTerminalState(unittest.TestCase):
    """Verify that the real claude CLI status 'idle' is treated as completed."""

    def setUp(self):
        import session_owners
        session_owners.clear()

    def tearDown(self):
        import session_owners
        session_owners.clear()

    def test_idle_status_returns_completed(self):
        from capabilities.dispatch import handle_dispatch
        provider = _MockProvider(
            session_id="s-idle",
            status_sequence=[_Session("s-idle", "idle")],
            log_output="task finished",
        )
        result = _run(handle_dispatch(
            {"task": "echo hi", "cwd": "/repo"},
            provider=provider, **_FAST,
        ))
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["session_id"], "s-idle")
        self.assertEqual(result["output"], "task finished")

    def test_busy_status_keeps_polling(self):
        from capabilities.dispatch import handle_dispatch
        provider = _MockProvider(
            session_id="s-busy",
            status_sequence=[
                _Session("s-busy", "busy"),
                _Session("s-busy", "busy"),
                _Session("s-busy", "idle"),
            ],
        )
        result = _run(handle_dispatch(
            {"task": "echo hi", "cwd": "/repo"},
            provider=provider, **_FAST,
        ))
        self.assertEqual(result["status"], "completed")


class TestDispatchValidation(unittest.TestCase):

    def test_missing_task_returns_error(self):
        from capabilities.dispatch import handle_dispatch
        result = _run(handle_dispatch({"cwd": "/repo"}))
        self.assertEqual(result["status"], "error")
        self.assertIn("task", result["message"])

    def test_missing_cwd_returns_error(self):
        from capabilities.dispatch import handle_dispatch
        result = _run(handle_dispatch({"task": "do something"}))
        self.assertEqual(result["status"], "error")
        self.assertIn("cwd", result["message"])

    def test_task_starting_with_dash_returns_error(self):
        from capabilities.dispatch import handle_dispatch
        result = _run(handle_dispatch({"task": "--inject", "cwd": "/repo"}))
        self.assertEqual(result["status"], "error")

    def test_dispatch_raises_returns_error(self):
        from capabilities.dispatch import handle_dispatch
        provider = _MockProvider(dispatch_exc=RuntimeError("claude not found"))
        result = _run(handle_dispatch(
            {"task": "add tests", "cwd": "/repo"},
            provider=provider, **_FAST,
        ))
        self.assertEqual(result["status"], "error")
        self.assertIn("claude not found", result["message"])

    def test_empty_session_id_returns_error(self):
        from capabilities.dispatch import handle_dispatch
        provider = _MockProvider(session_id="")
        result = _run(handle_dispatch(
            {"task": "add tests", "cwd": "/repo"},
            provider=provider, **_FAST,
        ))
        self.assertEqual(result["status"], "error")
        self.assertIn("session", result["message"].lower())

    def test_timeout_returns_error_with_session_id(self):
        from capabilities.dispatch import handle_dispatch
        provider = _MockProvider(status_sequence=[_Session("s1", "running")] * 100)
        result = _run(handle_dispatch(
            {"task": "add tests", "cwd": "/repo"},
            provider=provider, **_INSTANT_TIMEOUT,
        ))
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["session_id"], "s1")
        self.assertIn("timeout", result["message"].lower())

    def test_relative_cwd_returns_error(self):
        """P1: relative cwd must be rejected before dispatch."""
        from capabilities.dispatch import handle_dispatch
        provider = _MockProvider(status_sequence=[_Session("s1", "stopped")])
        result = _run(handle_dispatch(
            {"task": "add tests", "cwd": "relative/path"},
            provider=provider, **_FAST,
        ))
        self.assertEqual(result["status"], "error")
        self.assertIn("absolute", result["message"])

    def test_allowed_roots_blocks_outside_cwd(self):
        """P1: cwd outside OCTOWIZ_ALLOWED_ROOTS must be rejected."""
        import unittest.mock
        from capabilities.dispatch import handle_dispatch
        provider = _MockProvider(status_sequence=[_Session("s1", "stopped")])
        with unittest.mock.patch.dict(os.environ, {"OCTOWIZ_ALLOWED_ROOTS": "/allowed"}):
            result = _run(handle_dispatch(
                {"task": "add tests", "cwd": "/other/path"},
                provider=provider, **_FAST,
            ))
        self.assertEqual(result["status"], "error")
        self.assertIn("allowed root", result["message"])


class TestDispatchOwnershipRegistration(unittest.TestCase):

    def setUp(self):
        import session_owners
        session_owners.clear()

    def tearDown(self):
        import session_owners
        session_owners.clear()

    def test_successful_dispatch_registers_session_owner_while_running(self):
        """P1: ownership is registered while a session is still alive (needs-input)."""
        import session_owners
        from capabilities.dispatch import handle_dispatch
        provider = _MockProvider(
            session_id="reg-s1",
            status_sequence=[
                _Session("reg-s1", "running"),
                _Session("reg-s1", "running", needs_input=True),
            ],
        )
        result = _run(handle_dispatch(
            {"task": "add tests", "cwd": "/repo", "_principal": "p-abc"},
            provider=provider, **_FAST,
        ))
        self.assertEqual(result["status"], "needs-input")
        # Session is still alive (needs-input does not deregister).
        self.assertTrue(session_owners.check("reg-s1", "p-abc"))
        self.assertFalse(session_owners.check("reg-s1", "other-principal"))

    def test_completed_session_retains_ownership_for_cleanup(self):
        """Ownership is kept after completion so caller can still run manage_agents logs/rm (issue #55)."""
        import session_owners
        from capabilities.dispatch import handle_dispatch
        provider = _MockProvider(
            session_id="reg-s2",
            status_sequence=[_Session("reg-s2", "stopped")],
        )
        _run(handle_dispatch(
            {"task": "add tests", "cwd": "/repo", "_principal": "p-abc"},
            provider=provider, **_FAST,
        ))
        self.assertTrue(session_owners.check("reg-s2", "p-abc"))

    def test_error_session_retains_ownership_for_cleanup(self):
        """Ownership is kept after error so caller can still run manage_agents logs/rm (issue #55)."""
        import session_owners
        from capabilities.dispatch import handle_dispatch
        provider = _MockProvider(
            session_id="reg-s3",
            status_sequence=[_Session("reg-s3", "error")],
        )
        _run(handle_dispatch(
            {"task": "add tests", "cwd": "/repo", "_principal": "p-abc"},
            provider=provider, **_FAST,
        ))
        self.assertTrue(session_owners.check("reg-s3", "p-abc"))

    def test_failed_dispatch_does_not_register_ownership(self):
        import session_owners
        from capabilities.dispatch import handle_dispatch
        provider = _MockProvider(dispatch_exc=RuntimeError("claude not found"))
        _run(handle_dispatch(
            {"task": "add tests", "cwd": "/repo", "_principal": "p-abc"},
            provider=provider, **_FAST,
        ))
        self.assertFalse(session_owners.check("any-id", "p-abc"))

    def test_empty_session_id_does_not_register_ownership(self):
        import session_owners
        from capabilities.dispatch import handle_dispatch
        provider = _MockProvider(session_id="")
        _run(handle_dispatch(
            {"task": "add tests", "cwd": "/repo", "_principal": "p-abc"},
            provider=provider, **_FAST,
        ))
        self.assertFalse(session_owners.check("", "p-abc"))


class TestDispatchRouting(unittest.TestCase):
    """Smoke test: verify dispatch.py routes octowiz.dispatch to the capability."""

    def test_dispatch_routes_to_capability(self):
        from unittest.mock import AsyncMock, patch
        import importlib
        import dispatch as dispatch_mod
        importlib.reload(dispatch_mod)

        mock_result = {"status": "completed", "session_id": "s1", "output": "done"}
        with patch("capabilities.dispatch.handle_dispatch", new=AsyncMock(return_value=mock_result)) as mock_h:
            result = asyncio.run(dispatch_mod.dispatch({
                "capability": "octowiz.dispatch",
                "task": "add tests",
                "cwd": "/repo",
            }))
        self.assertEqual(result["status"], "completed")
        mock_h.assert_called_once()


class TestDispatchSessionStateMachine(unittest.TestCase):
    """Test DispatchSession state transitions directly."""

    def setUp(self):
        import session_owners
        session_owners.clear()

    def tearDown(self):
        import session_owners
        session_owners.clear()

    def _make_session(self, provider, poll_interval=0.001, timeout=5.0):
        from capabilities.dispatch import DispatchSession
        return DispatchSession(
            "add tests",
            "/repo",
            "p-test",
            provider=provider,
            poll_interval=poll_interval,
            timeout=timeout,
        )

    def test_initial_state_is_pending(self):
        from capabilities.dispatch import DispatchSession, DispatchSessionState
        provider = _MockProvider(status_sequence=[])
        session = DispatchSession(
            "task", "/repo", "p1",
            provider=provider, poll_interval=0.001, timeout=5.0,
        )
        self.assertEqual(session.state, DispatchSessionState.PENDING)

    def test_start_transitions_pending_to_running(self):
        from capabilities.dispatch import DispatchSessionState
        provider = _MockProvider(status_sequence=[_Session("s1", "running")])
        session = self._make_session(provider)
        _run(session.start())
        self.assertEqual(session.state, DispatchSessionState.RUNNING)
        self.assertEqual(session.session_id, "s1")

    def test_poll_returns_needs_input_when_session_awaits_input(self):
        from capabilities.dispatch import DispatchSessionState
        provider = _MockProvider(
            session_id="s1",
            status_sequence=[_Session("s1", "running", needs_input=True)],
        )
        session = self._make_session(provider)
        _run(session.start())
        state = _run(session.poll())
        self.assertEqual(state, DispatchSessionState.NEEDS_INPUT)

    def test_poll_returns_done_when_terminal_status(self):
        from capabilities.dispatch import DispatchSessionState
        provider = _MockProvider(
            session_id="s1",
            status_sequence=[_Session("s1", "stopped")],
        )
        session = self._make_session(provider)
        _run(session.start())
        state = _run(session.poll())
        self.assertEqual(state, DispatchSessionState.DONE)

    def test_poll_returns_done_when_error_status(self):
        from capabilities.dispatch import DispatchSessionState
        provider = _MockProvider(
            session_id="s1",
            status_sequence=[_Session("s1", "error")],
        )
        session = self._make_session(provider)
        _run(session.start())
        state = _run(session.poll())
        self.assertEqual(state, DispatchSessionState.DONE)

    def test_poll_returns_running_when_session_not_visible_yet(self):
        from capabilities.dispatch import DispatchSessionState
        provider = _MockProvider(
            session_id="s1",
            status_sequence=[None, _Session("s1", "stopped")],
        )
        session = self._make_session(provider)
        _run(session.start())
        # First poll: session not in supervisor yet
        state = _run(session.poll())
        self.assertEqual(state, DispatchSessionState.RUNNING)

    def test_run_drives_to_done_completed(self):
        from capabilities.dispatch import DispatchSessionState
        provider = _MockProvider(
            session_id="s1",
            status_sequence=[_Session("s1", "stopped")],
        )
        session = self._make_session(provider)
        _run(session.start())
        result = _run(session.run())
        self.assertEqual(result["status"], "completed")
        self.assertEqual(session.state, DispatchSessionState.DONE)

    def test_run_drives_to_done_error(self):
        from capabilities.dispatch import DispatchSessionState
        provider = _MockProvider(
            session_id="s1",
            status_sequence=[_Session("s1", "error")],
            log_output="crash log",
        )
        session = self._make_session(provider)
        _run(session.start())
        result = _run(session.run())
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["output"], "crash log")
        self.assertEqual(session.state, DispatchSessionState.DONE)

    def test_run_drives_to_needs_input(self):
        from capabilities.dispatch import DispatchSessionState
        provider = _MockProvider(
            session_id="s1",
            status_sequence=[_Session("s1", "running", needs_input=True)],
        )
        session = self._make_session(provider)
        _run(session.start())
        result = _run(session.run())
        self.assertEqual(result["status"], "needs-input")
        self.assertEqual(session.state, DispatchSessionState.NEEDS_INPUT)

    def test_run_times_out_as_timed_out_state(self):
        from capabilities.dispatch import DispatchSessionState
        provider = _MockProvider(
            session_id="s1",
            status_sequence=[_Session("s1", "running")] * 100,
        )
        session = self._make_session(provider, timeout=0.005)
        _run(session.start())
        result = _run(session.run())
        self.assertEqual(result["status"], "error")
        self.assertIn("timeout", result["message"].lower())
        self.assertEqual(session.state, DispatchSessionState.TIMED_OUT)


class TestDispatchSessionOrphaned(unittest.TestCase):
    """Test ORPHANED state: session never observed by supervisor before deadline.

    The discriminator between TIMED_OUT and ORPHANED:
    - ORPHANED: get_status always returned None (supervisor never saw the session).
      This indicates the A2A server restarted mid-poll and the lease is held but
      the session is lost. mark_orphaned() is called from run().
    - TIMED_OUT: session was observed at least once but did not complete in time.
    """

    def setUp(self):
        import session_owners
        session_owners.clear()

    def tearDown(self):
        import session_owners
        session_owners.clear()

    def test_run_orphans_when_session_never_observed(self):
        """ORPHANED: session is dispatched but supervisor never returns a non-None status."""
        from capabilities.dispatch import DispatchSession, DispatchSessionState
        # Provider always returns None from get_status — session never observable.
        provider = _MockProvider(
            session_id="s-orphan",
            status_sequence=[],  # StopIteration → None from _MockProvider.get_status
        )
        session = DispatchSession(
            "long task", "/repo", "p1",
            provider=provider, poll_interval=0.001, timeout=0.005,
        )
        _run(session.start())
        result = _run(session.run())
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["message"], "dispatch timed out (orphaned)")
        self.assertEqual(session.state, DispatchSessionState.ORPHANED)

    def test_run_orphan_logs_session_id(self):
        """ORPHANED run logs the session id with 'orphaned' in the message."""
        import logging
        from capabilities.dispatch import DispatchSession
        provider = _MockProvider(
            session_id="s-orphan-log",
            status_sequence=[],
        )
        session = DispatchSession(
            "long task", "/repo", "p1",
            provider=provider, poll_interval=0.001, timeout=0.005,
        )
        _run(session.start())

        with self.assertLogs("capabilities.dispatch", level=logging.WARNING) as cm:
            _run(session.run())

        self.assertTrue(
            any("s-orphan-log" in line and "orphaned" in line for line in cm.output),
            msg=f"Expected orphan log with session id in: {cm.output}",
        )

    def test_run_orphan_deregisters_ownership(self):
        """ORPHANED: owner deregistered because session is unrecoverable."""
        import session_owners
        from capabilities.dispatch import DispatchSession
        provider = _MockProvider(
            session_id="s-orphan-dereg",
            status_sequence=[],
        )
        session = DispatchSession(
            "task", "/repo", "p-owner",
            provider=provider, poll_interval=0.001, timeout=0.005,
        )
        _run(session.start())
        # After start, owner should be registered.
        self.assertTrue(session_owners.check("s-orphan-dereg", "p-owner"))
        # After orphaned run, owner should be deregistered.
        _run(session.run())
        self.assertFalse(session_owners.check("s-orphan-dereg", "p-owner"))

    def test_timed_out_when_observed_but_did_not_complete(self):
        """TIMED_OUT: session was seen at least once but ran past deadline."""
        from capabilities.dispatch import DispatchSession, DispatchSessionState
        provider = _MockProvider(
            session_id="s-timeout",
            status_sequence=[_Session("s-timeout", "running")] * 100,
        )
        session = DispatchSession(
            "task", "/repo", "p1",
            provider=provider, poll_interval=0.001, timeout=0.005,
        )
        _run(session.start())
        result = _run(session.run())
        self.assertEqual(result["status"], "error")
        self.assertIn("timeout", result["message"].lower())
        self.assertNotEqual(result["message"], "dispatch timed out (orphaned)")
        self.assertEqual(session.state, DispatchSessionState.TIMED_OUT)

    def test_mark_orphaned_returns_error_artifact(self):
        """mark_orphaned() helper returns the correct artifact directly."""
        from capabilities.dispatch import DispatchSession, DispatchSessionState
        provider = _MockProvider(
            session_id="s-orphan-direct",
            status_sequence=[_Session("s-orphan-direct", "running")],
        )
        session = DispatchSession(
            "long task", "/repo", "p1",
            provider=provider, poll_interval=0.001, timeout=5.0,
        )
        _run(session.start())
        result = session.mark_orphaned()
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["message"], "dispatch timed out (orphaned)")
        self.assertEqual(session.state, DispatchSessionState.ORPHANED)

    def test_completed_and_error_sessions_retain_ownership_after_run(self):
        """Ownership is retained for completed/error to allow manage_agents cleanup."""
        import session_owners
        from capabilities.dispatch import DispatchSession

        for status, label in [("stopped", "s-completed"), ("error", "s-error")]:
            with self.subTest(status=status):
                session_owners.clear()
                provider = _MockProvider(
                    session_id=label,
                    status_sequence=[_Session(label, status)],
                )
                session = DispatchSession(
                    "task", "/repo", "p-owner",
                    provider=provider, poll_interval=0.001, timeout=5.0,
                )
                _run(session.start())
                _run(session.run())
                self.assertTrue(
                    session_owners.check(label, "p-owner"),
                    msg=f"Ownership should be retained after {status}",
                )


class TestDispatchSessionPollFetchesOnce(unittest.TestCase):
    """Test that poll() fetches output exactly once per call."""

    def setUp(self):
        import session_owners
        session_owners.clear()

    def tearDown(self):
        import session_owners
        session_owners.clear()

    def test_poll_fetches_logs_exactly_once_per_call(self):
        from capabilities.dispatch import DispatchSession
        provider = _MockProvider(
            session_id="s1",
            status_sequence=[
                _Session("s1", "running"),
                _Session("s1", "stopped"),
            ],
        )
        session = DispatchSession(
            "task", "/repo", "p1",
            provider=provider, poll_interval=0.001, timeout=5.0,
        )
        _run(session.start())

        # First poll tick — session still running, one get_logs call expected.
        _run(session.poll())
        self.assertEqual(len(provider.logs_calls), 1, "First poll should fetch logs exactly once")

        # Second poll tick — session stopped, one more get_logs call expected.
        _run(session.poll())
        self.assertEqual(len(provider.logs_calls), 2, "Second poll should fetch logs exactly once more")

    def test_poll_does_not_fetch_logs_when_session_not_visible(self):
        """When session is None (not yet in supervisor), no get_logs call is made."""
        from capabilities.dispatch import DispatchSession
        provider = _MockProvider(
            session_id="s1",
            status_sequence=[None, _Session("s1", "stopped")],
        )
        session = DispatchSession(
            "task", "/repo", "p1",
            provider=provider, poll_interval=0.001, timeout=5.0,
        )
        _run(session.start())

        # First poll — session not visible, no logs fetch.
        _run(session.poll())
        self.assertEqual(len(provider.logs_calls), 0, "No logs should be fetched when session is not visible")

        # Second poll — session visible and terminal, one logs fetch.
        _run(session.poll())
        self.assertEqual(len(provider.logs_calls), 1, "Logs should be fetched once when session becomes visible")


class TestDispatchSessionOwnerRegistration(unittest.TestCase):
    """Test that owner registration/deregistration is correctly bracketed."""

    def setUp(self):
        import session_owners
        session_owners.clear()

    def tearDown(self):
        import session_owners
        session_owners.clear()

    def test_owner_registered_after_start(self):
        import session_owners
        from capabilities.dispatch import DispatchSession
        provider = _MockProvider(
            session_id="s-reg",
            status_sequence=[_Session("s-reg", "running")],
        )
        session = DispatchSession(
            "task", "/repo", "p-reg",
            provider=provider, poll_interval=0.001, timeout=5.0,
        )
        # Before start — not registered.
        self.assertFalse(session_owners.check("s-reg", "p-reg"))
        _run(session.start())
        # After start — registered.
        self.assertTrue(session_owners.check("s-reg", "p-reg"))

    def test_owner_not_registered_before_start(self):
        import session_owners
        from capabilities.dispatch import DispatchSession
        provider = _MockProvider(session_id="s-noreg", status_sequence=[])
        session = DispatchSession(
            "task", "/repo", "p-noreg",
            provider=provider, poll_interval=0.001, timeout=5.0,
        )
        self.assertFalse(session_owners.check("s-noreg", "p-noreg"))

    def test_owner_retained_after_completed_run(self):
        """Ownership stays registered after run() completes (issue #55)."""
        import session_owners
        from capabilities.dispatch import DispatchSession
        provider = _MockProvider(
            session_id="s-retain",
            status_sequence=[_Session("s-retain", "stopped")],
        )
        session = DispatchSession(
            "task", "/repo", "p-retain",
            provider=provider, poll_interval=0.001, timeout=5.0,
        )
        _run(session.start())
        _run(session.run())
        self.assertTrue(session_owners.check("s-retain", "p-retain"))

    def test_owner_retained_after_needs_input(self):
        """Ownership stays registered after needs-input (issue #55)."""
        import session_owners
        from capabilities.dispatch import DispatchSession
        provider = _MockProvider(
            session_id="s-ni",
            status_sequence=[_Session("s-ni", "running", needs_input=True)],
        )
        session = DispatchSession(
            "task", "/repo", "p-ni",
            provider=provider, poll_interval=0.001, timeout=5.0,
        )
        _run(session.start())
        _run(session.run())
        self.assertTrue(session_owners.check("s-ni", "p-ni"))

    def test_owner_deregistered_after_orphan(self):
        """Ownership is removed when run() reaches the ORPHANED state."""
        import session_owners
        from capabilities.dispatch import DispatchSession
        # Never-visible session → ORPHANED via run().
        provider = _MockProvider(
            session_id="s-orphan",
            status_sequence=[],
        )
        session = DispatchSession(
            "task", "/repo", "p-orphan",
            provider=provider, poll_interval=0.001, timeout=0.005,
        )
        _run(session.start())
        self.assertTrue(session_owners.check("s-orphan", "p-orphan"))
        _run(session.run())
        self.assertFalse(session_owners.check("s-orphan", "p-orphan"))


if __name__ == "__main__":
    unittest.main()
