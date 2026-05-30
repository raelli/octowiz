"""Tests for octowiz.dispatch capability."""
import asyncio
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["OCTOWIZ_INBOUND_SECRET"] = "test-secret"

_SECRET = "test-secret"

import unittest


class FakeRunner:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "", raises=None):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.raises = raises
        self.calls: list = []

    def __call__(self, args: list) -> tuple:
        self.calls.append(list(args))
        if self.raises is not None:
            raise self.raises
        return self.returncode, self.stdout, self.stderr


PLAIN_OUTPUT = "backgrounded · b188cbb0 (idle — send a prompt to start)"
ANSI_OUTPUT = "backgrounded · \x1b[36mb188cbb0\x1b[39m (idle — send a prompt to start)"
MIDDLE_DOT_OUTPUT = "backgrounded • b188cbb0 (idle — send a prompt to start)"


def _run(coro):
    return asyncio.run(coro)


class TestDispatchStart(unittest.TestCase):

    def test_start_returns_session_id_from_plain_output(self):
        from capabilities.dispatch import handle_dispatch
        runner = FakeRunner(stdout=PLAIN_OUTPUT)
        result = _run(handle_dispatch({"operation": "start", "task": "fix the bug", "cwd": "/repo"}, runner=runner))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["sessionId"], "b188cbb0")

    def test_start_strips_ansi_codes_before_parsing_session_id(self):
        from capabilities.dispatch import handle_dispatch
        runner = FakeRunner(stdout=ANSI_OUTPUT)
        result = _run(handle_dispatch({"operation": "start", "task": "fix the bug", "cwd": "/repo"}, runner=runner))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["sessionId"], "b188cbb0")

    def test_start_accepts_middle_dot_separator(self):
        from capabilities.dispatch import handle_dispatch
        runner = FakeRunner(stdout=MIDDLE_DOT_OUTPUT)
        result = _run(handle_dispatch({"operation": "start", "task": "fix the bug", "cwd": "/repo"}, runner=runner))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["sessionId"], "b188cbb0")

    def test_start_with_optional_name_returns_ok(self):
        from capabilities.dispatch import handle_dispatch
        runner = FakeRunner(stdout=PLAIN_OUTPUT)
        result = _run(handle_dispatch(
            {"operation": "start", "task": "fix the bug", "cwd": "/repo", "name": "feat/fix"},
            runner=runner,
        ))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["sessionId"], "b188cbb0")


class TestDispatchValidation(unittest.TestCase):

    def test_empty_task_returns_error_without_touching_runner(self):
        from capabilities.dispatch import handle_dispatch
        runner = FakeRunner()
        result = _run(handle_dispatch({"operation": "start", "task": "", "cwd": "/repo"}, runner=runner))
        self.assertEqual(result["status"], "error")
        self.assertIn("task", result["message"])
        self.assertEqual(runner.calls, [])

    def test_missing_task_returns_error_without_touching_runner(self):
        from capabilities.dispatch import handle_dispatch
        runner = FakeRunner()
        result = _run(handle_dispatch({"operation": "start", "cwd": "/repo"}, runner=runner))
        self.assertEqual(result["status"], "error")
        self.assertIn("task", result["message"])
        self.assertEqual(runner.calls, [])

    def test_empty_cwd_returns_error_without_touching_runner(self):
        from capabilities.dispatch import handle_dispatch
        runner = FakeRunner()
        result = _run(handle_dispatch({"operation": "start", "task": "fix it", "cwd": ""}, runner=runner))
        self.assertEqual(result["status"], "error")
        self.assertIn("cwd", result["message"])
        self.assertEqual(runner.calls, [])

    def test_missing_cwd_returns_error_without_touching_runner(self):
        from capabilities.dispatch import handle_dispatch
        runner = FakeRunner()
        result = _run(handle_dispatch({"operation": "start", "task": "fix it"}, runner=runner))
        self.assertEqual(result["status"], "error")
        self.assertIn("cwd", result["message"])
        self.assertEqual(runner.calls, [])


class TestDispatchFailures(unittest.TestCase):

    def test_cli_nonzero_exit_returns_error_with_stderr(self):
        from capabilities.dispatch import handle_dispatch
        runner = FakeRunner(returncode=1, stderr="permission denied")
        result = _run(handle_dispatch({"operation": "start", "task": "fix it", "cwd": "/repo"}, runner=runner))
        self.assertEqual(result["status"], "error")
        self.assertIn("permission denied", result["message"])

    def test_output_not_matching_pattern_returns_parse_failure(self):
        from capabilities.dispatch import handle_dispatch
        runner = FakeRunner(stdout="some unexpected output with no session info")
        result = _run(handle_dispatch({"operation": "start", "task": "fix it", "cwd": "/repo"}, runner=runner))
        self.assertEqual(result["status"], "error")
        self.assertIn("could not parse session id", result["message"])

    def test_runner_exception_returns_error_not_exception(self):
        import subprocess
        from capabilities.dispatch import handle_dispatch
        runner = FakeRunner(raises=subprocess.TimeoutExpired(cmd=["claude"], timeout=10))
        result = _run(handle_dispatch({"operation": "start", "task": "fix it", "cwd": "/repo"}, runner=runner))
        self.assertEqual(result["status"], "error")
        self.assertTrue(len(result["message"]) > 0)


