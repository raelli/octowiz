"""Tests for WorkflowRunClient — all HTTP calls mocked via httpx.MockTransport."""
import asyncio
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest

import httpx


def _run(coro):
    return asyncio.run(coro)


def _mock_transport(status_code: int, body: dict):
    """Return an httpx.MockTransport that always responds with the given status and JSON body."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=body)

    return httpx.MockTransport(handler)


def _error_transport():
    """Return a transport that always raises a connection error."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    return httpx.MockTransport(handler)


def _make_client(transport) -> "WorkflowRunClient":
    from workflow_run_client import WorkflowRunClient
    client = WorkflowRunClient.__new__(WorkflowRunClient)
    client._client = httpx.AsyncClient(
        base_url="http://litellm",
        headers={"Authorization": "Bearer sk-test"},
        transport=transport,
    )
    return client


_FAKE_RUN = {
    "run_id": "run-abc",
    "session_id": "sess-xyz",
    "workflow_type": "octowiz.dispatch",
    "status": "pending",
}

_FAKE_EVENT = {
    "event_id": "evt-001",
    "run_id": "run-abc",
    "event_type": "step.started",
    "step_name": "dispatch",
    "sequence_number": 0,
}


class TestCreateRun(unittest.TestCase):

    def test_returns_run_dict_on_success(self):
        client = _make_client(_mock_transport(200, _FAKE_RUN))
        result = _run(client.create_run(task="do stuff", cwd="/repo", principal="user"))
        self.assertEqual(result["run_id"], "run-abc")
        self.assertEqual(result["session_id"], "sess-xyz")

    def test_returns_none_on_http_error(self):
        client = _make_client(_mock_transport(500, {"error": "db down"}))
        result = _run(client.create_run(task="do stuff", cwd="/repo", principal="user"))
        self.assertIsNone(result)

    def test_returns_none_on_connection_error(self):
        client = _make_client(_error_transport())
        result = _run(client.create_run(task="do stuff", cwd="/repo", principal="user"))
        self.assertIsNone(result)


class TestTransition(unittest.TestCase):

    def test_sends_correct_payload(self):
        received = {}

        def handler(request: httpx.Request) -> httpx.Response:
            received["path"] = request.url.path
            received["body"] = json.loads(request.content)
            return httpx.Response(200, json=_FAKE_EVENT)

        client = _make_client(httpx.MockTransport(handler))
        _run(client.transition("run-abc", "step.started", "dispatch", data={"claude_session_id": "s1"}))

        self.assertEqual(received["path"], "/v1/workflows/runs/run-abc/events")
        self.assertEqual(received["body"]["event_type"], "step.started")
        self.assertEqual(received["body"]["step_name"], "dispatch")
        self.assertEqual(received["body"]["data"]["claude_session_id"], "s1")

    def test_omits_data_when_none(self):
        received = {}

        def handler(request: httpx.Request) -> httpx.Response:
            received["body"] = json.loads(request.content)
            return httpx.Response(200, json=_FAKE_EVENT)

        client = _make_client(httpx.MockTransport(handler))
        _run(client.transition("run-abc", "hook.waiting", "needs-input"))
        self.assertNotIn("data", received["body"])

    def test_swallows_http_error(self):
        client = _make_client(_mock_transport(500, {}))
        # must not raise
        _run(client.transition("run-abc", "step.started", "dispatch"))

    def test_swallows_connection_error(self):
        client = _make_client(_error_transport())
        _run(client.transition("run-abc", "step.started", "dispatch"))


class TestComplete(unittest.TestCase):

    def test_patches_completed_status_with_output(self):
        received = {}

        def handler(request: httpx.Request) -> httpx.Response:
            received["path"] = request.url.path
            received["body"] = json.loads(request.content)
            return httpx.Response(200, json={**_FAKE_RUN, "status": "completed"})

        client = _make_client(httpx.MockTransport(handler))
        _run(client.complete("run-abc", output={"session_id": "s1", "output": "done"}))

        self.assertIn("/run-abc", received["path"])
        self.assertEqual(received["body"]["status"], "completed")
        self.assertEqual(received["body"]["output"]["session_id"], "s1")

    def test_swallows_error(self):
        client = _make_client(_error_transport())
        _run(client.complete("run-abc", output={}))


class TestFail(unittest.TestCase):

    def test_patches_failed_status(self):
        received = {}

        def handler(request: httpx.Request) -> httpx.Response:
            received["body"] = json.loads(request.content)
            return httpx.Response(200, json={**_FAKE_RUN, "status": "failed"})

        client = _make_client(httpx.MockTransport(handler))
        _run(client.fail("run-abc", output={"session_id": "s1", "output": "boom"}))

        self.assertEqual(received["body"]["status"], "failed")

    def test_swallows_error(self):
        client = _make_client(_error_transport())
        _run(client.fail("run-abc", output={}))


class TestListActiveRuns(unittest.TestCase):

    def test_returns_runs_list(self):
        body = {"runs": [_FAKE_RUN], "count": 1}
        client = _make_client(_mock_transport(200, body))
        runs = _run(client.list_active_runs())
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["run_id"], "run-abc")

    def test_passes_correct_query_params(self):
        received = {}

        def handler(request: httpx.Request) -> httpx.Response:
            received["params"] = dict(request.url.params)
            return httpx.Response(200, json={"runs": [], "count": 0})

        client = _make_client(httpx.MockTransport(handler))
        _run(client.list_active_runs())

        self.assertEqual(received["params"]["workflow_type"], "octowiz.dispatch")
        self.assertEqual(received["params"]["status"], "running,paused")

    def test_returns_empty_list_on_error(self):
        client = _make_client(_error_transport())
        runs = _run(client.list_active_runs())
        self.assertEqual(runs, [])


class TestMakeFromEnv(unittest.TestCase):

    def test_returns_none_when_env_not_set(self):
        import os
        from workflow_run_client import _make_from_env
        saved = os.environ.pop("AELLI_LITELLM_BASE", None), os.environ.pop("AELLI_AUTH_TOKEN", None)
        try:
            self.assertIsNone(_make_from_env())
        finally:
            if saved[0]:
                os.environ["AELLI_LITELLM_BASE"] = saved[0]
            if saved[1]:
                os.environ["AELLI_AUTH_TOKEN"] = saved[1]

    def test_returns_client_when_env_set(self):
        import os
        from workflow_run_client import _make_from_env, WorkflowRunClient
        os.environ["AELLI_LITELLM_BASE"] = "http://litellm"
        os.environ["AELLI_AUTH_TOKEN"] = "sk-test"
        try:
            client = _make_from_env()
            self.assertIsInstance(client, WorkflowRunClient)
            asyncio.run(client.close())
        finally:
            del os.environ["AELLI_LITELLM_BASE"]
            del os.environ["AELLI_AUTH_TOKEN"]


if __name__ == "__main__":
    unittest.main()
