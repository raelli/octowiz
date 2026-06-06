"""Tests for octowiz.manage_agents capability."""
import asyncio
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["OCTOWIZ_INBOUND_SECRET"] = "test-secret"

_SECRET = "test-secret"

import unittest

# path_guard.validate_cwd checks OCTOWIZ_ALLOWED_ROOTS at call time.
# These tests exercise manage_agents logic; path-guard logic is covered in
# test_path_guard.py and in TestManageAgentsCwdValidation (which pops this
# env var in its own setUp, so the module default does not interfere).
_PREV_ALLOWED_ROOTS = None


def setUpModule():
    global _PREV_ALLOWED_ROOTS
    _PREV_ALLOWED_ROOTS = os.environ.get("OCTOWIZ_ALLOWED_ROOTS")
    os.environ["OCTOWIZ_ALLOWED_ROOTS"] = "/projects:/repo"


def tearDownModule():
    if _PREV_ALLOWED_ROOTS is None:
        os.environ.pop("OCTOWIZ_ALLOWED_ROOTS", None)
    else:
        os.environ["OCTOWIZ_ALLOWED_ROOTS"] = _PREV_ALLOWED_ROOTS


def _run(coro):
    return asyncio.run(coro)


class FakeAdapter:
    """Injected ClaudeCliAdapter for capability tests. Returns typed results directly."""

    def __init__(self, list_result=None, control_result=""):
        self._list = list_result  # list[SessionInfo] | CliError | None (→ [])
        self._control = control_result  # str | CliError
        self.list_calls: list = []  # records cwd passed to list_sessions
        self.control_calls: list = []  # records (op, session_id) tuples

    def list_sessions(self, cwd=None):
        self.list_calls.append(cwd)
        return [] if self._list is None else self._list

    def control(self, op: str, session_id: str):
        self.control_calls.append((op, session_id))
        return self._control


def _session_info(session_id="s1", name="feat/auth-refactor", status="idle",
                  cwd="/repo", pid=1234, started_at=1780116355048):
    from capabilities.cli_adapter import SessionInfo
    return SessionInfo(session_id=session_id, name=name, status=status,
                       cwd=cwd, pid=pid, started_at=started_at)


class TestManageAgentsList(unittest.TestCase):

    def test_list_returns_normalised_session_array(self):
        from capabilities.manage_agents import handle_manage_agents
        adapter = FakeAdapter(list_result=[_session_info()])
        result = _run(handle_manage_agents({"operation": "list"}, adapter=adapter))
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
        adapter = FakeAdapter()
        result = _run(handle_manage_agents({"operation": "list", "cwd": "/projects/foo"}, adapter=adapter))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["sessions"], [])

    def test_list_supervisor_unavailable_returns_warning(self):
        from capabilities.manage_agents import handle_manage_agents
        from capabilities.cli_adapter import CliError
        adapter = FakeAdapter(list_result=CliError(kind="nonzero_exit", message="supervisor not running"))
        result = _run(handle_manage_agents({"operation": "list"}, adapter=adapter))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["sessions"], [])
        self.assertEqual(result.get("warning"), "supervisor_unavailable")

    def test_list_empty_returns_ok(self):
        from capabilities.manage_agents import handle_manage_agents
        adapter = FakeAdapter(list_result=[])
        result = _run(handle_manage_agents({"operation": "list"}, adapter=adapter))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["sessions"], [])

    def test_list_adapter_error_returns_supervisor_warning(self):
        from capabilities.manage_agents import handle_manage_agents
        from capabilities.cli_adapter import CliError
        adapter = FakeAdapter(list_result=CliError(kind="timeout", message="timed out"))
        result = _run(handle_manage_agents({"operation": "list"}, adapter=adapter))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result.get("warning"), "supervisor_unavailable")