class TestDispatchUnknownOp(unittest.TestCase):

    def test_unknown_operation_returns_error_with_op_name(self):
        from capabilities.dispatch import handle_dispatch
        runner = FakeRunner()
        result = _run(handle_dispatch({"operation": "attach"}, runner=runner))
        self.assertEqual(result["status"], "error")
        self.assertIn("unknown operation", result["message"])
        self.assertIn("attach", result["message"])

    def test_missing_operation_returns_error(self):
        from capabilities.dispatch import handle_dispatch
        runner = FakeRunner()
        result = _run(handle_dispatch({}, runner=runner))
        self.assertEqual(result["status"], "error")
        self.assertIn("unknown operation", result["message"])


class FakeSession:
    """Minimal AgentSession stand-in for provider mock."""
    def __init__(self, status="running", needs_input=False):
        self.id = "bg-test"
        self.status = status
        self.needs_input = needs_input
        self.ready_for_review = (status == "stopped" and not needs_input)


class FakeProvider:
    """Configurable mock for ClaudeAgentViewProvider used in run tests."""

    def __init__(self, states, logs="session output"):
        self._states = iter(states)
        self._logs = logs
        self.log_calls: list = []

    def get_status(self, run_id):
        try:
            return next(self._states)
        except StopIteration:
            return None

    def get_logs(self, run_id):
        self.log_calls.append(run_id)
        return self._logs


async def _sleep_noop(_delay):
    """Instant sleep for tests."""


class TestDispatchRun(unittest.TestCase):
    """Tests for operation='run' (fire-and-observe)."""

    def test_run_resolves_completed_when_session_stops(self):
        from capabilities.dispatch import handle_dispatch
        runner = FakeRunner(stdout=PLAIN_OUTPUT)
        provider = FakeProvider(
            states=[FakeSession("running"), FakeSession("stopped")],
            logs="done",
        )
        result = _run(handle_dispatch(
            {"operation": "run", "task": "fix bug", "cwd": "/repo"},
            runner=runner,
            provider=provider,
            _sleep_fn=_sleep_noop,
        ))
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["sessionId"], "b188cbb0")
        self.assertEqual(result["output"], "done")

    def test_run_resolves_needs_input_when_session_waits(self):
        from capabilities.dispatch import handle_dispatch
        runner = FakeRunner(stdout=PLAIN_OUTPUT)
        provider = FakeProvider(
            states=[FakeSession("running"), FakeSession("waiting", needs_input=True)],
        )
        result = _run(handle_dispatch(
            {"operation": "run", "task": "fix bug", "cwd": "/repo"},
            runner=runner,
            provider=provider,
            _sleep_fn=_sleep_noop,
        ))
        self.assertEqual(result["status"], "needs-input")

    def test_run_resolves_failed_when_session_errors(self):
        from capabilities.dispatch import handle_dispatch
        runner = FakeRunner(stdout=PLAIN_OUTPUT)
        provider = FakeProvider(states=[FakeSession("error")])
        result = _run(handle_dispatch(
            {"operation": "run", "task": "fix bug", "cwd": "/repo"},
            runner=runner,
            provider=provider,
            _sleep_fn=_sleep_noop,
        ))
        self.assertEqual(result["status"], "failed")

    def test_run_returns_error_when_start_fails(self):
        from capabilities.dispatch import handle_dispatch
        runner = FakeRunner(returncode=1, stderr="permission denied")
        provider = FakeProvider(states=[])
        result = _run(handle_dispatch(
            {"operation": "run", "task": "fix bug", "cwd": "/repo"},
            runner=runner,
            provider=provider,
        ))
        self.assertEqual(result["status"], "error")
        self.assertIn("permission denied", result["message"])

    def test_run_times_out_and_returns_error(self):
        from capabilities.dispatch import handle_dispatch

        class NeverDone:
            def get_status(self, _): return FakeSession("running")
            def get_logs(self, _): return ""

        result = _run(handle_dispatch(
            {
                "operation": "run",
                "task": "fix bug",
                "cwd": "/repo",
                "_poll_interval": 1.0,
                "_timeout": 0.0,
            },
            runner=FakeRunner(stdout=PLAIN_OUTPUT),
            provider=NeverDone(),
            _sleep_fn=_sleep_noop,
        ))
        self.assertEqual(result["status"], "error")
        self.assertIn("timed out", result["message"])

    def test_run_missing_task_returns_error_immediately(self):
        from capabilities.dispatch import handle_dispatch
        runner = FakeRunner()
        provider = FakeProvider(states=[])
        result = _run(handle_dispatch(
            {"operation": "run", "cwd": "/repo"},
            runner=runner,
            provider=provider,
        ))
        self.assertEqual(result["status"], "error")
        self.assertIn("task", result["message"])
        self.assertEqual(runner.calls, [])


class TestDispatchIntegration(unittest.TestCase):
    """Smoke test: verify dispatch routes octowiz.dispatch to the handler."""

    def setUp(self):
        os.environ["OCTOWIZ_INBOUND_SECRET"] = _SECRET

    def tearDown(self):
        os.environ.pop("OCTOWIZ_INBOUND_SECRET", None)

    def test_dispatch_is_routed_not_not_implemented(self):
        import importlib
        import dispatch as dispatch_mod
        importlib.reload(dispatch_mod)
        import main as m
        importlib.reload(m)
        from fastapi.testclient import TestClient
        client = TestClient(m.app)
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "params": {"message": {"parts": [{"text": json.dumps({
                "capability": "octowiz.dispatch",
                "operation": "start",
                "task": "",
                "cwd": "/tmp",
            })}]}},
        }
        resp = client.post("/a2a/octowiz", json=body, headers={"x-octowiz-secret": _SECRET})
        self.assertEqual(resp.status_code, 200)
        artifact = json.loads(resp.json()["result"]["artifacts"][0]["parts"][0]["text"])
        self.assertNotEqual(artifact.get("status"), "not_implemented")


if __name__ == "__main__":
    unittest.main()
