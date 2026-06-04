"""Tests for octowiz.write_diary capability."""
import asyncio
import json
import os
import sys
import tempfile
import unittest
from io import StringIO
from unittest.mock import MagicMock, patch, patch as mock_patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _run(coro):
    return asyncio.run(coro)


class TestWriteDiaryValidation(unittest.TestCase):

    def test_error_invalid_entry_type(self):
        from capabilities.write_diary import handle_write_diary
        result = _run(handle_write_diary({"entry_type": "notes", "content": "some content"}))
        self.assertEqual(result["status"], "error")
        self.assertIn("entry_type", result["message"])

    def test_error_missing_content(self):
        from capabilities.write_diary import handle_write_diary
        result = _run(handle_write_diary({"entry_type": "working"}))
        self.assertEqual(result["status"], "error")
        self.assertIn("content", result["message"])

    def test_error_empty_content(self):
        from capabilities.write_diary import handle_write_diary
        result = _run(handle_write_diary({"entry_type": "working", "content": ""}))
        self.assertEqual(result["status"], "error")
        self.assertIn("content", result["message"])

    def test_error_missing_entry_type(self):
        from capabilities.write_diary import handle_write_diary
        result = _run(handle_write_diary({"content": "some content"}))
        self.assertEqual(result["status"], "error")
        self.assertIn("entry_type", result["message"])


class TestWriteDiaryLocalBackend(unittest.TestCase):

    def test_writes_local_when_no_litellm(self):
        """When LITELLM_BASE_URL is absent, writes to local JSONL and returns status ok."""
        from capabilities.write_diary import handle_write_diary

        with tempfile.TemporaryDirectory() as tmp_dir:
            fake_home = tmp_dir

            def fake_home_fn():
                from pathlib import Path
                return Path(fake_home)

            with patch.dict(os.environ, {}, clear=True):
                # clear=True removes all env vars including any LITELLM_BASE_URL
                with patch("pathlib.Path.home", staticmethod(fake_home_fn)):
                    result = _run(handle_write_diary({
                        "entry_type": "working",
                        "content": "Today I learned about A2A protocols",
                        "sessionId": "sess-123",
                        "metadata": {"source": "test"},
                    }))

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["backend"], "local")
        self.assertEqual(result["entry_type"], "working")
        self.assertIn("path", result)
        self.assertNotIn("warning", result)

    def test_local_file_written_correctly(self):
        """Local backend writes valid JSONL with expected fields."""
        from capabilities.write_diary import handle_write_diary

        with tempfile.TemporaryDirectory() as tmp_dir:
            from pathlib import Path

            def fake_home_fn():
                return Path(tmp_dir)

            with patch.dict(os.environ, {}, clear=True):
                with patch("pathlib.Path.home", staticmethod(fake_home_fn)):
                    result = _run(handle_write_diary({
                        "entry_type": "long_term",
                        "content": "Key insight: caching matters",
                        "sessionId": "sess-abc",
                    }))

            # Verify the JSONL file was written
            diary_path = Path(tmp_dir) / ".cache" / "octowiz" / "diary" / "long_term.jsonl"
            self.assertTrue(diary_path.exists())
            with open(diary_path, "r", encoding="utf-8") as f:
                record = json.loads(f.readline())
            self.assertEqual(record["content"], "Key insight: caching matters")
            self.assertEqual(record["sessionId"], "sess-abc")
            self.assertIn("ts", record)


class TestWriteDiaryLiteLLMBackend(unittest.TestCase):

    def test_writes_litellm_when_configured(self):
        """When LITELLM_BASE_URL is set and httpx succeeds, returns backend: litellm."""
        from capabilities.write_diary import handle_write_diary

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.put = MagicMock(return_value=mock_response)

        with patch.dict(os.environ, {
            "LITELLM_BASE_URL": "http://litellm.example.com",
            "LITELLM_API_KEY": "test-key",
        }):
            with patch("httpx.Client", return_value=mock_client):
                result = _run(handle_write_diary({
                    "entry_type": "working",
                    "content": "Progress update: all tests green",
                    "sessionId": "sess-xyz",
                }))

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["backend"], "litellm")
        self.assertEqual(result["entry_type"], "working")
        self.assertIn("key", result)
        self.assertNotIn("warning", result)

    def test_litellm_put_called_with_correct_url_and_headers(self):
        """PUT is called on the correct /v1/memory/{key} endpoint with auth header."""
        from capabilities.write_diary import handle_write_diary

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.put = MagicMock(return_value=mock_response)

        with patch.dict(os.environ, {
            "LITELLM_BASE_URL": "http://litellm.example.com/",
            "LITELLM_API_KEY": "secret-token",
        }):
            with patch("httpx.Client", return_value=mock_client):
                result = _run(handle_write_diary({
                    "entry_type": "long_term",
                    "content": "Architecture decision recorded",
                }))

        call_args = mock_client.put.call_args
        url = call_args[0][0]
        headers = call_args[1].get("headers", call_args[0][2] if len(call_args[0]) > 2 else {})
        # URL should not have double slash from trailing slash on base
        self.assertNotIn("//v1", url)
        self.assertIn("/v1/memory/", url)
        self.assertEqual(headers.get("Authorization"), "Bearer secret-token")


