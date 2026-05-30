"""Tests for octowiz.manage_agents capability."""
import asyncio
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.pop("OCTOWIZ_INBOUND_SECRET", None)

import unittest


class FakeRunner:
    """Injected in place of _default_runner. Records calls for inspection."""

    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "", raises: Exception = None):
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


SESSIONS_JSON = json.dumps([
    {
        "sessionId": "s1",
        "name": "feat/auth-refactor",
        "status": "idle",
        "cwd": "/repo",
        "pid": 1234,
        "startedAt": 1780116355048,
    }
])


def _run(coro):
    return asyncio.run(coro)


class TestManageAgentsList(unittest.TestCase):

    def test_list_returns_normalised_session_array(self):
        from capabilities.manage_agents import handle_manage_agents
        runner = FakeRunner(stdout=SESSIONS_JSON)
        result = _run(handle_manage_agents({"operation": "list"}, runner=runner))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["sessions"]), 1)
        s = result["sessions"][0]
        self.assertEqual(s["sessionId"], "s1")
        self.assertEqual(s["name"], "feat/auth-refactor")
        self.assertEqual(s["status"], "idle")
        self.assertEqual(s["cwd"], "/repo")
        self.assertEqual(s["pid"], 1234)
        self.assertEqual(s["startedAt"], 1780116355048)

    def test_list_with_cwd_passes_through(self):
        from capabilities.manage_agents import handle_manage_agents
        runner = FakeRunner(stdout="[]")
        result = _run(handle_manage_agents({"operation": "list", "cwd": "/projects/foo"}, runner=runner))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["sessions"], [])

    def test_list_supervisor_unavailable_returns_warning(self):
        from capabilities.manage_agents import handle_manage_agents
        runner = FakeRunner(returncode=1, stdout="", stderr="supervisor not running")
        result = _run(handle_manage_agents({"operation": "list"}, runner=runner))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["sessions"], [])
        self.assertEqual(result.get("warning"), "supervisor_unavailable")

    def test_list_empty_array_returns_ok(self):
        from capabilities.manage_agents import handle_manage_agents
        runner = FakeRunner(stdout="[]")
        result = _run(handle_manage_agents({"operation": "list"}, runner=runner))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["sessions"], [])

    def test_list_cli_not_found_returns_warning_not_exception(self):
        from capabilities.manage_agents import handle_manage_agents
        runner = FakeRunner(raises=FileNotFoundError("claude: command not found"))
        result = _run(handle_manage_agents({"operation": "list"}, runner=runner))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["sessions"], [])
        self.assertEqual(result.get("warning"), "supervisor_unavailable")


class TestManageAgentsControlOps(unittest.TestCase):

    def test_logs_returns_output(self):
        from capabilities.manage_agents import handle_manage_agents
        runner = FakeRunner(stdout="log line 1\nlog line 2")
        result = _run(handle_manage_agents({"operation": "logs", "sessionId": "s1"}, runner=runner))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["output"], "log line 1\nlog line 2")

    def test_stop_returns_ok(self):
        from capabilities.manage_agents import handle_manage_agents
        runner = FakeRunner(stdout="session stopped")
        result = _run(handle_manage_agents({"operation": "stop", "sessionId": "s1"}, runner=runner))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["output"], "session stopped")

    def test_rm_returns_ok(self):
        from capabilities.manage_agents import handle_manage_agents
        runner = FakeRunner(stdout="")
        result = _run(handle_manage_agents({"operation": "rm", "sessionId": "s1"}, runner=runner))
        self.assertEqual(result["status"], "ok")

    def test_respawn_returns_ok(self):
        from capabilities.manage_agents import handle_manage_agents
        runner = FakeRunner(stdout="session respawned")
        result = _run(handle_manage_agents({"operation": "respawn", "sessionId": "s1"}, runner=runner))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["output"], "session respawned")

    def test_cli_nonzero_returns_error_with_stderr(self):
        from capabilities.manage_agents import handle_manage_agents
        runner = FakeRunner(returncode=1, stderr="permission denied")
        result = _run(handle_manage_agents({"operation": "stop", "sessionId": "s1"}, runner=runner))
        self.assertEqual(result["status"], "error")
        self.assertIn("permission denied", result["message"])

    def test_cli_nonzero_no_stderr_returns_fallback_message(self):
        from capabilities.manage_agents import handle_manage_agents
        runner = FakeRunner(returncode=1, stdout="", stderr="")
        result = _run(handle_manage_agents({"operation": "rm", "sessionId": "s1"}, runner=runner))
        self.assertEqual(result["status"], "error")
        self.assertTrue(len(result["message"]) > 0)


class TestManageAgentsUnknownOp(unittest.TestCase):

    def test_unknown_operation_returns_error_with_op_name(self):
        from capabilities.manage_agents import handle_manage_agents
        runner = FakeRunner()
        result = _run(handle_manage_agents({"operation": "reboot"}, runner=runner))
        self.assertEqual(result["status"], "error")
        self.assertIn("unknown operation", result["message"])
        self.assertIn("reboot", result["message"])

    def test_missing_operation_returns_error(self):
        from capabilities.manage_agents import handle_manage_agents
        runner = FakeRunner()
        result = _run(handle_manage_agents({}, runner=runner))
        self.assertEqual(result["status"], "error")
        self.assertIn("unknown operation", result["message"])


class TestManageAgentsDispatchIntegration(unittest.TestCase):
    """Smoke test: verify dispatch routes octowiz.manage_agents to the handler."""

    def test_manage_agents_is_routed_not_not_implemented(self):
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
                "capability": "octowiz.manage_agents",
                "operation": "list",
            })}]}},
        }
        resp = client.post("/a2a/octowiz", json=body)
        self.assertEqual(resp.status_code, 200)
        artifact = json.loads(resp.json()["result"]["artifacts"][0]["parts"][0]["text"])
        self.assertNotEqual(artifact.get("status"), "not_implemented")


if __name__ == "__main__":
    unittest.main()
