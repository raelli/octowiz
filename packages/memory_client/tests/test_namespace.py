"""Tests for namespace/project-rules loader."""
import json
import unittest
from unittest.mock import MagicMock, patch
import httpx


class TestLoadProjectRules(unittest.TestCase):

    def test_fetches_correct_memory_key(self):
        """load_project_rules fetches project:{id}:octowiz:rules."""
        with patch("packages.memory_client.namespace.httpx") as mock_httpx:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {"content": json.dumps({"rule": "no force push"})}
            mock_httpx.get.return_value = mock_response

            from packages.memory_client.namespace import load_project_rules
            load_project_rules(
                base_url="http://localhost:4000",
                api_key="sk-test",
                project_id="proj-abc",
            )

            url = mock_httpx.get.call_args[0][0]
            self.assertIn("project:proj-abc:octowiz:rules", url)

    def test_returns_parsed_dict_on_200(self):
        """load_project_rules returns parsed dict on success."""
        with patch("packages.memory_client.namespace.httpx") as mock_httpx:
            rules = {"no_force_push": True, "require_review": True}
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {"content": json.dumps(rules)}
            mock_httpx.get.return_value = mock_response

            from packages.memory_client.namespace import load_project_rules
            result = load_project_rules("http://localhost:4000", "sk-test", "proj-abc")
            self.assertEqual(result, rules)

    def test_raises_on_http_error(self):
        """load_project_rules propagates HTTP errors."""
        with patch("packages.memory_client.namespace.httpx") as mock_httpx:
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "404", request=MagicMock(), response=MagicMock()
            )
            mock_httpx.get.return_value = mock_response
            mock_httpx.HTTPStatusError = httpx.HTTPStatusError

            from packages.memory_client.namespace import load_project_rules
            with self.assertRaises(httpx.HTTPStatusError):
                load_project_rules("http://localhost:4000", "sk-test", "proj-x")


class TestLoadRoleBundle(unittest.TestCase):

    def test_fetches_correct_role_key(self):
        """load_role_bundle fetches team:{namespace}:octowiz:roles:{role}."""
        with patch("packages.memory_client.namespace.httpx") as mock_httpx:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {"content": json.dumps({"role": "implementer"})}
            mock_httpx.get.return_value = mock_response

            from packages.memory_client.namespace import load_role_bundle
            load_role_bundle(
                base_url="http://localhost:4000",
                api_key="sk-test",
                role="implementer",
                namespace="allspark",
            )

            url = mock_httpx.get.call_args[0][0]
            self.assertIn("team:allspark:octowiz:roles:implementer", url)

    def test_returns_parsed_dict_on_200(self):
        """load_role_bundle returns parsed dict from content field."""
        with patch("packages.memory_client.namespace.httpx") as mock_httpx:
            bundle = {"tdd": True, "deep_modules": True}
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {"content": json.dumps(bundle)}
            mock_httpx.get.return_value = mock_response

            from packages.memory_client.namespace import load_role_bundle
            result = load_role_bundle("http://localhost:4000", "sk-test", "planner", "allspark")
            self.assertEqual(result, bundle)


if __name__ == "__main__":
    unittest.main()
