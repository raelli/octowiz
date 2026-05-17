import httpx
import importlib
import json
import os
import sys
import tempfile
import unittest
import urllib.parse
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import import_litellm_memories as _importer_module
from import_litellm_memories import load_memories, main, validate_memories, rewrite_namespace


class TestValidateMemories(unittest.TestCase):
    def test_valid_memories_pass(self):
        memories = [{"key": "k1", "value": "v1"}, {"key": "k2", "value": "v2"}]
        validate_memories(memories)  # must not raise or exit

    def test_missing_value_exits_1(self):
        memories = [{"key": "k1"}]
        with self.assertRaises(SystemExit) as ctx:
            validate_memories(memories)
        self.assertEqual(ctx.exception.code, 1)

    def test_missing_key_exits_1(self):
        memories = [{"value": "v1"}]
        with self.assertRaises(SystemExit) as ctx:
            validate_memories(memories)
        self.assertEqual(ctx.exception.code, 1)

    def test_empty_key_exits_1(self):
        memories = [{"key": "", "value": "v1"}]
        with self.assertRaises(SystemExit) as ctx:
            validate_memories(memories)
        self.assertEqual(ctx.exception.code, 1)

    def test_non_string_value_exits_1(self):
        memories = [{"key": "k1", "value": 42}]
        with self.assertRaises(SystemExit) as ctx:
            validate_memories(memories)
        self.assertEqual(ctx.exception.code, 1)


class TestRewriteNamespace(unittest.TestCase):
    def test_rewrites_team_namespace(self):
        memories = [{"key": "team:allspark:playbook:overview", "value": "v"}]
        result = rewrite_namespace(memories, "integrahub")
        self.assertEqual(result[0]["key"], "team:integrahub:playbook:overview")

    def test_rewrites_project_namespace(self):
        memories = [{"key": "project:allspark:config:setup", "value": "v"}]
        result = rewrite_namespace(memories, "myteam")
        self.assertEqual(result[0]["key"], "project:myteam:config:setup")

    def test_does_not_modify_agent_keys(self):
        memories = [{"key": "agent:planner:memory:workflow", "value": "v"}]
        result = rewrite_namespace(memories, "integrahub")
        self.assertEqual(result[0]["key"], "agent:planner:memory:workflow")

    def test_does_not_mutate_original(self):
        memories = [{"key": "team:allspark:test", "value": "v"}]
        rewrite_namespace(memories, "x")
        self.assertEqual(memories[0]["key"], "team:allspark:test")

    def test_rewrites_both_prefixes_in_one_call(self):
        memories = [
            {"key": "team:allspark:playbook:overview", "value": "v1"},
            {"key": "project:allspark:config:setup", "value": "v2"},
            {"key": "agent:planner:memory:workflow", "value": "v3"},
        ]
        result = rewrite_namespace(memories, "acme")
        self.assertEqual(result[0]["key"], "team:acme:playbook:overview")
        self.assertEqual(result[1]["key"], "project:acme:config:setup")
        self.assertEqual(result[2]["key"], "agent:planner:memory:workflow")

    def test_rewrites_allspark_refs_in_value(self):
        contract = '{"A_fresh": ["team:allspark:playbook:overview", "team:allspark:skills:hub"]}'
        memories = [{"key": "team:allspark:config:retrieval-contract", "value": contract}]
        result = rewrite_namespace(memories, "myorg")
        self.assertNotIn("allspark", result[0]["value"])
        self.assertIn("team:myorg:playbook:overview", result[0]["value"])
        self.assertIn("team:myorg:skills:hub", result[0]["value"])