class TestManageAgentsCwdValidation(unittest.TestCase):

    def setUp(self):
        os.environ.pop("OCTOWIZ_ALLOWED_ROOTS", None)

    def tearDown(self):
        os.environ.pop("OCTOWIZ_ALLOWED_ROOTS", None)

    def test_relative_cwd_returns_error_without_calling_adapter(self):
        from capabilities.manage_agents import handle_manage_agents
        adapter = FakeAdapter()
        result = _run(handle_manage_agents({"operation": "list", "cwd": "relative/path"}, adapter=adapter))
        self.assertEqual(result["status"], "error")
        self.assertIn("absolute", result["message"])
        self.assertEqual(adapter.list_calls, [])

    def test_absolute_cwd_is_accepted_and_forwarded(self):
        from capabilities.manage_agents import handle_manage_agents
        adapter = FakeAdapter()
        with __import__("unittest.mock", fromlist=["patch"]).patch.dict(
            os.environ, {"OCTOWIZ_ALLOWED_ROOTS": "/projects"}
        ):
            result = _run(handle_manage_agents({"operation": "list", "cwd": "/projects/foo"}, adapter=adapter))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(adapter.list_calls), 1)
        self.assertIn("/projects/foo", adapter.list_calls[0])

    def test_cwd_canonicalized_before_passing_to_adapter(self):
        from capabilities.manage_agents import handle_manage_agents
        adapter = FakeAdapter()
        with __import__("unittest.mock", fromlist=["patch"]).patch.dict(
            os.environ, {"OCTOWIZ_ALLOWED_ROOTS": "/projects"}
        ):
            _run(handle_manage_agents({"operation": "list", "cwd": "/projects/../projects/foo"}, adapter=adapter))
        self.assertEqual(len(adapter.list_calls), 1)
        self.assertEqual(adapter.list_calls[0], "/projects/foo")

    def test_allowed_roots_blocks_outside_path(self):
        from capabilities.manage_agents import handle_manage_agents
        adapter = FakeAdapter()
        with __import__("unittest.mock", fromlist=["patch"]).patch.dict(
            os.environ, {"OCTOWIZ_ALLOWED_ROOTS": "/allowed"}
        ):
            result = _run(handle_manage_agents({"operation": "list", "cwd": "/other/path"}, adapter=adapter))
        self.assertEqual(result["status"], "error")
        self.assertIn("allowed root", result["message"])
        self.assertEqual(adapter.list_calls, [])

    def test_allowed_roots_permits_matching_path(self):
        from capabilities.manage_agents import handle_manage_agents
        adapter = FakeAdapter()
        with __import__("unittest.mock", fromlist=["patch"]).patch.dict(
            os.environ, {"OCTOWIZ_ALLOWED_ROOTS": "/allowed"}
        ):
            result = _run(handle_manage_agents({"operation": "list", "cwd": "/allowed/project"}, adapter=adapter))
        self.assertEqual(result["status"], "ok")

    def test_list_without_cwd_always_allowed(self):
        from capabilities.manage_agents import handle_manage_agents
        adapter = FakeAdapter()
        result = _run(handle_manage_agents({"operation": "list"}, adapter=adapter))
        self.assertEqual(result["status"], "ok")

    def test_symlink_traversal_blocked_by_allowlist(self):
        from capabilities.manage_agents import handle_manage_agents
        adapter = FakeAdapter()
        with __import__("unittest.mock", fromlist=["patch"]).patch.dict(
            os.environ, {"OCTOWIZ_ALLOWED_ROOTS": "/projects"}
        ):
            result = _run(handle_manage_agents({"operation": "list", "cwd": "/tmp"}, adapter=adapter))
        self.assertEqual(result["status"], "error")
        self.assertEqual(adapter.list_calls, [])


