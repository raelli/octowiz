"""Tests for octowiz.plan capability."""
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


class TestPlanValidation(unittest.TestCase):

    def test_error_when_task_missing(self):
        from capabilities.plan import handle_plan
        result = _run(handle_plan({}))
        self.assertEqual(result["status"], "error")
        self.assertIn("task is required", result["message"])

    def test_error_when_task_empty_string(self):
        from capabilities.plan import handle_plan
        result = _run(handle_plan({"task": ""}))
        self.assertEqual(result["status"], "error")
        self.assertIn("task is required", result["message"])


class TestPlanWithoutLiteLLM(unittest.TestCase):

    def test_ok_without_litellm(self):
        from capabilities.plan import handle_plan
        # Ensure LITELLM_BASE_URL is absent so the doctrine-fetch branch is skipped.
        with patch.dict(os.environ, {}, clear=True):
            os.environ["OCTOWIZ_INBOUND_SECRET"] = "test-secret"
            result = _run(handle_plan({"task": "add auth feature"}))
        self.assertEqual(result["status"], "ok")
        self.assertIsNone(result["doctrine"])
        self.assertNotIn("warning", result)

    def test_role_is_planner(self):
        from capabilities.plan import handle_plan
        with patch.dict(os.environ, {}, clear=True):
            result = _run(handle_plan({"task": "add tests"}))
        self.assertEqual(result["role"], "planner")

    def test_task_echoed_in_response(self):
        from capabilities.plan import handle_plan
        with patch.dict(os.environ, {}, clear=True):
            result = _run(handle_plan({"task": "refactor DB layer"}))
        self.assertEqual(result["task"], "refactor DB layer")

    def test_default_namespace_is_gfe(self):
        from capabilities.plan import handle_plan
        with patch.dict(os.environ, {}, clear=True):
            result = _run(handle_plan({"task": "add tests"}))
        self.assertEqual(result["namespace"], "gfe")

    def test_namespace_from_event_overrides_default(self):
        from capabilities.plan import handle_plan
        with patch.dict(os.environ, {}, clear=True):
            result = _run(handle_plan({"task": "add tests", "namespace": "acme"}))
        self.assertEqual(result["namespace"], "acme")

    def test_namespace_from_env_var(self):
        from capabilities.plan import handle_plan
        with patch.dict(os.environ, {"OCTOWIZ_MEMORY_NAMESPACE": "myteam"}, clear=True):
            result = _run(handle_plan({"task": "add tests"}))
        self.assertEqual(result["namespace"], "myteam")


class TestPlanWithDoctrine(unittest.TestCase):

    def test_ok_with_doctrine(self):
        from capabilities.plan import handle_plan
        fake_doctrine = "# Octowiz Doctrine Bundle: planner\n\n## key\n\nthink step by step\n"
        with patch("memory_client.cache.get_bundle", return_value=fake_doctrine):
            with patch.dict(os.environ, {"LITELLM_BASE_URL": "http://litellm.local", "LITELLM_API_KEY": "key123"}):
                result = _run(handle_plan({"task": "build feature X"}))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["doctrine"], fake_doctrine)
        self.assertNotIn("warning", result)

    def test_doctrine_error_is_warning(self):
        from capabilities.plan import handle_plan
        with patch("memory_client.cache.get_bundle", side_effect=Exception("connection refused")):
            with patch.dict(os.environ, {"LITELLM_BASE_URL": "http://litellm.local", "LITELLM_API_KEY": "key123"}):
                result = _run(handle_plan({"task": "build feature X"}))
        self.assertEqual(result["status"], "ok")
        self.assertIsNone(result["doctrine"])
        self.assertIn("warning", result)
        self.assertIn("connection refused", result["warning"])


class TestPlanSuggestedPrompt(unittest.TestCase):

    def test_suggested_prompt_includes_task(self):
        from capabilities.plan import handle_plan
        with patch.dict(os.environ, {}, clear=True):
            result = _run(handle_plan({"task": "implement OAuth2"}))
        self.assertIn("[octowiz.plan]", result["suggested_prompt"])
        self.assertIn("implement OAuth2", result["suggested_prompt"])

    def test_suggested_prompt_includes_context(self):
        from capabilities.plan import handle_plan
        with patch.dict(os.environ, {}, clear=True):
            result = _run(handle_plan({
                "task": "refactor auth",
                "context": "JWT tokens expire too fast",
            }))
        self.assertIn("Context:", result["suggested_prompt"])
        self.assertIn("JWT tokens expire too fast", result["suggested_prompt"])

    def test_suggested_prompt_no_context_section_when_absent(self):
        from capabilities.plan import handle_plan
        with patch.dict(os.environ, {}, clear=True):
            result = _run(handle_plan({"task": "add tests"}))
        self.assertNotIn("Context:", result["suggested_prompt"])

    def test_suggested_prompt_with_dict_context(self):
        from capabilities.plan import handle_plan
        with patch.dict(os.environ, {}, clear=True):
            ctx = {"pr": "123", "diff": "..."}
            result = _run(handle_plan({"task": "review PR", "context": ctx}))
        self.assertIn("Context:", result["suggested_prompt"])


if __name__ == "__main__":
    unittest.main()
