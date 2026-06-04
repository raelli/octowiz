"""Tests for marketplace_client.manifest — manifest fetch, parse, and cache."""
from __future__ import annotations

import json
import os
import sys
import time
import unittest
from unittest.mock import patch, MagicMock

# Make packages/ importable
_PKG_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _PKG_DIR)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SAMPLE_MANIFEST = {
    "name": "IntegraHub",
    "owner": {"name": "https://github.com/raelli", "email": "support@integrahub.de"},
    "plugins": [
        {
            "name": "superpowers",
            "source": {"source": "github", "repo": "obra/superpowers"},
            "version": "1.0.0",
            "description": "Composable coding-agent workflow.",
            "keywords": ["coding-agent", "skills"],
            "category": "Coding",
        },
        {
            "name": "mattpo-skills",
            "source": {"source": "github", "repo": "obra/mattpo-skills"},
            "version": "2.3.1",
            "description": "Matt Pocock TypeScript skills.",
            "keywords": ["typescript"],
            "category": "Development",
        },
        {
            "name": "octowiz",
            "source": {"source": "github", "repo": "raelli/octowiz"},
            "version": "0.9.0",
            "description": "AELLI's coding alter-ego.",
            "keywords": ["a2a", "agent"],
            "category": "Development",
        },
    ],
}


# ---------------------------------------------------------------------------
# Tests: fetch (no cache)
# ---------------------------------------------------------------------------


class TestFetchManifest(unittest.TestCase):
    """fetch_manifest returns parsed manifest from configured URL."""

    def setUp(self):
        os.environ["INTEGRAHUB_MARKETPLACE_URL"] = "https://fake.integrahub.de/marketplace.json"
        os.environ.pop("MARKETPLACE_CACHE_TTL_SECONDS", None)

    def tearDown(self):
        os.environ.pop("INTEGRAHUB_MARKETPLACE_URL", None)
        os.environ.pop("MARKETPLACE_CACHE_TTL_SECONDS", None)

    def test_returns_parsed_manifest_from_url(self):
        import httpx
        from marketplace_client.manifest import fetch_manifest

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = _SAMPLE_MANIFEST

        with patch("httpx.get", return_value=mock_resp) as mock_get:
            result = fetch_manifest()

        mock_get.assert_called_once()
        called_url = mock_get.call_args[0][0]
        self.assertIn("fake.integrahub.de", called_url)
        self.assertEqual(result["name"], "IntegraHub")
        self.assertIsInstance(result["plugins"], list)
        self.assertEqual(len(result["plugins"]), 3)

    def test_url_read_from_env_not_hardcoded(self):
        """Marketplace URL must come from env var, not a literal in code."""
        from marketplace_client.manifest import fetch_manifest
        os.environ["INTEGRAHUB_MARKETPLACE_URL"] = "https://custom.example.com/mkt.json"

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = _SAMPLE_MANIFEST

        with patch("httpx.get", return_value=mock_resp) as mock_get:
            fetch_manifest()

        called_url = mock_get.call_args[0][0]
        self.assertIn("custom.example.com", called_url)

    def test_raises_on_http_error(self):
        import httpx
        from marketplace_client.manifest import fetch_manifest

        with patch("httpx.get", side_effect=httpx.RequestError("connection refused")):
            with self.assertRaises(httpx.RequestError):
                fetch_manifest()

    def test_url_not_configured_raises_value_error(self):
        os.environ.pop("INTEGRAHUB_MARKETPLACE_URL", None)
        from marketplace_client.manifest import fetch_manifest

        with self.assertRaises(ValueError):
            fetch_manifest()


# ---------------------------------------------------------------------------
# Tests: cached fetch
# ---------------------------------------------------------------------------


class TestCachedManifest(unittest.TestCase):
    """get_manifest returns cached manifest, only refetches after TTL."""

    def setUp(self):
        os.environ["INTEGRAHUB_MARKETPLACE_URL"] = "https://fake.integrahub.de/marketplace.json"

    def tearDown(self):
        os.environ.pop("INTEGRAHUB_MARKETPLACE_URL", None)
        # Reset module-level cache between tests
        try:
            from marketplace_client import manifest as _m
            _m._CACHE.clear()
        except Exception:
            pass

    def test_second_call_does_not_hit_network(self):
        from marketplace_client.manifest import get_manifest

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = _SAMPLE_MANIFEST

        with patch("httpx.get", return_value=mock_resp) as mock_get:
            r1 = get_manifest()
            r2 = get_manifest()

        self.assertEqual(mock_get.call_count, 1)
        self.assertEqual(r1, r2)

    def test_expired_cache_refetches(self):
        from marketplace_client.manifest import get_manifest, _CACHE

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = _SAMPLE_MANIFEST

        # Seed cache with very old entry
        _CACHE["manifest"] = (_SAMPLE_MANIFEST, time.monotonic() - 99999)

        with patch("httpx.get", return_value=mock_resp) as mock_get:
            get_manifest(ttl_seconds=1)

        self.assertEqual(mock_get.call_count, 1)

    def test_fresh_cache_not_refetched(self):
        from marketplace_client.manifest import get_manifest, _CACHE

        _CACHE["manifest"] = (_SAMPLE_MANIFEST, time.monotonic())

        with patch("httpx.get") as mock_get:
            result = get_manifest(ttl_seconds=3600)

        mock_get.assert_not_called()
        self.assertEqual(result["name"], "IntegraHub")


class TestListPlugins(unittest.TestCase):
    """list_plugins returns flat list of plugin entries from manifest."""

    def setUp(self):
        os.environ["INTEGRAHUB_MARKETPLACE_URL"] = "https://fake.integrahub.de/marketplace.json"

    def tearDown(self):
        os.environ.pop("INTEGRAHUB_MARKETPLACE_URL", None)
        try:
            from marketplace_client import manifest as _m
            _m._CACHE.clear()
        except Exception:
            pass

    def _patch_get_manifest(self, data=None):
        from unittest.mock import patch
        return patch("marketplace_client.manifest.get_manifest", return_value=data or _SAMPLE_MANIFEST)

    def test_returns_all_plugin_names(self):
        from marketplace_client.manifest import list_plugins

        with self._patch_get_manifest():
            plugins = list_plugins()

        names = [p["name"] for p in plugins]
        self.assertIn("superpowers", names)
        self.assertIn("mattpo-skills", names)
        self.assertIn("octowiz", names)

    def test_returns_empty_for_empty_manifest(self):
        from marketplace_client.manifest import list_plugins

        with self._patch_get_manifest({"name": "empty", "plugins": []}):
            result = list_plugins()

        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
