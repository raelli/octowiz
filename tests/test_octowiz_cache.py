import hashlib
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

import octowiz_cache
import octowiz_cache as _module
from octowiz_cache import (
    BuildResult,
    RoleStatus,
    build_bundles,
    cache_status,
    fetch_memory,
    get_bundle,
    get_litellm_client,
    hash_bundle,
    hash_memory,
    manifest_is_fresh,
    render_bundle,
)


# ---------------------------------------------------------------------------
# hash_memory
# ---------------------------------------------------------------------------


class TestHashMemory(unittest.TestCase):
    def _make_memory(self, key="team:allspark:playbook:overview", value="doc content"):
        return {"key": key, "value": value, "metadata": {}}

    def test_same_content_same_hash(self):
        m = self._make_memory()
        self.assertEqual(hash_memory(m), hash_memory(m))

    def test_changed_value_changes_hash(self):
        m1 = self._make_memory(value="original")
        m2 = self._make_memory(value="changed")
        self.assertNotEqual(hash_memory(m1), hash_memory(m2))

    def test_hash_is_hex_string(self):
        m = self._make_memory()
        h = hash_memory(m)
        # SHA-256 hex = 64 chars
        self.assertEqual(len(h), 64)
        int(h, 16)  # must be valid hex

    def test_changed_key_changes_hash(self):
        m1 = self._make_memory(key="team:allspark:a")
        m2 = self._make_memory(key="team:allspark:b")
        self.assertNotEqual(hash_memory(m1), hash_memory(m2))


# ---------------------------------------------------------------------------
# hash_bundle
# ---------------------------------------------------------------------------


class TestHashBundle(unittest.TestCase):
    def _memories(self):
        return [
            {"key": "team:allspark:playbook:overview", "value": "doc1", "metadata": {}},
            {"key": "team:allspark:skills:hub", "value": "doc2", "metadata": {}},
        ]

    def test_same_memories_same_bundle_hash(self):
        mems = self._memories()
        self.assertEqual(hash_bundle("planner", mems), hash_bundle("planner", mems))

    def test_changed_memory_changes_bundle_hash(self):
        mems1 = self._memories()
        mems2 = [
            {"key": "team:allspark:playbook:overview", "value": "CHANGED", "metadata": {}},
            {"key": "team:allspark:skills:hub", "value": "doc2", "metadata": {}},
        ]
        self.assertNotEqual(hash_bundle("planner", mems1), hash_bundle("planner", mems2))

    def test_different_role_changes_bundle_hash(self):
        mems = self._memories()
        self.assertNotEqual(hash_bundle("planner", mems), hash_bundle("reviewer", mems))


# ---------------------------------------------------------------------------
# render_bundle
# ---------------------------------------------------------------------------


class TestRenderBundle(unittest.TestCase):
    def _memories(self):
        return [
            {"key": "team:allspark:skills:hub", "value": "skill content", "metadata": {}},
            {"key": "team:allspark:playbook:overview", "value": "overview content", "metadata": {}},
        ]

    def test_rendering_is_deterministic(self):
        mems = self._memories()
        self.assertEqual(render_bundle("planner", mems), render_bundle("planner", mems))

    def test_memories_sorted_by_key(self):
        mems = self._memories()
        result = render_bundle("planner", mems)
        # overview comes before skills alphabetically
        overview_pos = result.index("team:allspark:playbook:overview")
        skills_pos = result.index("team:allspark:skills:hub")
        self.assertLess(overview_pos, skills_pos)

    def test_value_passed_through_as_is(self):
        # JSON-ish value should NOT be reformatted
        raw_value = '{"key":"value","list":[1,2,3]}'
        mems = [{"key": "team:allspark:config:retrieval-contract", "value": raw_value, "metadata": {}}]
        result = render_bundle("routing", mems)
        self.assertIn(raw_value, result)

    def test_never_contains_dynamic_context_markers(self):
        mems = self._memories()
        result = render_bundle("planner", mems)
        for forbidden in ("git status", "git diff", "test output", "user request"):
            self.assertNotIn(forbidden, result)

    def test_header_contains_role(self):
        mems = self._memories()
        result = render_bundle("planner", mems)
        self.assertIn("# Octowiz Doctrine Bundle: planner", result)

    def test_ends_with_newline(self):
        mems = self._memories()
        result = render_bundle("planner", mems)
        self.assertTrue(result.endswith("\n"))


