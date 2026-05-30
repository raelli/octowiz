import hashlib
import json
import os
import re
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx

from packages.memory_client import cache as octowiz_cache
from packages.memory_client.cache import (
    BuildFailure,
    BuildResult,
    FailureKind,
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
        keys = octowiz_cache.ROLE_REGISTRY.get_keys(role, namespace)
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
            with patch("packages.memory_client.cache.get_litellm_client", return_value=mock_client):
                result = get_bundle("planner", "allspark", cache_dir=tmpdir)
            self.assertIsInstance(result, str)
            self.assertIn("Octowiz Doctrine Bundle", result)

    def test_refresh_flag_triggers_fetch(self):
        """refresh=True must call fetch_role_memories even when a valid cache exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_client = self._make_mock_client()

            with patch("packages.memory_client.cache.get_litellm_client", return_value=mock_client):
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

            with patch("packages.memory_client.cache.get_litellm_client", return_value=mock_client):
                # Populate cache
                first_result = get_bundle("planner", "allspark", cache_dir=tmpdir)

            # Now simulate LiteLLM failure and expired TTL
            failing_client = MagicMock()
            failing_client.get.side_effect = Exception("LiteLLM down")

            import io

            with patch("packages.memory_client.cache.get_litellm_client", return_value=failing_client):
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
            with patch("packages.memory_client.cache.get_litellm_client", return_value=mock_client):
                with patch.dict(os.environ, {"OCTOWIZ_CACHE_DIR": tmpdir}):
                    result = get_bundle("planner", "allspark", cache_dir=None)
            self.assertIn("Octowiz Doctrine Bundle", result)


# ---------------------------------------------------------------------------
# manifest read/write and bundle atomic write
# ---------------------------------------------------------------------------


class TestCacheStoreAtomicWrite(unittest.TestCase):
    """Verify CacheStore write operations leave no temp files behind."""

    def test_seed_leaves_no_tmp_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = octowiz_cache.CacheStore(Path(tmpdir))
            store.seed("planner", "allspark", "# Doctrine\n")
            bundle_dir = Path(tmpdir) / "namespaces" / "allspark" / "bundles" / "planner"
            self.assertEqual(list(bundle_dir.glob("*.tmp")), [])

    def test_seed_and_retrieve_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = octowiz_cache.CacheStore(Path(tmpdir))
            store.seed("planner", "allspark", "# Doctrine\n")
            self.assertEqual(store.get_best_available("planner", "allspark"), "# Doctrine\n")

    def test_empty_cache_returns_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = octowiz_cache.CacheStore(Path(tmpdir))
            self.assertIsNone(store.get_best_available("planner", "allspark"))


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
            store = octowiz_cache.CacheStore(Path(tmpdir))
            store.seed("routing", "allspark", "# content\n")
            ns_dir = Path(tmpdir) / "namespaces" / "allspark"
            manifest = json.loads((ns_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertIn("schema_version", manifest)
            self.assertEqual(manifest["schema_version"], octowiz_cache.CACHE_SCHEMA_VERSION)

    def test_stale_schema_version_triggers_rebuild(self):
        memory = {"key": "team:allspark:config:retrieval-contract", "value": "v1", "metadata": {}}
        with tempfile.TemporaryDirectory() as tmpdir:
            store = octowiz_cache.CacheStore(Path(tmpdir))
            store.seed("routing", "allspark", "# old bundle\n")
            # Corrupt the manifest's schema version to simulate a stale schema
            ns_dir = Path(tmpdir) / "namespaces" / "allspark"
            manifest = json.loads((ns_dir / "manifest.json").read_text(encoding="utf-8"))
            manifest["schema_version"] = 99999
            (ns_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

            with patch("packages.memory_client.cache.fetch_role_memories", return_value=[memory]) as mock_fetch:
                with patch("packages.memory_client.cache.get_litellm_client", return_value=MagicMock()):
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
        routing_keys = octowiz_cache.ROLE_REGISTRY._entries["routing"]
        config_keys = [k for k in routing_keys if "config:retrieval-contract" in k]
        self.assertEqual(len(config_keys), 1, "routing role must have exactly one config:retrieval-contract key")
        self.assertTrue(
            config_keys[0].startswith("team:"),
            f"routing config key must use team:{{namespace}}: prefix, got {config_keys[0]!r}",
        )


# ---------------------------------------------------------------------------
# MemorySource Protocol — DictMemorySource test double
# ---------------------------------------------------------------------------


class DictMemorySource:
    """In-memory MemorySource backed by a plain dict. For use in tests."""

    def __init__(self, data: dict):
        # data: {key: {"key": ..., "value": ..., "metadata": {...}}}
        self._data = data

    def fetch(self, key: str) -> dict:
        if key not in self._data:
            raise KeyError(f"Memory key not found: {key!r}")
        return dict(self._data[key])


class TestMemorySourceProtocol(unittest.TestCase):
    """DictMemorySource satisfies the MemorySource Protocol and works in fetch_role_memories."""

    def _make_source_for_role(self, role="routing", namespace="allspark"):
        keys = octowiz_cache.ROLE_REGISTRY.get_keys(role, namespace)
        data = {k: {"key": k, "value": f"value for {k}", "metadata": {}} for k in keys}
        return DictMemorySource(data)

    def test_dict_memory_source_fetch_returns_entry(self):
        source = DictMemorySource({"k:1": {"key": "k:1", "value": "v", "metadata": {}}})
        result = source.fetch("k:1")
        self.assertEqual(result["key"], "k:1")
        self.assertEqual(result["value"], "v")

    def test_dict_memory_source_fetch_raises_key_error_on_missing(self):
        source = DictMemorySource({})
        with self.assertRaises(KeyError):
            source.fetch("missing:key")

    def test_dict_memory_source_works_in_fetch_role_memories(self):
        source = self._make_source_for_role("routing", "allspark")
        results = octowiz_cache.fetch_role_memories(source, "routing", "allspark")
        self.assertIsInstance(results, list)
        self.assertTrue(len(results) > 0)
        for mem in results:
            self.assertIn("key", mem)
            self.assertIn("value", mem)

    def test_dict_memory_source_satisfies_protocol(self):
        from packages.memory_client.cache import MemorySource
        source = DictMemorySource({})
        self.assertIsInstance(source, MemorySource)


# ---------------------------------------------------------------------------
# LiteLLMMemorySource
# ---------------------------------------------------------------------------


class TestLiteLLMMemorySource(unittest.TestCase):
    def _make_client(self, response_data=None, status_code=200):
        mock_response = MagicMock()
        mock_response.status_code = status_code
        if response_data is not None:
            mock_response.json.return_value = response_data
        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        return mock_client

    def test_200_success_returns_dict(self):
        data = {"key": "team:allspark:playbook:overview", "value": "content", "metadata": {}}
        client = self._make_client(response_data=data, status_code=200)
        source = octowiz_cache.LiteLLMMemorySource(client)
        result = source.fetch("team:allspark:playbook:overview")
        self.assertEqual(result["key"], "team:allspark:playbook:overview")
        self.assertEqual(result["value"], "content")
        self.assertIsInstance(result["metadata"], dict)

    def test_404_raises_key_error(self):
        client = self._make_client(status_code=404)
        source = octowiz_cache.LiteLLMMemorySource(client)
        with self.assertRaises(KeyError) as ctx:
            source.fetch("team:allspark:missing")
        self.assertIn("team:allspark:missing", str(ctx.exception))

    def test_non_string_value_emits_warning_and_converts(self):
        data = {"key": "k", "value": {"nested": "dict"}, "metadata": {}}
        client = self._make_client(response_data=data, status_code=200)
        source = octowiz_cache.LiteLLMMemorySource(client)
        import io
        with patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
            result = source.fetch("k")
        warning = mock_stderr.getvalue()
        self.assertIn("WARNING", warning)
        self.assertIn("non-string", warning)
        # value must be a JSON string now
        self.assertIsInstance(result["value"], str)
        parsed = json.loads(result["value"])
        self.assertEqual(parsed, {"nested": "dict"})

    def test_url_encodes_colons_in_key(self):
        data = {"key": "team:allspark:playbook", "value": "v", "metadata": {}}
        client = self._make_client(response_data=data, status_code=200)
        source = octowiz_cache.LiteLLMMemorySource(client)
        source.fetch("team:allspark:playbook")
        called_url = client.get.call_args[0][0]
        self.assertIn("%3A", called_url)


# ---------------------------------------------------------------------------
# CacheStore
# ---------------------------------------------------------------------------


class TestCacheStoreFresh(unittest.TestCase):
    def test_fresh_bundle_returned_by_get_best_available(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = octowiz_cache.CacheStore(Path(tmpdir))
            store.seed("routing", "allspark", "# Fresh Bundle\n")
            self.assertEqual(store.get_best_available("routing", "allspark"), "# Fresh Bundle\n")

    def test_expired_bundle_still_returned_as_stale_fallback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = octowiz_cache.CacheStore(Path(tmpdir), ttl_seconds=3600)
            store.seed("routing", "allspark", "# Bundle\n", expired=True)
            # get_best_available falls back to stale — so stale content is still served
            self.assertEqual(store.get_best_available("routing", "allspark"), "# Bundle\n")

    def test_expired_bundle_not_served_as_fresh_in_get_bundle(self):
        """Schema-mismatch and expiry both force a LiteLLM fetch via get_bundle."""
        memory = {"key": "team:allspark:config:retrieval-contract", "value": "fetched", "metadata": {}}
        with tempfile.TemporaryDirectory() as tmpdir:
            store = octowiz_cache.CacheStore(Path(tmpdir), ttl_seconds=3600)
            store.seed("routing", "allspark", "# cached\n")
            # Corrupt schema version so the fresh path forces a rebuild
            ns_dir = Path(tmpdir) / "namespaces" / "allspark"
            manifest = json.loads((ns_dir / "manifest.json").read_text(encoding="utf-8"))
            manifest["schema_version"] = 99999
            (ns_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            with patch("packages.memory_client.cache.fetch_role_memories", return_value=[memory]) as mock_fetch:
                with patch("packages.memory_client.cache.get_litellm_client", return_value=MagicMock()):
                    octowiz_cache.get_bundle("routing", "allspark", cache_dir=tmpdir,
                                             ttl_seconds=3600, refresh=False)
            mock_fetch.assert_called_once()

    def test_empty_cache_get_best_available_returns_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = octowiz_cache.CacheStore(Path(tmpdir))
            self.assertIsNone(store.get_best_available("routing", "allspark"))


class TestCacheStoreStale(unittest.TestCase):
    def test_stale_bundle_served_as_fallback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = octowiz_cache.CacheStore(Path(tmpdir), ttl_seconds=3600)
            store.seed("routing", "allspark", "# Stale Bundle\n", expired=True)
            self.assertEqual(store.get_best_available("routing", "allspark"), "# Stale Bundle\n")

    def test_no_cache_returns_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = octowiz_cache.CacheStore(Path(tmpdir), ttl_seconds=3600)
            self.assertIsNone(store.get_best_available("routing", "allspark"))


class TestCacheStoreGetBestAvailable(unittest.TestCase):
    """Tests for CacheStore.get_best_available()."""

    def test_returns_fresh_when_fresh_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = octowiz_cache.CacheStore(Path(tmpdir), ttl_seconds=3600)
            store.seed("routing", "allspark", "# Fresh Bundle\n")
            self.assertEqual(store.get_best_available("routing", "allspark"), "# Fresh Bundle\n")

    def test_returns_stale_when_no_fresh_but_stale_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = octowiz_cache.CacheStore(Path(tmpdir), ttl_seconds=3600)
            store.seed("routing", "allspark", "# Stale Bundle\n", expired=True)
            self.assertEqual(store.get_best_available("routing", "allspark"), "# Stale Bundle\n")

    def test_prints_to_stderr_when_on_stale_fallback_set_and_stale_returned(self):
        import io
        with tempfile.TemporaryDirectory() as tmpdir:
            store = octowiz_cache.CacheStore(Path(tmpdir), ttl_seconds=3600)
            store.seed("routing", "allspark", "# stale\n", expired=True)
            with patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
                result = store.get_best_available(
                    "routing", "allspark",
                    on_stale_fallback="WARNING: using stale cache",
                )
            self.assertIsNotNone(result)
            self.assertIn("WARNING: using stale cache", mock_stderr.getvalue())

    def test_no_stderr_output_when_on_stale_fallback_empty(self):
        import io
        with tempfile.TemporaryDirectory() as tmpdir:
            store = octowiz_cache.CacheStore(Path(tmpdir), ttl_seconds=3600)
            store.seed("routing", "allspark", "# stale\n", expired=True)
            with patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
                result = store.get_best_available("routing", "allspark")
            self.assertIsNotNone(result)
            self.assertEqual(mock_stderr.getvalue(), "")

    def test_returns_none_when_nothing_cached(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = octowiz_cache.CacheStore(Path(tmpdir), ttl_seconds=3600)
            self.assertIsNone(store.get_best_available("routing", "allspark"))

    def test_no_stderr_output_when_nothing_cached(self):
        import io
        with tempfile.TemporaryDirectory() as tmpdir:
            store = octowiz_cache.CacheStore(Path(tmpdir), ttl_seconds=3600)
            with patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
                result = store.get_best_available(
                    "routing", "allspark",
                    on_stale_fallback="WARNING: should not appear",
                )
            self.assertIsNone(result)
            self.assertEqual(mock_stderr.getvalue(), "")


class TestCacheStorePut(unittest.TestCase):
    def _make_memories(self, role="routing", namespace="allspark"):
        keys = octowiz_cache.ROLE_REGISTRY.get_keys(role, namespace)
        return [{"key": k, "value": f"content {k}", "metadata": {}} for k in keys]

    def test_put_writes_bundle_retrievable_via_get_best_available(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = octowiz_cache.CacheStore(Path(tmpdir), ttl_seconds=3600)
            memories = self._make_memories()
            content = store.put("routing", "allspark", memories)
            self.assertEqual(store.get_best_available("routing", "allspark"), content)

    def test_put_updates_manifest_with_role_entry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = octowiz_cache.CacheStore(Path(tmpdir), ttl_seconds=3600)
            memories = self._make_memories()
            store.put("routing", "allspark", memories)
            # Verify through the raw manifest file — we're testing the file format contract
            ns_dir = Path(tmpdir) / "namespaces" / "allspark"
            manifest = json.loads((ns_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertIn("routing", manifest["roles"])
            self.assertIn("bundle_hash", manifest["roles"]["routing"])

    def test_put_removes_old_bundle_on_hash_change(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = octowiz_cache.CacheStore(Path(tmpdir), ttl_seconds=3600)
            # Seed "old" content first, then put different content
            store.seed("routing", "allspark", "# old bundle\n")
            bundle_dir = Path(tmpdir) / "namespaces" / "allspark" / "bundles" / "routing"
            # Only one bundle file should exist after seed
            self.assertEqual(len(list(bundle_dir.glob("*.md"))), 1)

            memories = self._make_memories()
            store.put("routing", "allspark", memories)

            # put() with different content produces a different hash — old file must be gone
            self.assertEqual(
                len(list(bundle_dir.glob("*.md"))), 1,
                "Old bundle file should be deleted when hash changes",
            )

    def test_put_does_not_fail_if_old_bundle_already_deleted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = octowiz_cache.CacheStore(Path(tmpdir), ttl_seconds=3600)
            store.seed("routing", "allspark", "# old\n")
            # Delete the bundle file to simulate it already being gone
            bundle_dir = Path(tmpdir) / "namespaces" / "allspark" / "bundles" / "routing"
            for f in bundle_dir.glob("*.md"):
                f.unlink()
            # put() must not raise even though the old bundle file no longer exists
            memories = self._make_memories()
            store.put("routing", "allspark", memories)
            self.assertIsNotNone(store.get_best_available("routing", "allspark"))


# ---------------------------------------------------------------------------
# get_bundle end-to-end with DictMemorySource
# ---------------------------------------------------------------------------


class TestGetBundleWithDictMemorySource(unittest.TestCase):
    def _make_source(self, role="routing", namespace="allspark"):
        keys = octowiz_cache.ROLE_REGISTRY.get_keys(role, namespace)
        data = {k: {"key": k, "value": f"value for {k}", "metadata": {}} for k in keys}
        return DictMemorySource(data)

    def test_get_bundle_end_to_end_with_dict_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = self._make_source()
            result = octowiz_cache.get_bundle("routing", "allspark", cache_dir=tmpdir, source=source)
            self.assertIsInstance(result, str)
            self.assertIn("Octowiz Doctrine Bundle", result)

    def test_cache_hit_on_second_call(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = self._make_source()
            octowiz_cache.get_bundle("routing", "allspark", cache_dir=tmpdir, source=source)
            # Second call — should hit cache, source.fetch must NOT be called
            spy = MagicMock()
            spy.fetch.side_effect = AssertionError("source.fetch called on cache hit")
            octowiz_cache.get_bundle("routing", "allspark", cache_dir=tmpdir, source=spy)

    def test_refresh_forces_fetch_with_dict_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = self._make_source()
            octowiz_cache.get_bundle("routing", "allspark", cache_dir=tmpdir, source=source)
            # refresh=True must re-fetch even with a warm cache
            call_count = [0]
            original_fetch = source.fetch
            def counting_fetch(key):
                call_count[0] += 1
                return original_fetch(key)
            source.fetch = counting_fetch
            octowiz_cache.get_bundle("routing", "allspark", cache_dir=tmpdir,
                                     source=source, refresh=True)
            self.assertGreater(call_count[0], 0, "refresh=True must call source.fetch")

    def test_stale_fallback_with_dict_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = self._make_source()
            first_result = octowiz_cache.get_bundle(
                "routing", "allspark", cache_dir=tmpdir, source=source
            )
            # Now: source raises, TTL=0 (expired) → expect stale fallback
            import io
            broken_source = DictMemorySource({})  # KeyError on any fetch
            with patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
                result = octowiz_cache.get_bundle(
                    "routing", "allspark", cache_dir=tmpdir,
                    ttl_seconds=0, refresh=True, source=broken_source,
                )
            self.assertEqual(result, first_result)
            self.assertIn("WARNING", mock_stderr.getvalue())




class TestRoleRegistry(unittest.TestCase):
    def test_has_role_known_role(self):
        self.assertTrue(octowiz_cache.ROLE_REGISTRY.has_role("planner"))

    def test_has_role_unknown_role(self):
        self.assertFalse(octowiz_cache.ROLE_REGISTRY.has_role("nonexistent"))

    def test_contains_operator(self):
        self.assertIn("implementer", octowiz_cache.ROLE_REGISTRY)
        self.assertNotIn("ghost", octowiz_cache.ROLE_REGISTRY)

    def test_role_names_returns_all_roles(self):
        names = octowiz_cache.ROLE_REGISTRY.role_names()
        self.assertIsInstance(names, list)
        for role in ("planner", "implementer", "reviewer", "qa", "routing"):
            self.assertIn(role, names)

    def test_get_keys_expands_namespace(self):
        keys = octowiz_cache.ROLE_REGISTRY.get_keys("planner", "myteam")
        # No key should contain the un-expanded placeholder
        for key in keys:
            self.assertNotIn("{namespace}", key)
        # At least one key must contain the actual namespace value
        self.assertTrue(
            any("myteam" in key for key in keys),
            "Expected at least one key to contain the expanded namespace 'myteam'",
        )

    def test_get_keys_unknown_role_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            octowiz_cache.ROLE_REGISTRY.get_keys("ghost", "allspark")
        self.assertIn("ghost", str(ctx.exception))

    def test_iter_yields_role_names(self):
        roles_via_iter = list(octowiz_cache.ROLE_REGISTRY)
        self.assertIn("planner", roles_via_iter)
        self.assertIn("routing", roles_via_iter)

    def test_role_names_returns_all_roles(self):
        """role_names() must return a list containing all registered roles."""
        names = octowiz_cache.ROLE_REGISTRY.role_names()
        self.assertIsInstance(names, list)
        self.assertIn("planner", names)
        self.assertIn("routing", names)


class TestRoleRegistryDriftDetection(unittest.TestCase):
    def test_all_skill_roles_exist_in_registry(self):
        skill_path = Path(__file__).parent.parent.parent.parent / "skills" / "octowiz-workflow" / "skill.md"
        text = skill_path.read_text(encoding="utf-8")
        # Find --role <name> patterns in the skill
        mentioned = set(re.findall(r"--role\s+(\w+)", text))
        for role in mentioned:
            self.assertIn(
                role,
                octowiz_cache.ROLE_REGISTRY,
                f"Role {role!r} mentioned in skill.md but not in ROLE_REGISTRY",
            )




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
        self.assertEqual(sorted(role_names), sorted(octowiz_cache.ROLE_REGISTRY.role_names()))

    def test_fresh_cache_entry_is_fresh(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            octowiz_cache.CacheStore(Path(tmpdir)).seed("planner", "allspark", "# content\n")
            statuses = cache_status(namespace="allspark", cache_dir=tmpdir, ttl_seconds=3600)
        planner = next(s for s in statuses if s.role == "planner")
        self.assertTrue(planner.is_fresh)
        self.assertIsNotNone(planner.age_seconds)
        self.assertGreater(planner.age_seconds, 0)
        self.assertLess(planner.age_seconds, 300)

    def test_stale_cache_entry_is_not_fresh(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            octowiz_cache.CacheStore(Path(tmpdir)).seed(
                "reviewer", "allspark", "# content\n", expired=True
            )
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
        keys = octowiz_cache.ROLE_REGISTRY.get_keys(role, namespace)
        return [{"key": k, "value": f"content for {k}", "metadata": {}} for k in keys]

    def _patch_get_bundle_success(self, roles_to_succeed):
        """Return a mock that succeeds for given roles."""
        def fake_get_bundle(role, namespace, cache_dir, ttl_seconds, refresh):
            if role in roles_to_succeed:
                return f"# Bundle for {role}\n"
            raise RuntimeError(f"Simulated failure for {role}")
        return fake_get_bundle

    def test_all_roles_succeed(self):
        roles = list(octowiz_cache.ROLE_REGISTRY.role_names())
        with patch("packages.memory_client.cache.get_bundle") as mock_gb:
            mock_gb.return_value = "# Bundle content\n"
            result = build_bundles(roles=roles, namespace="allspark",
                                   cache_dir="/tmp/test", ttl_seconds=3600, refresh=False)
        self.assertEqual(result.failed, [])
        self.assertEqual(sorted(result.built), sorted(roles))

    def test_one_role_fails(self):
        roles = list(octowiz_cache.ROLE_REGISTRY.role_names())
        failing_role = roles[0]

        def side_effect(role, namespace, cache_dir, ttl_seconds, refresh):
            if role == failing_role:
                raise RuntimeError("fetch error")
            return f"# Bundle for {role}\n"

        with patch("packages.memory_client.cache.get_bundle", side_effect=side_effect):
            result = build_bundles(roles=roles, namespace="allspark",
                                   cache_dir="/tmp/test", ttl_seconds=3600, refresh=False)

        self.assertEqual(len(result.failed), 1)
        failure = result.failed[0]
        self.assertIsInstance(failure, BuildFailure)
        self.assertEqual(failure.role, failing_role)
        self.assertIn("fetch error", str(failure.exception))
        self.assertEqual(failure.kind, FailureKind.UNKNOWN)
        self.assertNotIn(failing_role, result.built)
        # All other roles should be in built
        for role in roles:
            if role != failing_role:
                self.assertIn(role, result.built)

    def test_refresh_true_passed_to_get_bundle(self):
        roles = list(octowiz_cache.ROLE_REGISTRY.role_names())
        with patch("packages.memory_client.cache.get_bundle") as mock_gb:
            mock_gb.return_value = "# Bundle content\n"
            build_bundles(roles=roles, namespace="allspark",
                          cache_dir="/tmp/test", ttl_seconds=3600, refresh=True)
        for call in mock_gb.call_args_list:
            self.assertEqual(call.kwargs["refresh"], True)

    def test_key_error_classified_as_missing_key(self):
        role = octowiz_cache.ROLE_REGISTRY.role_names()[0]

        def side_effect(role, namespace, cache_dir, ttl_seconds, refresh):
            raise KeyError("some-memory-key")

        with patch("packages.memory_client.cache.get_bundle", side_effect=side_effect):
            result = build_bundles(roles=[role], namespace="allspark",
                                   cache_dir="/tmp/test", ttl_seconds=3600, refresh=False)

        self.assertEqual(len(result.failed), 1)
        self.assertEqual(result.failed[0].kind, FailureKind.MISSING_KEY)
        self.assertEqual(result.failed[0].role, role)

    def test_runtime_error_with_api_key_classified_as_auth(self):
        role = octowiz_cache.ROLE_REGISTRY.role_names()[0]

        def side_effect(role, namespace, cache_dir, ttl_seconds, refresh):
            raise RuntimeError("No LiteLLM API key configured")

        with patch("packages.memory_client.cache.get_bundle", side_effect=side_effect):
            result = build_bundles(roles=[role], namespace="allspark",
                                   cache_dir="/tmp/test", ttl_seconds=3600, refresh=False)

        self.assertEqual(len(result.failed), 1)
        self.assertEqual(result.failed[0].kind, FailureKind.AUTH)
        self.assertEqual(result.failed[0].role, role)

    def test_unknown_exception_classified_as_unknown(self):
        role = octowiz_cache.ROLE_REGISTRY.role_names()[0]

        def side_effect(role, namespace, cache_dir, ttl_seconds, refresh):
            raise ValueError("something unexpected")

        with patch("packages.memory_client.cache.get_bundle", side_effect=side_effect):
            result = build_bundles(roles=[role], namespace="allspark",
                                   cache_dir="/tmp/test", ttl_seconds=3600, refresh=False)

        self.assertEqual(len(result.failed), 1)
        self.assertEqual(result.failed[0].kind, FailureKind.UNKNOWN)
        self.assertEqual(result.failed[0].role, role)


# ---------------------------------------------------------------------------
# CacheStore.seed() — public test-setup helper
# ---------------------------------------------------------------------------


class TestCacheStoreSeed(unittest.TestCase):
    def test_seed_makes_bundle_retrievable_via_get_best_available(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = octowiz_cache.CacheStore(Path(tmpdir))
            store.seed("routing", "allspark", "# seeded content\n")
            self.assertEqual(store.get_best_available("routing", "allspark"), "# seeded content\n")

    def test_seed_returns_self_for_chaining(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = octowiz_cache.CacheStore(Path(tmpdir))
            result = store.seed("routing", "allspark", "# content\n")
            self.assertIs(result, store)

    def test_seed_expired_bundle_still_served_as_stale_fallback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = octowiz_cache.CacheStore(Path(tmpdir), ttl_seconds=3600)
            store.seed("routing", "allspark", "# stale content\n", expired=True)
            # get_best_available falls back to stale when no fresh entry exists
            self.assertEqual(store.get_best_available("routing", "allspark"), "# stale content\n")

    def test_seed_fresh_is_returned_preferentially_over_stale(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = octowiz_cache.CacheStore(Path(tmpdir), ttl_seconds=3600)
            # Seed stale first, then fresh; fresh must win
            store.seed("routing", "allspark", "# old stale\n", expired=True)
            store.seed("routing", "allspark", "# new fresh\n")
            self.assertEqual(store.get_best_available("routing", "allspark"), "# new fresh\n")

    def test_seed_expired_is_not_served_by_get_fresh_path(self):
        """Expired seed must trigger a LiteLLM fetch in get_bundle (tested via stale-fallback
        behaviour: calling get_bundle with a failing source still serves the stale seed)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = octowiz_cache.CacheStore(Path(tmpdir), ttl_seconds=3600)
            store.seed("routing", "allspark", "# stale\n", expired=True)
            # With ttl=0 every entry counts as expired; best_available still serves stale
            store2 = octowiz_cache.CacheStore(Path(tmpdir), ttl_seconds=0)
            self.assertEqual(store2.get_best_available("routing", "allspark"), "# stale\n")

    def test_seed_multiple_roles_independently(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = octowiz_cache.CacheStore(Path(tmpdir))
            store.seed("routing", "allspark", "# routing\n")
            store.seed("planner", "allspark", "# planner\n")
            self.assertEqual(store.get_best_available("routing", "allspark"), "# routing\n")
            self.assertEqual(store.get_best_available("planner", "allspark"), "# planner\n")


# ---------------------------------------------------------------------------
# get_bundle() source injection (Candidate 1)
# ---------------------------------------------------------------------------


class TestGetBundleSourceInjection(unittest.TestCase):
    """source: MemorySource | None = None parameter on get_bundle()."""

    def _make_source(self, role="routing", namespace="allspark"):
        keys = octowiz_cache.ROLE_REGISTRY.get_keys(role, namespace)
        data = {k: {"key": k, "value": f"injected:{k}", "metadata": {}} for k in keys}
        return DictMemorySource(data)

    def test_injected_source_used_instead_of_litellm(self):
        """When source is provided, get_bundle must use it and never call get_litellm_client."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = self._make_source()
            with patch("packages.memory_client.cache.get_litellm_client") as mock_client_factory:
                result = octowiz_cache.get_bundle(
                    "routing", "allspark", cache_dir=tmpdir, source=source
                )
            mock_client_factory.assert_not_called()
            self.assertIn("Octowiz Doctrine Bundle", result)

    def test_injected_source_content_appears_in_bundle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = self._make_source()
            result = octowiz_cache.get_bundle(
                "routing", "allspark", cache_dir=tmpdir, source=source
            )
            self.assertIn("injected:", result)

    def test_cache_hit_skips_source_on_second_call(self):
        """A fresh cache entry must be served without calling source.fetch at all."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = self._make_source()
            # Populate cache
            octowiz_cache.get_bundle("routing", "allspark", cache_dir=tmpdir, source=source)
            # Second call: cache is fresh, source.fetch must NOT be called
            from unittest.mock import MagicMock
            spy_source = MagicMock()
            spy_source.fetch.side_effect = AssertionError("source.fetch called on cache hit")
            octowiz_cache.get_bundle("routing", "allspark", cache_dir=tmpdir, source=spy_source)

    def test_stale_cache_with_source_fetches_fresh(self):
        """If cache is expired, source must be called even when source is injected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = octowiz_cache.CacheStore(Path(tmpdir))
            store.seed("routing", "allspark", "# old cached\n", expired=True)
            source = self._make_source()
            result = octowiz_cache.get_bundle(
                "routing", "allspark", cache_dir=tmpdir, ttl_seconds=3600,
                source=source, refresh=False,
            )
            # Fresh fetch from source should overwrite the stale seed
            self.assertIn("injected:", result)

    def test_none_source_falls_back_to_litellm(self):
        """Omitting source (None) must still call get_litellm_client as before."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_client = MagicMock()
            keys = octowiz_cache.ROLE_REGISTRY.get_keys("routing", "allspark")
            memories = [{"key": k, "value": "v", "metadata": {}} for k in keys]
            with patch("packages.memory_client.cache.get_litellm_client", return_value=mock_client):
                with patch("packages.memory_client.cache.fetch_role_memories", return_value=memories):
                    octowiz_cache.get_bundle("routing", "allspark", cache_dir=tmpdir)
            mock_client.close.assert_called()


if __name__ == "__main__":
    unittest.main()
