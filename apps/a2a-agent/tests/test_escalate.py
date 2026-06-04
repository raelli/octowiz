"""Tests for octowiz.escalate_to_aelli capability."""
import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
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
        with patch("httpx.Client.post", side_effect=httpx.ConnectError("connection refused")):
            result = _run(handle_escalate({"question": "Is the deployment safe?"}))
        self.assertEqual(result["status"], "escalated")
        self.assertEqual(result["delivery"], "queued")
        self.assertIn("warning", result)

    def test_failopen_on_http_500(self):
        from capabilities.escalate import handle_escalate
        mock_resp = _make_mock_response(
            status_code=500,
            raise_on_status=httpx.HTTPStatusError(
                "500 Server Error",
                request=MagicMock(),
                response=MagicMock(status_code=500),
            ),
        )
        with patch("httpx.Client.post", return_value=mock_resp):
            result = _run(handle_escalate({"question": "Is the deployment safe?"}))
        self.assertEqual(result["status"], "escalated")
        self.assertEqual(result["delivery"], "queued")


class TestEscalateAuthHeader(unittest.TestCase):

    def setUp(self):
        os.environ.pop("AELLI_AUTH_TOKEN", None)

    def tearDown(self):
        os.environ.pop("AELLI_AUTH_TOKEN", None)

    def test_auth_header_sent_when_token_set(self):
        from capabilities.escalate import handle_escalate
        mock_resp = _make_mock_response(status_code=200, json_data={"result": "ok"})
        with patch("httpx.Client.post", return_value=mock_resp) as mock_post:
            with patch.dict(os.environ, {"AELLI_AUTH_TOKEN": "secret-token-abc"}):
                _run(handle_escalate({"question": "Prioritize next quarter goals?"}))
        mock_post.assert_called_once()
        call_headers = mock_post.call_args.kwargs.get("headers", {})
        self.assertIn("Authorization", call_headers)
        self.assertEqual(call_headers["Authorization"], "Bearer secret-token-abc")


if __name__ == "__main__":
    unittest.main()