# ---------------------------------------------------------------------------
# manifest_is_fresh
# ---------------------------------------------------------------------------


class TestManifestIsFresh(unittest.TestCase):
    def test_fresh_manifest_returns_true(self):
        manifest = {"updated_at": time.time() - 60, "ttl_seconds": 3600}
        self.assertTrue(manifest_is_fresh(manifest, ttl_seconds=3600))

    def test_expired_manifest_returns_false(self):
        manifest = {"updated_at": time.time() - 7200, "ttl_seconds": 3600}
        self.assertFalse(manifest_is_fresh(manifest, ttl_seconds=3600))

    def test_exactly_at_boundary_is_expired(self):
        # updated_at exactly ttl_seconds ago → NOT fresh
        manifest = {"updated_at": time.time() - 3600, "ttl_seconds": 3600}
        self.assertFalse(manifest_is_fresh(manifest, ttl_seconds=3600))


# ---------------------------------------------------------------------------
# get_litellm_client
# ---------------------------------------------------------------------------


class TestGetLitellmClient(unittest.TestCase):
    def test_no_api_key_raises_runtime_error(self):
        # clear=True ensures no leaked env vars
        with patch.dict(
            os.environ,
            {},
            clear=True,
        ):
            # Only LITELLM_BASE_URL could be set, but no key
            with self.assertRaises(RuntimeError) as ctx:
                get_litellm_client()
        self.assertIn("LITELLM_ADMIN_API_KEY", str(ctx.exception))

    def test_admin_key_used_when_set(self):
        env = {
            "LITELLM_ADMIN_API_KEY": "sk-admin-123",
            "LITELLM_BASE_URL": "http://localhost:4000",
        }
        with patch.dict(os.environ, env, clear=True):
            with patch("httpx.Client") as mock_client_cls:
                get_litellm_client()
                mock_client_cls.assert_called_once()
                call_kwargs = mock_client_cls.call_args.kwargs
                self.assertEqual(
                    call_kwargs["headers"]["Authorization"],
                    "Bearer sk-admin-123",
                )

    def test_api_key_fallback_when_no_admin_key(self):
        env = {
            "LITELLM_API_KEY": "sk-fallback",
            "LITELLM_BASE_URL": "http://localhost:4000",
        }
        with patch.dict(os.environ, env, clear=True):
            with patch("httpx.Client") as mock_client_cls:
                get_litellm_client()
                mock_client_cls.assert_called_once()
                call_kwargs = mock_client_cls.call_args.kwargs
                self.assertEqual(
                    call_kwargs["headers"]["Authorization"],
                    "Bearer sk-fallback",
                )


# ---------------------------------------------------------------------------
# fetch_memory
# ---------------------------------------------------------------------------


class TestFetchMemory(unittest.TestCase):
    def _make_client(self, response_data=None, status_code=200):
        mock_response = MagicMock()
        mock_response.status_code = status_code
        if response_data is not None:
            mock_response.json.return_value = response_data
        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        return mock_client

    def test_successful_fetch_returns_dict(self):
        data = {"key": "team:allspark:playbook:overview", "value": "doc content", "metadata": {}}
        client = self._make_client(response_data=data, status_code=200)
        result = fetch_memory(client, "team:allspark:playbook:overview")
        self.assertEqual(result["key"], "team:allspark:playbook:overview")
        self.assertEqual(result["value"], "doc content")

    def test_404_raises_with_key_name(self):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_client = MagicMock()
        mock_client.get.return_value = mock_response

        with self.assertRaises(KeyError) as ctx:
            fetch_memory(mock_client, "team:allspark:missing:key")
        self.assertIn("team:allspark:missing:key", str(ctx.exception))

    def test_url_encodes_colons(self):
        data = {"key": "team:allspark:playbook:overview", "value": "v", "metadata": {}}
        client = self._make_client(response_data=data, status_code=200)
        fetch_memory(client, "team:allspark:playbook:overview")
        called_url = client.get.call_args[0][0]
        self.assertIn("%3A", called_url)

    def test_memory_key_in_response(self):
        data = {"key": "team:allspark:playbook:overview", "value": "some value", "metadata": {"source": "test"}}
        client = self._make_client(response_data=data, status_code=200)
        result = fetch_memory(client, "team:allspark:playbook:overview")
        self.assertIn("key", result)
        self.assertIn("value", result)


