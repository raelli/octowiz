"""Tests for octowiz.dispatch fire-and-observe capability (operation:observe migrated to provider API)."""
import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.pop("OCTOWIZ_INBOUND_SECRET", None)

import unittest
from unittest.mock import MagicMock

_FAST = {"poll_interval": 0.001, "timeout": 5.0}
_INSTANT_TIMEOUT = {"poll_interval": 0.001, "timeout": 0.005}

_PREV_ALLOWED_ROOTS = None


def setUpModule():
    global _PREV_ALLOWED_ROOTS
    _PREV_ALLOWED_ROOTS = os.environ.get("OCTOWIZ_ALLOWED_ROOTS")
    os.environ["OCTOWIZ_ALLOWED_ROOTS"] = "/repo"


def tearDownModule():
    if _PREV_ALLOWED_ROOTS is None:
        os.environ.pop("OCTOWIZ_ALLOWED_ROOTS", None)
    else:
        os.environ["OCTOWIZ_ALLOWED_ROOTS"] = _PREV_ALLOWED_ROOTS


def _run(coro):
    return asyncio.run(coro)


def _session(status="running", needs_input=False):
    s = MagicMock()
    s.status = status
    s.needs_input = needs_input
    return s


class FakeProvider:
    """Injectable provider for dispatch fire-and-observe tests."""
    def __init__(self, session_id="bg-test-1", status_sequence=None, logs="task output", dispatch_raises=None):
        self._session_id = session_id
        self._seq = iter(status_sequence or [_session("stopped")])
        self.logs = logs
        self._dispatch_raises = dispatch_raises

    def dispatch(self, task, cwd):
        if self._dispatch_raises:
            raise self._dispatch_raises
        return self._session_id

    def get_status(self, session_id):
        try:
            return next(self._seq)
        except StopIteration:
            return _session("stopped")

    def get_logs(self, session_id):
        return self.logs


class TestObserveOperation(unittest.TestCase):

    def _dispatch(self, event, provider=None, **kwargs):
        from capabilities.dispatch import handle_dispatch
        opts = {**_FAST, **kwargs}
        return _run(handle_dispatch(event, provider=provider or FakeProvider(), **opts))

    def test_completed_when_session_stops(self):
        provider = FakeProvider(status_sequence=[_session("stopped")])
        result = self._dispatch({"task": "fix the bug", "cwd": "/repo"}, provider=provider)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["session_id"], "bg-test-1")
        self.assertEqual(result["output"], "task output")

    def test_needs_input_when_session_waits(self):
        provider = FakeProvider(status_sequence=[_session("running", needs_input=True)])
        result = self._dispatch({"task": "do something", "cwd": "/repo"}, provider=provider)
        self.assertEqual(result["status"], "needs-input")
        self.assertIn("session_id", result)

    def test_error_when_session_errors(self):
        provider = FakeProvider(status_sequence=[_session("error")])
        result = self._dispatch({"task": "do something", "cwd": "/repo"}, provider=provider)
        self.assertEqual(result["status"], "error")

    def test_timeout_returns_error_with_message(self):
        provider = FakeProvider(status_sequence=[_session("running")] * 100)
        result = self._dispatch(
            {"task": "slow task", "cwd": "/repo"},
            provider=provider,
            **_INSTANT_TIMEOUT,
        )
        self.assertEqual(result["status"], "error")
        self.assertIn("session_id", result)
        self.assertIn("timeout", result["message"].lower())

    def test_error_when_task_missing(self):
        result = self._dispatch({"cwd": "/repo"})
        self.assertEqual(result["status"], "error")
        self.assertIn("task", result["message"])

    def test_error_when_cwd_missing(self):
        result = self._dispatch({"task": "do something"})
        self.assertEqual(result["status"], "error")
        self.assertIn("cwd", result["message"])

    def test_error_propagated_when_start_fails(self):
        provider = FakeProvider(dispatch_raises=RuntimeError("claude not found"))
        result = self._dispatch({"task": "do something", "cwd": "/repo"}, provider=provider)
        self.assertEqual(result["status"], "error")
        self.assertIn("failed to start session", result["message"])

    def test_skips_none_status_and_continues_polling(self):
        provider = FakeProvider(status_sequence=[None, _session("stopped")])
        result = self._dispatch({"task": "task", "cwd": "/repo"}, provider=provider)
        self.assertEqual(result["status"], "completed")
