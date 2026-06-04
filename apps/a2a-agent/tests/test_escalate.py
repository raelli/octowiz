"""Tests for octowiz.escalate_to_aelli capability."""
import asyncio
import json
import os
import sys
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx


def _run(coro):
    return asyncio.run(coro)


def _make_mock_response(status_code=200, json_data=None, raise_on_status=None):
    """Build a mock httpx.Response."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    if raise_on_status is not None:
        mock_resp.raise_for_status.side_effect = raise_on_status
    else:
        mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = json_data if json_data is not None else {}
    return mock_resp


class TestEscalateValidation(unittest.TestCase):

    def test_error_when_question_missing(self):
        from capabilities.escalate import handle_escalate
        result = _run(handle_escalate({}))
        self.assertEqual(result["status"], "error")
        self.assertIn("question", result["message"])

    def test_error_when_question_empty(self):
        from capabilities.escalate import handle_escalate
        result = _run(handle_escalate({"question": ""}))
        self.assertEqual(result["status"], "error")
        self.assertIn("question", result["message"])


class TestEscalateSuccess(unittest.TestCase):

    def test_successful_escalation(self):
        from capabilities.escalate import handle_escalate
        mock_resp = _make_mock_response(status_code=200, json_data={"result": "ok"})
        with patch("httpx.Client.post", return_value=mock_resp):
            result = _run(handle_escalate({"question": "Should we pivot to a new architecture?"}))
        self.assertEqual(result["status"], "escalated")
        self.assertEqual(result["delivery"], "sent")
        self.assertEqual(result["aelli_response"], {"result": "ok"})


class TestEscalateFailOpen(unittest.TestCase):

    def test_failopen_on_connection_error(self):
        from capabilities.escalate import handle_escalate
        tmp = tempfile.mkdtemp()
        try:
            with patch("pathlib.Path.home", staticmethod(lambda: Path(tmp))):
                with patch("httpx.Client.post", side_effect=httpx.ConnectError("connection refused")):
                    result = _run(handle_escalate({"question": "Is the deployment safe?"}))
        finally:
            import shutil; shutil.rmtree(tmp, ignore_errors=True)
        self.assertEqual(result["status"], "escalated")
        self.assertEqual(result["delivery"], "queued")
        self.assertIn("warning", result)

    def test_failopen_on_http_500(self):
        from capabilities.escalate import handle_escalate
        tmp = tempfile.mkdtemp()
        try:
            mock_resp = _make_mock_response(
                status_code=500,
                raise_on_status=httpx.HTTPStatusError(
                    "500 Server Error",
                    request=MagicMock(),
                    response=MagicMock(status_code=500),
                ),
            )
            with patch("pathlib.Path.home", staticmethod(lambda: Path(tmp))):
                with patch("httpx.Client.post", return_value=mock_resp):
                    result = _run(handle_escalate({"question": "Is the deployment safe?"}))
        finally:
            import shutil; shutil.rmtree(tmp, ignore_errors=True)
        self.assertEqual(result["status"], "escalated")
        self.assertEqual(result["delivery"], "queued")

    def test_queued_escalation_persisted_to_disk(self):
        """Failed escalations must be written to escalation-queue.jsonl before returning queued."""
        from capabilities.escalate import handle_escalate
        tmp = tempfile.mkdtemp()
        try:
            with patch("pathlib.Path.home", staticmethod(lambda: Path(tmp))):
                with patch("httpx.Client.post", side_effect=httpx.ConnectError("timeout")):
                    result = _run(handle_escalate({"question": "Should we scale the DB?", "sessionId": "sess-1"}))
            queue_path = Path(tmp) / ".cache" / "octowiz" / "escalation-queue.jsonl"
            self.assertTrue(queue_path.exists(), "escalation-queue.jsonl must be created on failure")
            record = json.loads(queue_path.read_text().strip())
        finally:
            import shutil; shutil.rmtree(tmp, ignore_errors=True)
        self.assertEqual(result["delivery"], "queued")
        self.assertEqual(record["question"], "Should we scale the DB?")
        self.assertEqual(record["sessionId"], "sess-1")
        self.assertIn("ts", record)
        self.assertIn("reason", record)

    def test_queue_file_accumulates_multiple_entries(self):
        """Each failed escalation appends a new line to the queue file."""
        from capabilities.escalate import handle_escalate
        tmp = tempfile.mkdtemp()
        try:
            with patch("pathlib.Path.home", staticmethod(lambda: Path(tmp))):
                with patch("httpx.Client.post", side_effect=httpx.ConnectError("down")):
                    _run(handle_escalate({"question": "Q1"}))
                    _run(handle_escalate({"question": "Q2"}))
            queue_path = Path(tmp) / ".cache" / "octowiz" / "escalation-queue.jsonl"
            lines = [l for l in queue_path.read_text().splitlines() if l.strip()]
        finally:
            import shutil; shutil.rmtree(tmp, ignore_errors=True)
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[0])["question"], "Q1")
        self.assertEqual(json.loads(lines[1])["question"], "Q2")


class TestEscalateAuthHeader(unittest.TestCase):

    def setUp(self):
        os.environ.pop("AELLI_AUTH_TOKEN", None)
        os.environ.pop("AELLI_LITELLM_BASE", None)

    def tearDown(self):
        os.environ.pop("AELLI_AUTH_TOKEN", None)
        os.environ.pop("AELLI_LITELLM_BASE", None)

    def test_direct_aelli_uses_x_aelli_secret_header(self):
        """Without AELLI_LITELLM_BASE, auth token goes in x-aelli-secret (direct AELLI)."""
        from capabilities.escalate import handle_escalate
        mock_resp = _make_mock_response(status_code=200, json_data={"result": "ok"})
        with patch("httpx.Client.post", return_value=mock_resp) as mock_post:
            with patch.dict(os.environ, {"AELLI_AUTH_TOKEN": "direct-secret"}, clear=False):
                os.environ.pop("AELLI_LITELLM_BASE", None)
                _run(handle_escalate({"question": "Prioritize next quarter goals?"}))
        call_headers = mock_post.call_args.kwargs.get("headers", {})
        self.assertIn("x-aelli-secret", call_headers)
        self.assertEqual(call_headers["x-aelli-secret"], "direct-secret")
        self.assertNotIn("Authorization", call_headers)

    def test_gateway_route_uses_authorization_bearer(self):
        """With AELLI_LITELLM_BASE set, auth token goes in Authorization: Bearer (gateway)."""
        from capabilities.escalate import handle_escalate
        mock_resp = _make_mock_response(status_code=200, json_data={"result": "ok"})
        with patch("httpx.Client.post", return_value=mock_resp) as mock_post:
            with patch.dict(os.environ, {
                "AELLI_AUTH_TOKEN": "gateway-key",
                "AELLI_LITELLM_BASE": "http://litellm.local",
            }):
                _run(handle_escalate({"question": "Is this the gateway path?"}))
        call_headers = mock_post.call_args.kwargs.get("headers", {})
        self.assertIn("Authorization", call_headers)
        self.assertEqual(call_headers["Authorization"], "Bearer gateway-key")
        self.assertNotIn("x-aelli-secret", call_headers)

    def test_no_auth_header_when_no_token(self):
        """With no AELLI_AUTH_TOKEN, neither auth header is sent."""
        from capabilities.escalate import handle_escalate
        mock_resp = _make_mock_response(status_code=200, json_data={})
        with patch("httpx.Client.post", return_value=mock_resp) as mock_post:
            _run(handle_escalate({"question": "No token test"}))
        call_headers = mock_post.call_args.kwargs.get("headers", {})
        self.assertNotIn("Authorization", call_headers)
        self.assertNotIn("x-aelli-secret", call_headers)


if __name__ == "__main__":
    unittest.main()
