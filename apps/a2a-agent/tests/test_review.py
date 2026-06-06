"""Tests for octowiz.review capability."""
import asyncio
import os
import sys
import unittest
from unittest.mock import patch

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(_HERE))), "packages"))

os.environ.setdefault("OCTOWIZ_INBOUND_SECRET", "test-secret")


def _run(coro):
    return asyncio.run(coro)


class TestReviewValidation(unittest.TestCase):

    def test_error_when_cwd_missing(self):
        from capabilities.review import handle_review
        result = _run(handle_review({}))
        self.assertEqual(result["status"], "error")
        self.assertIn("cwd is required", result["message"])

    def test_error_when_cwd_empty_string(self):
        from capabilities.review import handle_review
        result = _run(handle_review({"cwd": ""}))
        self.assertEqual(result["status"], "error")
        self.assertIn("cwd is required", result["message"])

    def test_path_guard_applied(self):
        from capabilities.review import handle_review
        # Relative path trips path_guard's absolute-path check.
        result = _run(handle_review({"cwd": "relative/path"}))
        self.assertEqual(result["status"], "error")
        self.assertIn("absolute", result["message"])


class TestReviewWithoutLiteLLM(unittest.TestCase):

    def test_ok_without_litellm(self):
        from capabilities.review import handle_review
        with patch.dict(os.environ, {"OCTOWIZ_ALLOWED_ROOTS": "/tmp", "OCTOWIZ_INBOUND_SECRET": "test-secret"}, clear=True):
            result = _run(handle_review({"cwd": "/tmp"}))
        self.assertEqual(result["status"], "ok")
        self.assertIsNone(result["doctrine"])
        self.assertNotIn("warning", result)

    def test_role_is_reviewer(self):
        from capabilities.review import handle_review
        with patch.dict(os.environ, {"OCTOWIZ_ALLOWED_ROOTS": "/tmp"}, clear=True):
            result = _run(handle_review({"cwd": "/tmp"}))
        self.assertEqual(result["role"], "reviewer")

    def test_cwd_echoed_in_response(self):
        from capabilities.review import handle_review
        with patch.dict(os.environ, {"OCTOWIZ_ALLOWED_ROOTS": "/tmp"}, clear=True):
            result = _run(handle_review({"cwd": "/tmp"}))
        # validate_cwd canonicalizes; /tmp should resolve to /private/tmp on macOS
        # but in either case the returned cwd should be an absolute path
        self.assertTrue(result["cwd"].startswith("/"))

    def test_default_namespace_is_gfe(self):
        from capabilities.review import handle_review
        with patch.dict(os.environ, {"OCTOWIZ_ALLOWED_ROOTS": "/tmp"}, clear=True):
            result = _run(handle_review({"cwd": "/tmp"}))
        self.assertEqual(result["namespace"], "gfe")

    def test_namespace_from_event_overrides_default(self):
        from capabilities.review import handle_review
        with patch.dict(os.environ, {"OCTOWIZ_ALLOWED_ROOTS": "/tmp"}, clear=True):
            result = _run(handle_review({"cwd": "/tmp", "namespace": "acme"}))
        self.assertEqual(result["namespace"], "acme")

    def test_session_id_none_when_absent(self):
        from capabilities.review import handle_review
        with patch.dict(os.environ, {"OCTOWIZ_ALLOWED_ROOTS": "/tmp"}, clear=True):
            result = _run(handle_review({"cwd": "/tmp"}))
        self.assertIsNone(result["sessionId"])


class TestReviewWithDoctrine(unittest.TestCase):

    def test_ok_with_doctrine(self):
        from capabilities.review import handle_review
        fake_doctrine = {"checklist": ["tests pass", "no secrets"], "role": "senior reviewer"}
        with patch("memory_client.namespace.load_role_bundle", return_value=fake_doctrine):
            with patch.dict(os.environ, {"LITELLM_BASE_URL": "http://litellm.local", "LITELLM_API_KEY": "key123", "OCTOWIZ_ALLOWED_ROOTS": "/tmp"}):
                result = _run(handle_review({"cwd": "/tmp"}))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["doctrine"], fake_doctrine)
        self.assertNotIn("warning", result)

    def test_doctrine_error_is_warning(self):
        import httpx
        from capabilities.review import handle_review
        with patch("memory_client.namespace.load_role_bundle", side_effect=httpx.RequestError("connection refused")):
            with patch.dict(os.environ, {"LITELLM_BASE_URL": "http://litellm.local", "LITELLM_API_KEY": "key123", "OCTOWIZ_ALLOWED_ROOTS": "/tmp"}):
                result = _run(handle_review({"cwd": "/tmp"}))
        self.assertEqual(result["status"], "ok")
        self.assertIsNone(result["doctrine"])
        self.assertIn("warning", result)


class TestReviewSuggestedPrompt(unittest.TestCase):

    def test_suggested_prompt_includes_cwd(self):
        from capabilities.review import handle_review
        with patch.dict(os.environ, {"OCTOWIZ_ALLOWED_ROOTS": "/tmp"}, clear=True):
            result = _run(handle_review({"cwd": "/tmp"}))
        self.assertIn("[octowiz.review]", result["suggested_prompt"])
        # cwd may be canonicalized (/tmp -> /private/tmp on macOS)
        self.assertIn("/", result["suggested_prompt"])

    def test_suggested_prompt_includes_session(self):
        from capabilities.review import handle_review
        with patch.dict(os.environ, {"OCTOWIZ_ALLOWED_ROOTS": "/tmp"}, clear=True):
            result = _run(handle_review({"cwd": "/tmp", "sessionId": "sess-abc123"}))
        self.assertIn("sess-abc123", result["suggested_prompt"])
        self.assertIn("session sess-abc123", result["suggested_prompt"])

    def test_suggested_prompt_includes_context(self):
        from capabilities.review import handle_review
        with patch.dict(os.environ, {"OCTOWIZ_ALLOWED_ROOTS": "/tmp"}, clear=True):
            result = _run(handle_review({
                "cwd": "/tmp",
                "context": "PR #42 — adds rate limiting",
            }))
        self.assertIn("Context:", result["suggested_prompt"])
        self.assertIn("PR #42", result["suggested_prompt"])

    def test_suggested_prompt_no_session_when_absent(self):
        from capabilities.review import handle_review
        with patch.dict(os.environ, {"OCTOWIZ_ALLOWED_ROOTS": "/tmp"}, clear=True):
            result = _run(handle_review({"cwd": "/tmp"}))
        self.assertNotIn("(session", result["suggested_prompt"])


if __name__ == "__main__":
    unittest.main()