class TestLoadMemories(unittest.TestCase):
    def _write_temp(self, content, suffix):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False)
        f.write(content)
        f.close()
        return f.name

    def test_load_json_list(self):
        data = [{"key": "k1", "value": "v1"}, {"key": "k2", "value": "v2"}]
        path = self._write_temp(json.dumps(data), ".json")
        try:
            self.assertEqual(load_memories(path), data)
        finally:
            os.unlink(path)

    def test_load_json_object_with_memories_key(self):
        data = {"memories": [{"key": "k1", "value": "v1"}]}
        path = self._write_temp(json.dumps(data), ".json")
        try:
            self.assertEqual(load_memories(path), data["memories"])
        finally:
            os.unlink(path)

    def test_load_jsonl(self):
        lines = '{"key": "k1", "value": "v1"}\n{"key": "k2", "value": "v2"}\n'
        path = self._write_temp(lines, ".jsonl")
        try:
            result = load_memories(path)
            self.assertEqual(len(result), 2)
            self.assertEqual(result[1]["key"], "k2")
        finally:
            os.unlink(path)


class TestPrefixFilter(unittest.TestCase):
    def test_prefix_filter_excludes_non_matching(self):
        data = [
            {"key": "team:allspark:playbook:overview", "value": "v1"},
            {"key": "team:allspark:skills:mattpocock", "value": "v2"},
            {"key": "agent:planner:memory:workflow", "value": "v3"},
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name
        try:
            mock_response = MagicMock()
            mock_response.raise_for_status.return_value = None
            mock_client_instance = MagicMock()
            mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
            mock_client_instance.__exit__ = MagicMock(return_value=False)
            mock_client_instance.put.return_value = mock_response
            with patch("httpx.Client", return_value=mock_client_instance):
                with patch.dict(os.environ, {"LITELLM_API_KEY": "sk-test", "LITELLM_BASE_URL": "http://localhost:4000"}):
                    with patch("sys.argv", ["import_litellm_memories.py", path, "--key-prefix", "team:allspark:skills:"]):
                        importlib.reload(_importer_module)
                        result = _importer_module.main()
            self.assertEqual(result, 0)
            self.assertEqual(mock_client_instance.put.call_count, 1)
            self.assertIn("team%3Aallspark%3Askills%3Amattpocock", mock_client_instance.put.call_args[0][0])
        finally:
            os.unlink(path)


class TestUrlEncoding(unittest.TestCase):
    def test_colons_encoded_correctly(self):
        data = [{"key": "team:allspark:playbook:overview", "value": "v1"}]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name
        try:
            mock_response = MagicMock()
            mock_response.raise_for_status.return_value = None
            mock_client_instance = MagicMock()
            mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
            mock_client_instance.__exit__ = MagicMock(return_value=False)
            mock_client_instance.put.return_value = mock_response
            with patch("httpx.Client", return_value=mock_client_instance):
                with patch.dict(os.environ, {"LITELLM_API_KEY": "sk-test", "LITELLM_BASE_URL": "http://localhost:4000"}):
                    with patch("sys.argv", ["import_litellm_memories.py", path]):
                        importlib.reload(_importer_module)
                        result = _importer_module.main()
            call_url = mock_client_instance.put.call_args[0][0]
            self.assertIn("%3A", call_url)
            self.assertEqual(result, 0)
        finally:
            os.unlink(path)


class TestDryRun(unittest.TestCase):
    def test_dry_run_makes_no_http_calls(self):
        data = [{"key": "k1", "value": "v1"}]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name
        try:
            with patch("httpx.Client") as mock_client:
                with patch("sys.argv", ["import_litellm_memories.py", path, "--dry-run"]):
                    result = main()
                mock_client.assert_not_called()
                self.assertEqual(result, 0)
        finally:
            os.unlink(path)


class TestBadHttpResponse(unittest.TestCase):
    def test_failed_http_response_exits_1(self):
        data = [{"key": "k1", "value": "v1"}]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name
        try:
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "404 Not Found",
                request=MagicMock(),
                response=MagicMock(status_code=404, text="Not Found"),
            )
            mock_client_instance = MagicMock()
            mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
            mock_client_instance.__exit__ = MagicMock(return_value=False)
            mock_client_instance.put.return_value = mock_response

            with patch("httpx.Client", return_value=mock_client_instance):
                with patch.dict(os.environ, {"LITELLM_API_KEY": "sk-test", "LITELLM_BASE_URL": "http://localhost:4000"}):
                    with patch("sys.argv", ["import_litellm_memories.py", path]):
                        result = main()
            self.assertEqual(result, 1)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
