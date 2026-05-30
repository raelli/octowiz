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


if __name__ == "__main__":
    unittest.main()
