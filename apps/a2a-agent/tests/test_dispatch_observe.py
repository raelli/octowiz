"""Tests for octowiz.dispatch operation:observe (fire-and-observe)."""
import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.pop("OCTOWIZ_INBOUND_SECRET", None)

import unittest
from unittest.mock import MagicMock


def _run(coro):
    return asyncio.run(coro)


def _session(status="running", needs_input=False):
    s = MagicMock()
    s.status = status
    s.needs_input = needs_input
    return s


class FakeRunner:
    """Injected instead of _default_runner. Simulates claude --bg output."""
    def __init__(self, returncode=0, stdout="backgrounded · bg-test-1", stderr="", raises=None):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.raises = raises

    def __call__(self, args):
        if self.raises:
            raise self.raises
        return self.returncode, self.stdout, self.stderr


class FakeProvider:
    """Injected ClaudeAgentViewProvider for observe polling tests."""
    def __init__(self, status_sequence=None, logs="task output"):
        self._seq = iter(status_sequence or [_session("stopped")])
        self.logs = logs

    def get_status(self, run_id):
        try:
            return next(self._seq)
        except StopIteration:
            return _session("stopped")

    def get_logs(self, run_id):
        return self.logs


class TestObserveOperation(unittest.TestCase):

    def _dispatch(self, event, runner=None, provider=None, poll_interval=0, max_wait=5):
        from capabilities.dispatch import handle_dispatch
        return _run(handle_dispatch(
            event, runner=runner or FakeRunner(),
            _provider=provider or FakeProvider(),
            _poll_interval=poll_interval,
            _max_wait=max_wait,
        ))

    def test_completed_when_session_stops(self):
        provider = FakeProvider(status_sequence=[_session("stopped")])
        result = self._dispatch(
            {"operation": "observe", "task": "fix the bug", "cwd": "/repo"},
            provider=provider,
        )
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["sessionId"], "bg-test-1")
        self.assertEqual(result["output"], "task output")

    def test_needs_input_when_session_waits(self):
        provider = FakeProvider(status_sequence=[_session("running", needs_input=True)])
        result = self._dispatch(
            {"operation": "observe", "task": "do something", "cwd": "/repo"},
            provider=provider,
        )
        self.assertEqual(result["status"], "needs-input")
        self.assertIn("sessionId", result)

    def test_failed_when_session_errors(self):
        provider = FakeProvider(status_sequence=[_session("error")])
        result = self._dispatch(
            {"operation": "observe", "task": "do something", "cwd": "/repo"},
            provider=provider,
        )
        self.assertEqual(result["status"], "failed")

    def test_timeout_when_max_wait_zero(self):
        # max_wait=0 means the polling loop never runs
        provider = FakeProvider(status_sequence=[_session("running")] * 100)
        result = self._dispatch(
            {"operation": "observe", "task": "slow task", "cwd": "/repo"},
            provider=provider,
            max_wait=0,
        )
        self.assertEqual(result["status"], "timeout")
        self.assertIn("sessionId", result)

    def test_error_when_task_missing(self):
        result = self._dispatch({"operation": "observe", "cwd": "/repo"})
        self.assertEqual(result["status"], "error")
        self.assertIn("task", result["message"])

    def test_error_when_cwd_missing(self):
        result = self._dispatch({"operation": "observe", "task": "do something"})
        self.assertEqual(result["status"], "error")
        self.assertIn("cwd", result["message"])

    def test_error_propagated_when_start_fails(self):
        runner = FakeRunner(returncode=1, stderr="claude not found")
        result = self._dispatch(
            {"operation": "observe", "task": "do something", "cwd": "/repo"},
            runner=runner,
        )
        self.assertEqual(result["status"], "error")

    def test_skips_none_status_and_continues_polling(self):
        provider = FakeProvider(status_sequence=[None, _session("stopped")])
        result = self._dispatch(
            {"operation": "observe", "task": "task", "cwd": "/repo"},
            provider=provider,
        )
        self.assertEqual(result["status"], "completed")