# ---------------------------------------------------------------------------
# get_bundle integration
# ---------------------------------------------------------------------------


class TestGetBundle(unittest.TestCase):
    def _mock_memories(self, role="planner", namespace="allspark"):
        """Return minimal fake memories matching the role's keys."""
        from octowiz_cache import ROLE_MEMORY_KEYS

        keys = [k.replace("{namespace}", namespace) for k in ROLE_MEMORY_KEYS[role]]
        return [{"key": k, "value": f"content for {k}", "metadata": {}} for k in keys]

    def _make_mock_client(self, role="planner", namespace="allspark"):
        memories = self._mock_memories(role, namespace)
        mem_by_key = {m["key"]: m for m in memories}

        def fake_get(url, **kwargs):
            # decode key from URL
            import urllib.parse

            # URL like http://localhost:4000/v1/memory/team%3A...
            encoded_key = url.split("/v1/memory/")[-1]
            key = urllib.parse.unquote(encoded_key)
            mock_resp = MagicMock()
            if key in mem_by_key:
                mock_resp.status_code = 200
                mock_resp.json.return_value = mem_by_key[key]
            else:
                mock_resp.status_code = 404
            return mock_resp

        mock_client = MagicMock()
        mock_client.get.side_effect = fake_get
        return mock_client

    def test_get_bundle_returns_string(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_client = self._make_mock_client()
            with patch("octowiz_cache.get_litellm_client", return_value=mock_client):
                result = get_bundle("planner", "allspark", cache_dir=tmpdir)
            self.assertIsInstance(result, str)
            self.assertIn("Octowiz Doctrine Bundle", result)

    def test_refresh_flag_triggers_fetch(self):
        """refresh=True must call fetch_role_memories even when a valid cache exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_client = self._make_mock_client()

            with patch("octowiz_cache.get_litellm_client", return_value=mock_client):
                # Populate cache
                get_bundle("planner", "allspark", cache_dir=tmpdir)
                fetch_count_after_first = mock_client.get.call_count

                # Second call without refresh — should NOT fetch
                get_bundle("planner", "allspark", cache_dir=tmpdir)
                fetch_count_after_cache_hit = mock_client.get.call_count
                self.assertEqual(fetch_count_after_first, fetch_count_after_cache_hit)

                # Third call WITH refresh — must fetch again
                get_bundle("planner", "allspark", cache_dir=tmpdir, refresh=True)
                fetch_count_after_refresh = mock_client.get.call_count
                self.assertGreater(fetch_count_after_refresh, fetch_count_after_cache_hit)

    def test_stale_cache_serves_bundle_on_litellm_failure(self):
        """If TTL expired and LiteLLM is unavailable, serve stale bundle with stderr warning."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_client = self._make_mock_client()

            with patch("octowiz_cache.get_litellm_client", return_value=mock_client):
                # Populate cache
                first_result = get_bundle("planner", "allspark", cache_dir=tmpdir)

            # Now simulate LiteLLM failure and expired TTL
            failing_client = MagicMock()
            failing_client.get.side_effect = Exception("LiteLLM down")

            import io

            with patch("octowiz_cache.get_litellm_client", return_value=failing_client):
                with patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
                    result = get_bundle(
                        "planner",
                        "allspark",
                        cache_dir=tmpdir,
                        ttl_seconds=0,  # immediately expired
                        refresh=True,
                    )
                    warning = mock_stderr.getvalue()

            self.assertEqual(result, first_result)
            self.assertTrue(len(warning) > 0, "Expected a warning on stderr")

    def test_cache_dir_from_env(self):
        """OCTOWIZ_CACHE_DIR env var is used when cache_dir param is None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_client = self._make_mock_client()
            with patch("octowiz_cache.get_litellm_client", return_value=mock_client):
                with patch.dict(os.environ, {"OCTOWIZ_CACHE_DIR": tmpdir}):
                    result = get_bundle("planner", "allspark", cache_dir=None)
            self.assertIn("Octowiz Doctrine Bundle", result)


# ---------------------------------------------------------------------------
# manifest read/write and bundle atomic write
# ---------------------------------------------------------------------------


class TestManifestReadWrite(unittest.TestCase):
    def test_write_and_read_manifest_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ns_dir = Path(tmpdir) / "namespaces" / "allspark"
            manifest = {
                "namespace": "allspark",
                "updated_at": 1760000000.0,
                "ttl_seconds": 3600,
                "roles": {
                    "planner": {
                        "bundle_hash": "abc123",
                        "bundle_path": "bundles/planner/abc123.md",
                        "updated_at": 1760000000.0,
                        "memory_hashes": {"team:allspark:playbook:overview": "def456"},
                    }
                },
            }
            _module._write_manifest(ns_dir, manifest)
            result = _module._read_manifest(ns_dir)
            self.assertEqual(result["namespace"], "allspark")
            self.assertIn("planner", result["roles"])
            self.assertEqual(result["roles"]["planner"]["bundle_hash"], "abc123")

    def test_read_missing_manifest_returns_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ns_dir = Path(tmpdir) / "namespaces" / "allspark"
            result = _module._read_manifest(ns_dir)
        self.assertIsNone(result)

    def test_write_bundle_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ns_dir = Path(tmpdir) / "namespaces" / "allspark"
            path = _module._write_bundle(ns_dir, "planner", "abc123", "# Doctrine\n")
            self.assertTrue(path.exists())
            self.assertEqual(path.read_text(encoding="utf-8"), "# Doctrine\n")

    def test_write_bundle_atomic_no_tmp_left_behind(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ns_dir = Path(tmpdir) / "namespaces" / "allspark"
            _module._write_bundle(ns_dir, "planner", "abc123", "# Doctrine\n")
            tmp_files = list((ns_dir / "bundles" / "planner").glob("*.tmp"))
        self.assertEqual(tmp_files, [], "No .tmp files should remain after atomic write")

    def test_read_bundle_returns_none_when_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ns_dir = Path(tmpdir) / "namespaces" / "allspark"
            result = _module._read_bundle(ns_dir, "planner", "nonexistent_hash")
        self.assertIsNone(result)


class TestRoleValidation(unittest.TestCase):
    def test_get_bundle_raises_value_error_for_unknown_role(self):
        with self.assertRaises(ValueError) as ctx:
            octowiz_cache.get_bundle(
                role="nonexistent",
                namespace="allspark",
                cache_dir="/tmp/octowiz-test-unused",
            )
        self.assertIn("nonexistent", str(ctx.exception))
        self.assertIn("planner", str(ctx.exception))

    def test_fetch_role_memories_raises_value_error_for_unknown_role(self):
        mock_client = MagicMock()
        with self.assertRaises(ValueError) as ctx:
            octowiz_cache.fetch_role_memories(mock_client, "ghost", "allspark")
        self.assertIn("ghost", str(ctx.exception))
        mock_client.get.assert_not_called()


class TestManifestDefensive(unittest.TestCase):
    def test_manifest_is_fresh_handles_missing_updated_at(self):
        manifest = {"roles": {}}
        result = octowiz_cache.manifest_is_fresh(manifest, ttl_seconds=3600)
        self.assertFalse(result)

    def test_manifest_is_fresh_handles_none_updated_at(self):
        manifest = {"updated_at": None}
        result = octowiz_cache.manifest_is_fresh(manifest, ttl_seconds=3600)
        self.assertFalse(result)

    def test_manifest_is_fresh_handles_non_numeric_updated_at(self):
        manifest = {"updated_at": "2024-01-01"}
        result = octowiz_cache.manifest_is_fresh(manifest, ttl_seconds=3600)
        self.assertFalse(result)


class TestCacheSchemaVersion(unittest.TestCase):
    def test_schema_version_constant_is_integer(self):
        self.assertIsInstance(octowiz_cache.CACHE_SCHEMA_VERSION, int)
        self.assertGreater(octowiz_cache.CACHE_SCHEMA_VERSION, 0)

    def test_written_manifest_contains_schema_version(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from pathlib import Path
            ns_dir = Path(tmpdir) / "namespaces" / "allspark"
            manifest = {"namespace": "allspark", "updated_at": time.time(), "roles": {}}
            octowiz_cache._write_manifest(ns_dir, manifest)
            result = octowiz_cache._read_manifest(ns_dir)
            self.assertIn("schema_version", result)
            self.assertEqual(result["schema_version"], octowiz_cache.CACHE_SCHEMA_VERSION)

    def test_stale_schema_version_triggers_rebuild(self):
        memory = {"key": "team:allspark:config:retrieval-contract", "value": "v1", "metadata": {}}
        with tempfile.TemporaryDirectory() as tmpdir:
            from pathlib import Path
            ns_dir = Path(tmpdir) / "namespaces" / "allspark"
            old_manifest = {
                "namespace": "allspark",
                "updated_at": time.time(),
                "schema_version": 99999,
                "roles": {
                    "routing": {
                        "bundle_hash": "oldhash",
                        "bundle_path": "bundles/routing/oldhash.md",
                        "updated_at": time.time(),
                        "memory_hashes": {},
                    }
                },
            }
            ns_dir.mkdir(parents=True, exist_ok=True)
            (ns_dir / "manifest.json").write_text(json.dumps(old_manifest, indent=2), encoding="utf-8")
            octowiz_cache._write_bundle(ns_dir, "routing", "oldhash", "# old bundle\n")

            with patch("octowiz_cache.fetch_role_memories", return_value=[memory]) as mock_fetch:
                with patch("octowiz_cache.get_litellm_client", return_value=MagicMock()):
                    octowiz_cache.get_bundle(
                        role="routing",
                        namespace="allspark",
                        cache_dir=tmpdir,
                        ttl_seconds=3600,
                        refresh=False,
                    )
            mock_fetch.assert_called_once()


class TestRoutingRoleConfigNamespace(unittest.TestCase):
    def test_routing_config_key_uses_team_namespace(self):
        routing_keys = octowiz_cache.ROLE_MEMORY_KEYS["routing"]
        config_keys = [k for k in routing_keys if "config:retrieval-contract" in k]
        self.assertEqual(len(config_keys), 1, "routing role must have exactly one config:retrieval-contract key")
        self.assertTrue(
            config_keys[0].startswith("team:"),
            f"routing config key must use team:{{namespace}}: prefix, got {config_keys[0]!r}",
        )


# ---------------------------------------------------------------------------
# cache_status()
# ---------------------------------------------------------------------------


class TestCacheStatus(unittest.TestCase):
    def test_empty_cache_all_roles_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            statuses = cache_status(namespace="allspark", cache_dir=tmpdir)
        for s in statuses:
            self.assertIsInstance(s, RoleStatus)
            self.assertFalse(s.is_fresh)
            self.assertIsNone(s.age_seconds)

    def test_returns_one_status_per_role(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            statuses = cache_status(namespace="allspark", cache_dir=tmpdir)
        role_names = [s.role for s in statuses]
        self.assertEqual(sorted(role_names), sorted(octowiz_cache.ROLE_MEMORY_KEYS.keys()))

    def test_fresh_cache_entry_is_fresh(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ns_dir = Path(tmpdir) / "namespaces" / "allspark"
            now = time.time()
            manifest = {
                "namespace": "allspark",
                "updated_at": now,
                "roles": {
                    "planner": {
                        "bundle_hash": "abc",
                        "bundle_path": "bundles/planner/abc.md",
                        "updated_at": now - 60,  # 1 minute ago
                        "memory_hashes": {},
                    }
                },
            }
            _module._write_manifest(ns_dir, manifest)
            statuses = cache_status(namespace="allspark", cache_dir=tmpdir, ttl_seconds=3600)
        planner = next(s for s in statuses if s.role == "planner")
        self.assertTrue(planner.is_fresh)
        self.assertIsNotNone(planner.age_seconds)
        self.assertGreater(planner.age_seconds, 0)
        self.assertLess(planner.age_seconds, 300)

    def test_stale_cache_entry_is_not_fresh(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ns_dir = Path(tmpdir) / "namespaces" / "allspark"
            old_time = time.time() - 7200  # 2 hours ago
            manifest = {
                "namespace": "allspark",
                "updated_at": old_time,
                "roles": {
                    "reviewer": {
                        "bundle_hash": "xyz",
                        "bundle_path": "bundles/reviewer/xyz.md",
                        "updated_at": old_time,
                        "memory_hashes": {},
                    }
                },
            }
            _module._write_manifest(ns_dir, manifest)
            statuses = cache_status(namespace="allspark", cache_dir=tmpdir, ttl_seconds=3600)
        reviewer = next(s for s in statuses if s.role == "reviewer")
        self.assertFalse(reviewer.is_fresh)
        self.assertIsNotNone(reviewer.age_seconds)
        self.assertGreater(reviewer.age_seconds, 3600)


# ---------------------------------------------------------------------------
# build_bundles()
# ---------------------------------------------------------------------------


class TestBuildBundles(unittest.TestCase):
    def _mock_memories(self, role, namespace="allspark"):
        keys = [k.replace("{namespace}", namespace) for k in octowiz_cache.ROLE_MEMORY_KEYS[role]]
        return [{"key": k, "value": f"content for {k}", "metadata": {}} for k in keys]

    def _patch_get_bundle_success(self, roles_to_succeed):
        """Return a mock that succeeds for given roles."""
        def fake_get_bundle(role, namespace, cache_dir, ttl_seconds, refresh):
            if role in roles_to_succeed:
                return f"# Bundle for {role}\n"
            raise RuntimeError(f"Simulated failure for {role}")
        return fake_get_bundle

    def test_all_roles_succeed(self):
        roles = list(octowiz_cache.ROLE_MEMORY_KEYS.keys())
        with patch("octowiz_cache.get_bundle") as mock_gb:
            mock_gb.return_value = "# Bundle content\n"
            result = build_bundles(roles=roles, namespace="allspark",
                                   cache_dir="/tmp/test", ttl_seconds=3600, refresh=False)
        self.assertEqual(result.failed, [])
        self.assertEqual(sorted(result.built), sorted(roles))

    def test_one_role_fails(self):
        roles = list(octowiz_cache.ROLE_MEMORY_KEYS.keys())
        failing_role = roles[0]

        def side_effect(role, namespace, cache_dir, ttl_seconds, refresh):
            if role == failing_role:
                raise RuntimeError("fetch error")
            return f"# Bundle for {role}\n"

        with patch("octowiz_cache.get_bundle", side_effect=side_effect):
            result = build_bundles(roles=roles, namespace="allspark",
                                   cache_dir="/tmp/test", ttl_seconds=3600, refresh=False)

        self.assertEqual(len(result.failed), 1)
        failed_role, err_msg = result.failed[0]
        self.assertEqual(failed_role, failing_role)
        self.assertIn("fetch error", err_msg)
        self.assertNotIn(failing_role, result.built)
        # All other roles should be in built
        for role in roles:
            if role != failing_role:
                self.assertIn(role, result.built)

    def test_refresh_true_passed_to_get_bundle(self):
        roles = list(octowiz_cache.ROLE_MEMORY_KEYS.keys())
        with patch("octowiz_cache.get_bundle") as mock_gb:
            mock_gb.return_value = "# Bundle content\n"
            build_bundles(roles=roles, namespace="allspark",
                          cache_dir="/tmp/test", ttl_seconds=3600, refresh=True)
        for call in mock_gb.call_args_list:
            self.assertEqual(call.kwargs["refresh"], True)


if __name__ == "__main__":
    unittest.main()