class TestManageAgentsControlOps(unittest.TestCase):

    def setUp(self):
        import session_owners
        session_owners.clear()
        # Pre-register "s1" with the empty principal that control-op tests use
        # (events without _principal default to "").
        session_owners.register("s1", "")

    def test_logs_returns_output(self):
        from capabilities.manage_agents import handle_manage_agents
        adapter = FakeAdapter(control_result="log line 1\nlog line 2")
        result = _run(handle_manage_agents({"operation": "logs", "sessionId": "s1"}, adapter=adapter))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["output"], "log line 1\nlog line 2")

    def test_stop_returns_ok(self):
        from capabilities.manage_agents import handle_manage_agents
        adapter = FakeAdapter(control_result="session stopped")
        result = _run(handle_manage_agents({"operation": "stop", "sessionId": "s1"}, adapter=adapter))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["output"], "session stopped")

    def test_rm_returns_ok(self):
        from capabilities.manage_agents import handle_manage_agents
        adapter = FakeAdapter(control_result="")
        result = _run(handle_manage_agents({"operation": "rm", "sessionId": "s1"}, adapter=adapter))
        self.assertEqual(result["status"], "ok")

    def test_respawn_returns_ok(self):
        from capabilities.manage_agents import handle_manage_agents
        adapter = FakeAdapter(control_result="session respawned")
        result = _run(handle_manage_agents({"operation": "respawn", "sessionId": "s1"}, adapter=adapter))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["output"], "session respawned")

    def test_control_adapter_error_returns_error_message(self):
        from capabilities.manage_agents import handle_manage_agents
        from capabilities.cli_adapter import CliError
        adapter = FakeAdapter(control_result=CliError(kind="nonzero_exit", message="permission denied"))
        result = _run(handle_manage_agents({"operation": "stop", "sessionId": "s1"}, adapter=adapter))
        self.assertEqual(result["status"], "error")
        self.assertIn("permission denied", result["message"])

    def test_control_adapter_timeout_returns_error(self):
        from capabilities.manage_agents import handle_manage_agents
        from capabilities.cli_adapter import CliError
        adapter = FakeAdapter(control_result=CliError(kind="timeout", message="operation timed out"))
        result = _run(handle_manage_agents({"operation": "rm", "sessionId": "s1"}, adapter=adapter))
        self.assertEqual(result["status"], "error")
        self.assertTrue(len(result["message"]) > 0)

    def test_control_invalid_session_id_returns_error_without_calling_adapter(self):
        from capabilities.manage_agents import handle_manage_agents
        adapter = FakeAdapter()
        result = _run(handle_manage_agents({"operation": "stop", "sessionId": "bad id!"}, adapter=adapter))
        self.assertEqual(result["status"], "error")
        self.assertIn("sessionId", result["message"])
        self.assertEqual(adapter.control_calls, [])

    def test_unregistered_session_denied_by_ownership_check(self):
        from capabilities.manage_agents import handle_manage_agents
        adapter = FakeAdapter(control_result="stopped")
        # "never-registered" is not in session_owners — must be denied fail-closed
        result = _run(handle_manage_agents(
            {"operation": "stop", "sessionId": "never-registered", "_principal": "any-principal"},
            adapter=adapter,
        ))
        self.assertEqual(result["status"], "error")
        self.assertIn("not owned", result["message"])
        self.assertEqual(adapter.control_calls, [])

    def test_registered_session_wrong_principal_returns_error(self):
        import session_owners
        from capabilities.manage_agents import handle_manage_agents
        session_owners.register("s1", "owner-principal")
        adapter = FakeAdapter(control_result="stopped")
        result = _run(handle_manage_agents(
            {"operation": "stop", "sessionId": "s1", "_principal": "other-principal"},
            adapter=adapter,
        ))
        self.assertEqual(result["status"], "error")
        self.assertIn("not owned", result["message"])
        self.assertEqual(adapter.control_calls, [])


class TestManageAgentsUnknownOp(unittest.TestCase):

    def test_unknown_operation_returns_error_with_op_name(self):
        from capabilities.manage_agents import handle_manage_agents
        adapter = FakeAdapter()
        result = _run(handle_manage_agents({"operation": "reboot"}, adapter=adapter))
        self.assertEqual(result["status"], "error")
        self.assertIn("unknown operation", result["message"])
        self.assertIn("reboot", result["message"])

    def test_missing_operation_returns_error(self):
        from capabilities.manage_agents import handle_manage_agents
        adapter = FakeAdapter()
        result = _run(handle_manage_agents({}, adapter=adapter))
        self.assertEqual(result["status"], "error")
        self.assertIn("unknown operation", result["message"])


class TestManageAgentsDispatchIntegration(unittest.TestCase):
    """Smoke test: verify dispatch routes octowiz.manage_agents to the handler."""

    def setUp(self):
        os.environ["OCTOWIZ_INBOUND_SECRET"] = _SECRET

    def tearDown(self):
        os.environ.pop("OCTOWIZ_INBOUND_SECRET", None)

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
        resp = client.post("/a2a/octowiz", json=body, headers={"x-octowiz-secret": _SECRET})
        self.assertEqual(resp.status_code, 200)
        artifact = json.loads(resp.json()["result"]["artifacts"][0]["parts"][0]["text"])
        self.assertNotEqual(artifact.get("status"), "not_implemented")


if __name__ == "__main__":
    unittest.main()