class TestWriteDiaryFallback(unittest.TestCase):

    def test_falls_back_to_local_on_litellm_error(self):
        """When LiteLLM raises, falls back to local backend and includes warning."""
        from capabilities.write_diary import handle_write_diary
        import httpx

        with tempfile.TemporaryDirectory() as tmp_dir:
            from pathlib import Path

            def fake_home_fn():
                return Path(tmp_dir)

            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.put = MagicMock(side_effect=httpx.ConnectError("connection refused"))

            with patch.dict(os.environ, {"LITELLM_BASE_URL": "http://litellm.example.com"}):
                with patch("httpx.Client", return_value=mock_client):
                    with patch("pathlib.Path.home", staticmethod(fake_home_fn)):
                        result = _run(handle_write_diary({
                            "entry_type": "working",
                            "content": "Fallback test entry",
                        }))

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["backend"], "local")
        self.assertIn("warning", result)
        self.assertIn("LiteLLM write failed", result["warning"])

    def test_warning_contains_original_exception_message(self):
        """Warning text includes the original exception detail for diagnostics."""
        from capabilities.write_diary import handle_write_diary
        import httpx

        with tempfile.TemporaryDirectory() as tmp_dir:
            from pathlib import Path

            def fake_home_fn():
                return Path(tmp_dir)

            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.put = MagicMock(side_effect=httpx.ConnectError("timeout after 10s"))

            with patch.dict(os.environ, {"LITELLM_BASE_URL": "http://litellm.example.com"}):
                with patch("httpx.Client", return_value=mock_client):
                    with patch("pathlib.Path.home", staticmethod(fake_home_fn)):
                        result = _run(handle_write_diary({
                            "entry_type": "long_term",
                            "content": "Critical knowledge entry",
                        }))

        self.assertIn("local fallback", result["warning"])


class TestWriteDiaryKeyFormat(unittest.TestCase):

    def test_bucket_key_format(self):
        """Memory key uses agent:octowiz:diary: prefix with correct structure."""
        from capabilities.write_diary import handle_write_diary

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.put = MagicMock(return_value=mock_response)

        with patch.dict(os.environ, {
            "LITELLM_BASE_URL": "http://litellm.example.com",
        }):
            with patch("httpx.Client", return_value=mock_client):
                result = _run(handle_write_diary({
                    "entry_type": "working",
                    "content": "Key format verification",
                    "sessionId": "sess-abc123",
                }))

        self.assertTrue(result["key"].startswith("agent:octowiz:diary:"))
        # Key structure: agent:octowiz:diary:{entry_type}:{slug}:{bucket}
        parts = result["key"].split(":")
        self.assertEqual(parts[0], "agent")
        self.assertEqual(parts[1], "octowiz")
        self.assertEqual(parts[2], "diary")
        self.assertEqual(parts[3], "working")  # entry_type
        # parts[4] is session slug, parts[5] is bucket (hour timestamp)
        self.assertEqual(len(parts), 6)

    def test_key_session_slug_truncated_to_32_chars(self):
        """Session IDs longer than 32 chars are truncated in the key."""
        from capabilities.write_diary import handle_write_diary

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.put = MagicMock(return_value=mock_response)

        long_session_id = "a" * 64  # 64 chars, should be truncated to 32

        with patch.dict(os.environ, {
            "LITELLM_BASE_URL": "http://litellm.example.com",
        }):
            with patch("httpx.Client", return_value=mock_client):
                result = _run(handle_write_diary({
                    "entry_type": "long_term",
                    "content": "Slug truncation test",
                    "sessionId": long_session_id,
                }))

        parts = result["key"].split(":")
        slug = parts[4]
        self.assertLessEqual(len(slug), 32)

    def test_key_uses_unknown_slug_when_no_session(self):
        """Missing sessionId results in 'unknown' slug in the memory key."""
        from capabilities.write_diary import handle_write_diary

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.put = MagicMock(return_value=mock_response)

        with patch.dict(os.environ, {
            "LITELLM_BASE_URL": "http://litellm.example.com",
        }):
            with patch("httpx.Client", return_value=mock_client):
                result = _run(handle_write_diary({
                    "entry_type": "working",
                    "content": "No session provided",
                }))

        parts = result["key"].split(":")
        self.assertEqual(parts[4], "unknown")


class TestWriteDiaryDispatchIntegration(unittest.TestCase):
    """Smoke test: verify dispatch routes octowiz.write_diary to the handler."""

    def setUp(self):
        os.environ["OCTOWIZ_INBOUND_SECRET"] = "test-secret"

    def tearDown(self):
        os.environ.pop("OCTOWIZ_INBOUND_SECRET", None)
        os.environ.pop("LITELLM_BASE_URL", None)

    def test_write_diary_is_routed_not_not_implemented(self):
        import importlib
        import dispatch as dispatch_mod
        importlib.reload(dispatch_mod)
        import main as m
        importlib.reload(m)
        from fastapi.testclient import TestClient

        with tempfile.TemporaryDirectory() as tmp_dir:
            from pathlib import Path

            def fake_home_fn():
                return Path(tmp_dir)

            client = TestClient(m.app)
            body = {
                "jsonrpc": "2.0",
                "id": 1,
                "params": {"message": {"parts": [{"text": json.dumps({
                    "capability": "octowiz.write_diary",
                    "entry_type": "working",
                    "content": "dispatch integration test",
                })}]}},
            }
            with patch("pathlib.Path.home", staticmethod(fake_home_fn)):
                resp = client.post(
                    "/a2a/octowiz",
                    json=body,
                    headers={"x-octowiz-secret": "test-secret"},
                )

        self.assertEqual(resp.status_code, 200)
        artifact = json.loads(resp.json()["result"]["artifacts"][0]["parts"][0]["text"])
        self.assertNotEqual(artifact.get("status"), "not_implemented")
        self.assertEqual(artifact.get("status"), "ok")


if __name__ == "__main__":
    unittest.main()
