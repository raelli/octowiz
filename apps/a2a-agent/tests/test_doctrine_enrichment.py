"""Tests for the shared doctrine-enrichment capability handler."""
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


def _builder(event, context):
    return f"prompt:{event.get('role_hint', 'x')}:{context or ''}"


class TestDoctrineEnrichmentNoLiteLLM(unittest.TestCase):

    def test_returns_ok_without_litellm_base_url(self):
        from capabilities.doctrine_enrichment import handle_doctrine_enrichment
        with patch.dict(os.environ, {}, clear=True):
            result = _run(handle_doctrine_enrichment({}, "planner", _builder))
        self.assertEqual(result["status"], "ok")
        self.assertIsNone(result["doctrine"])
        self.assertNotIn("warning", result)

    def test_role_reflected_in_result(self):
        from capabilities.doctrine_enrichment import handle_doctrine_enrichment
        with patch.dict(os.environ, {}, clear=True):
            result = _run(handle_doctrine_enrichment({}, "reviewer", _builder))
        self.assertEqual(result["role"], "reviewer")

    def test_default_namespace_is_gfe(self):
        from capabilities.doctrine_enrichment import handle_doctrine_enrichment
        with patch.dict(os.environ, {}, clear=True):
            result = _run(handle_doctrine_enrichment({}, "planner", _builder))
        self.assertEqual(result["namespace"], "gfe")

    def test_namespace_from_event_overrides(self):
        from capabilities.doctrine_enrichment import handle_doctrine_enrichment
        with patch.dict(os.environ, {}, clear=True):
            result = _run(handle_doctrine_enrichment({"namespace": "acme"}, "planner", _builder))
        self.assertEqual(result["namespace"], "acme")

    def test_namespace_from_env_var(self):
        from capabilities.doctrine_enrichment import handle_doctrine_enrichment
        with patch.dict(os.environ, {"OCTOWIZ_MEMORY_NAMESPACE": "myteam"}, clear=True):
            result = _run(handle_doctrine_enrichment({}, "planner", _builder))
        self.assertEqual(result["namespace"], "myteam")

    def test_prompt_builder_called(self):
        from capabilities.doctrine_enrichment import handle_doctrine_enrichment
        with patch.dict(os.environ, {}, clear=True):
            result = _run(handle_doctrine_enrichment({"role_hint": "z"}, "planner", _builder))
        self.assertEqual(result["suggested_prompt"], "prompt:z:")


class TestDoctrineEnrichmentWithLiteLLM(unittest.TestCase):

    def test_doctrine_returned_on_success(self):
        from capabilities.doctrine_enrichment import handle_doctrine_enrichment
        fake = "# bundle"
        with patch("memory_client.cache.get_bundle", return_value=fake):
            with patch.dict(os.environ, {"LITELLM_BASE_URL": "http://llm.local"}):
                result = _run(handle_doctrine_enrichment({}, "planner", _builder))
        self.assertEqual(result["doctrine"], fake)
        self.assertNotIn("warning", result)

    def test_source_injected_into_get_bundle(self):
        from capabilities.doctrine_enrichment import handle_doctrine_enrichment

        class _StubSource:
            def fetch(self, key):
                return {"key": key, "value": "stub", "metadata": {}}

        stub = _StubSource()
        with patch("memory_client.cache.get_bundle", return_value="bundle") as mock_get:
            with patch.dict(os.environ, {"LITELLM_BASE_URL": "http://llm.local"}):
                _run(handle_doctrine_enrichment({}, "planner", _builder, source=stub))
        mock_get.assert_called_once_with("planner", "gfe", source=stub)

    def test_doctrine_none_and_warning_on_fetch_error(self):
        from capabilities.doctrine_enrichment import handle_doctrine_enrichment
        with patch("memory_client.cache.get_bundle", side_effect=Exception("timeout")):
            with patch.dict(os.environ, {"LITELLM_BASE_URL": "http://llm.local"}):
                result = _run(handle_doctrine_enrichment({}, "planner", _builder))
        self.assertIsNone(result["doctrine"])
        self.assertIn("warning", result)
        self.assertIn("timeout", result["warning"])
        self.assertEqual(result["status"], "ok")


if __name__ == "__main__":
    unittest.main()
