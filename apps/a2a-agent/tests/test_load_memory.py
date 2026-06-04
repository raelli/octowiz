"""Tests for octowiz.load_memory capability."""
import asyncio
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
# Make apps/a2a-agent importable (capabilities, dispatch, etc.)
sys.path.insert(0, os.path.dirname(_HERE))
# Make packages/ importable so `from memory_client import namespace` works
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(_HERE))), "packages"))

os.environ.setdefault("OCTOWIZ_INBOUND_SECRET", "test-secret")

import unittest
from unittest.mock import patch
import httpx


def _run(coro):
    return asyncio.run(coro)


class TestLoadMemoryUnavailable(unittest.TestCase):

    def setUp(self):
        os.environ.pop("LITELLM_BASE_URL", None)

    def tearDown(self):
        os.environ.pop("LITELLM_BASE_URL", None)

    def test_unavailable_when_no_base_url(self):
        from capabilities.load_memory import handle_load_memory
        result = _run(handle_load_memory({}))
        self.assertEqual(result["status"], "unavailable")
        self.assertIn("LITELLM_BASE_URL", result["message"])


class TestLoadMemoryBundle(unittest.TestCase):

    def setUp(self):
        os.environ["LITELLM_BASE_URL"] = "http://fake-litellm"
        os.environ["LITELLM_API_KEY"] = "fake-key"
        os.environ.pop("OCTOWIZ_MEMORY_NAMESPACE", None)

    def tearDown(self):
        os.environ.pop("LITELLM_BASE_URL", None)
        os.environ.pop("LITELLM_API_KEY", None)
        os.environ.pop("OCTOWIZ_MEMORY_NAMESPACE", None)

    def test_returns_bundle_for_role(self):
        from capabilities.load_memory import handle_load_memory
        with patch("memory_client.namespace.load_role_bundle", return_value={"key": "val"}) as mock_rb:
            result = _run(handle_load_memory({"role": "planner"}))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["bundle"], {"key": "val"})
        self.assertEqual(result["role"], "planner")
        mock_rb.assert_called_once()

    def test_returns_rules_for_project_id(self):
        from capabilities.load_memory import handle_load_memory
        with patch("memory_client.namespace.load_role_bundle", return_value={"bundle": "data"}), \
             patch("memory_client.namespace.load_project_rules", return_value={"rule": "x"}) as mock_pr:
            result = _run(handle_load_memory({"role": "reviewer", "project_id": "proj-42"}))
        self.assertEqual(result["status"], "ok")
        self.assertIn("rules", result)
        self.assertEqual(result["rules"], {"rule": "x"})
        mock_pr.assert_called_once()

    def test_error_on_http_error(self):
        from capabilities.load_memory import handle_load_memory
        with patch("memory_client.namespace.load_role_bundle",
                   side_effect=httpx.RequestError("connection refused")):
            result = _run(handle_load_memory({"role": "implementer"}))
        self.assertEqual(result["status"], "error")
        self.assertIn("connection refused", result["message"])

    def test_default_namespace_from_env(self):
        os.environ["OCTOWIZ_MEMORY_NAMESPACE"] = "testns"
        from capabilities.load_memory import handle_load_memory
        with patch("memory_client.namespace.load_role_bundle", return_value={}) as mock_rb:
            result = _run(handle_load_memory({}))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["namespace"], "testns")
        args = mock_rb.call_args[0]
        self.assertIn("testns", args)

    def test_rules_key_absent_when_no_project_id(self):
        from capabilities.load_memory import handle_load_memory
        with patch("memory_client.namespace.load_role_bundle", return_value={}):
            result = _run(handle_load_memory({"role": "implementer"}))
        self.assertNotIn("rules", result)


if __name__ == "__main__":
    unittest.main()
