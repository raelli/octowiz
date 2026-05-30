"""Tests for octowiz-cache seed — project namespace seeding into LiteLLM Memory."""
import json
import os
import subprocess
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from packages.memory_client.env import derive_project_id, seed_project_namespace


def _mock_client(get_status=404, rules_value=None):
    """Return a mock httpx.Client for seeding tests."""
    client = unittest.mock.MagicMock()

    def _get(url, **kwargs):
        resp = unittest.mock.MagicMock()
        resp.status_code = get_status
        if get_status == 200 and rules_value is not None and "rules" in url:
            resp.json.return_value = {"value": rules_value}
        elif get_status == 200:
            resp.json.return_value = {"value": "{}"}
        return resp

    client.get.side_effect = _get
    put_resp = unittest.mock.MagicMock()
    put_resp.raise_for_status = unittest.mock.MagicMock()
    client.put.return_value = put_resp
    return client


def _make_git_repo(tmp_dir: str, remote_url: str) -> Path:
    cwd = Path(tmp_dir)
    subprocess.run(["git", "init"], cwd=cwd, capture_output=True, check=True)
    subprocess.run(
        ["git", "remote", "add", "origin", remote_url],
        cwd=cwd, capture_output=True, check=True,
    )
    return cwd


class TestDeriveProjectIdFromRemote(unittest.TestCase):
    def test_github_https_url_produces_org_repo_slug(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd = _make_git_repo(tmp, "https://github.com/raelli/octowiz.git")
            result = derive_project_id(cwd)
        self.assertEqual(result, "raelli-octowiz")


class TestSeedProjectNamespaceBothAbsent(unittest.TestCase):
    def test_writes_config_and_rules_when_both_absent(self):
        client = _mock_client(get_status=404)
        seed_project_namespace("raelli-octowiz", client)

        put_urls = [call.args[0] for call in client.put.call_args_list]
        self.assertEqual(len(put_urls), 2)
        self.assertTrue(any("config" in u for u in put_urls))
        self.assertTrue(any("rules" in u for u in put_urls))

    def test_config_value_contains_namespace_and_created_at(self):
        client = _mock_client(get_status=404)
        seed_project_namespace("raelli-octowiz", client)

        config_call = next(
            c for c in client.put.call_args_list if "config" in c.args[0]
        )
        body = config_call.kwargs["json"]
        value = json.loads(body["value"])
        self.assertIn("namespace", value)
        self.assertIn("created_at", value)

    def test_rules_written_as_empty_list(self):
        client = _mock_client(get_status=404)
        seed_project_namespace("raelli-octowiz", client)

        rules_call = next(
            c for c in client.put.call_args_list if "rules" in c.args[0]
        )
        body = rules_call.kwargs["json"]
        value = json.loads(body["value"])
        self.assertEqual(value, [])


class TestSeedProjectNamespaceRulesPreserved(unittest.TestCase):
    def test_nonempty_rules_are_not_overwritten(self):
        existing_rules = json.dumps([{"rule": "no merges on Friday"}])
        client = _mock_client(get_status=200, rules_value=existing_rules)
        seed_project_namespace("raelli-octowiz", client)

        put_urls = [call.args[0] for call in client.put.call_args_list]
        self.assertFalse(any("rules" in u for u in put_urls))

    def test_config_still_skipped_when_already_present(self):
        client = _mock_client(get_status=200)
        seed_project_namespace("raelli-octowiz", client)

        self.assertEqual(client.put.call_count, 0)


class TestCmdSeedLiteLLMUnreachable(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self.tmp.name)
        subprocess.run(["git", "init"], cwd=self.cwd, capture_output=True, check=True)
        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/raelli/octowiz.git"],
            cwd=self.cwd, capture_output=True, check=True,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def _fake_args(self):
        cwd = str(self.cwd)

        class FakeArgs:
            pass

        a = FakeArgs()
        a.cwd = cwd
        a.project = None
        a.namespace = "allspark"
        a.cache_dir = None
        a.ttl_seconds = None
        return a

    def test_exits_1_when_litellm_unreachable(self):
        import httpx
        import unittest.mock
        from packages.memory_client.cli import cmd_seed
        from packages.memory_client import cache as octowiz_cache

        with unittest.mock.patch.object(octowiz_cache, "get_litellm_client",
                                        return_value=unittest.mock.MagicMock()), \
             unittest.mock.patch("packages.memory_client.env.seed_project_namespace",
                                 side_effect=httpx.ConnectError("refused")):
            result = cmd_seed(self._fake_args())

        self.assertEqual(result, 1)

    def test_setup_state_not_written_when_litellm_unreachable(self):
        import httpx
        import unittest.mock
        from packages.memory_client.cli import cmd_seed
        from packages.memory_client import cache as octowiz_cache

        setup_state_path = self.cwd / ".octowiz" / "setup-state.json"
        self.assertFalse(setup_state_path.exists())

        with unittest.mock.patch.object(octowiz_cache, "get_litellm_client",
                                        return_value=unittest.mock.MagicMock()), \
             unittest.mock.patch("packages.memory_client.env.seed_project_namespace",
                                 side_effect=httpx.ConnectError("refused")):
            cmd_seed(self._fake_args())

        self.assertFalse(setup_state_path.exists())


class TestCmdSeedReusesStoredProjectId(unittest.TestCase):
    """Regression: cmd_seed must not generate a new UUID on every call for repos without a remote."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self.tmp.name)
        subprocess.run(["git", "init"], cwd=self.cwd, capture_output=True, check=True)
        # No remote — derive_project_id would return a new UUID each time

    def tearDown(self):
        self.tmp.cleanup()

    def _fake_args(self):
        class FakeArgs:
            pass
        a = FakeArgs()
        a.cwd = str(self.cwd)
        a.project = None
        a.namespace = "allspark"
        a.cache_dir = None
        a.ttl_seconds = None
        return a

    def test_second_seed_reuses_project_id_from_state_file(self):
        from packages.memory_client import cache as octowiz_cache
        from packages.memory_client.cli import cmd_seed
        from packages.memory_client.env import load_repo_state

        with unittest.mock.patch.object(octowiz_cache, "get_litellm_client",
                                        return_value=_mock_client(get_status=404)), \
             unittest.mock.patch("packages.memory_client.env.seed_project_namespace"):
            cmd_seed(self._fake_args())
            state_after_first = load_repo_state(self.cwd)

        with unittest.mock.patch.object(octowiz_cache, "get_litellm_client",
                                        return_value=_mock_client(get_status=404)), \
             unittest.mock.patch("packages.memory_client.env.seed_project_namespace"):
            cmd_seed(self._fake_args())
            state_after_second = load_repo_state(self.cwd)

        self.assertEqual(state_after_first.project_id, state_after_second.project_id)


class TestSeedExistsOnlyTreats404AsAbsent(unittest.TestCase):
    """Regression: _exists() must raise on non-200/non-404 instead of silently treating as absent."""

    def test_server_error_on_config_read_raises_not_writes(self):
        client = unittest.mock.MagicMock()
        resp_500 = unittest.mock.MagicMock()
        resp_500.status_code = 500
        resp_500.raise_for_status.side_effect = Exception("server error")
        client.get.return_value = resp_500

        with self.assertRaises(Exception):
            seed_project_namespace("raelli-octowiz", client)

        self.assertEqual(client.put.call_count, 0)


class TestDeriveProjectIdFallback(unittest.TestCase):
    def test_no_git_remote_returns_nonempty_string(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            subprocess.run(["git", "init"], cwd=cwd, capture_output=True, check=True)
            # No remote added
            result = derive_project_id(cwd)
        self.assertTrue(len(result) > 0)

    def test_no_git_remote_results_differ_each_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            subprocess.run(["git", "init"], cwd=cwd, capture_output=True, check=True)
            r1 = derive_project_id(cwd)
            r2 = derive_project_id(cwd)
        self.assertNotEqual(r1, r2)
