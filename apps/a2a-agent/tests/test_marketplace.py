"""Tests for octowiz.marketplace_info A2A capability."""
from __future__ import annotations

import asyncio
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
_PKG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(_HERE))), "packages")
sys.path.insert(0, _PKG_DIR)

os.environ.setdefault("OCTOWIZ_INBOUND_SECRET", "test-secret")


def _run(coro):
    return asyncio.run(coro)


_SAMPLE_MANIFEST = {
    "name": "IntegraHub",
    "plugins": [
        {"name": "superpowers", "version": "1.0.0", "category": "Coding",
         "source": {"source": "github", "repo": "obra/superpowers"}},
        {"name": "mattpo-skills", "version": "2.3.1", "category": "Development",
         "source": {"source": "github", "repo": "obra/mattpo-skills"}},
        {"name": "octowiz", "version": "0.9.0", "category": "Development",
         "source": {"source": "github", "repo": "raelli/octowiz"}},
    ],
}


class TestMarketplaceInfoUnavailable(unittest.TestCase):
    """Returns unavailable when no marketplace URL configured."""

    def setUp(self):
        os.environ.pop("INTEGRAHUB_MARKETPLACE_URL", None)

    def tearDown(self):
        os.environ.pop("INTEGRAHUB_MARKETPLACE_URL", None)

    def test_unavailable_when_no_url(self):
        from capabilities.marketplace_info import handle_marketplace_info
        result = _run(handle_marketplace_info({}))
        self.assertEqual(result["status"], "unavailable")
        self.assertIn("INTEGRAHUB_MARKETPLACE_URL", result["message"])


class TestMarketplaceInfoResolve(unittest.TestCase):
    """resolve operation returns resolved and unresolved dependencies."""

    def setUp(self):
        os.environ["INTEGRAHUB_MARKETPLACE_URL"] = "https://fake.integrahub.de/marketplace.json"

    def tearDown(self):
        os.environ.pop("INTEGRAHUB_MARKETPLACE_URL", None)
        try:
            from marketplace_client import manifest as _m
            _m._CACHE.clear()
        except Exception:
            pass

    def test_resolve_deps_from_plugin_json(self):
        from capabilities.marketplace_info import handle_marketplace_info

        with patch("marketplace_client.manifest.get_manifest", return_value=_SAMPLE_MANIFEST):
            result = _run(handle_marketplace_info({
                "operation": "resolve",
                "dependencies": ["superpowers", "mattpo-skills"],
            }))

        self.assertEqual(result["status"], "ok")
        self.assertIn("resolved", result)
        resolved_names = [r["name"] for r in result["resolved"]]
        self.assertIn("superpowers", resolved_names)
        self.assertIn("mattpo-skills", resolved_names)

    def test_resolve_reports_missing_dep(self):
        from capabilities.marketplace_info import handle_marketplace_info

        with patch("marketplace_client.manifest.get_manifest", return_value=_SAMPLE_MANIFEST):
            result = _run(handle_marketplace_info({
                "operation": "resolve",
                "dependencies": ["superpowers", "does-not-exist"],
            }))

        self.assertEqual(result["status"], "ok")
        self.assertIn("unresolved", result)
        self.assertIn("does-not-exist", result["unresolved"])

    def test_resolve_empty_deps(self):
        from capabilities.marketplace_info import handle_marketplace_info

        with patch("marketplace_client.manifest.get_manifest", return_value=_SAMPLE_MANIFEST):
            result = _run(handle_marketplace_info({
                "operation": "resolve",
                "dependencies": [],
            }))

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["resolved"], [])

    def test_resolve_error_on_http_failure(self):
        import httpx
        from capabilities.marketplace_info import handle_marketplace_info

        with patch("marketplace_client.manifest.get_manifest",
                   side_effect=httpx.RequestError("connection refused")):
            result = _run(handle_marketplace_info({
                "operation": "resolve",
                "dependencies": ["superpowers"],
            }))

        self.assertEqual(result["status"], "error")
        self.assertIn("connection refused", result["message"])


class TestMarketplaceInfoDiscover(unittest.TestCase):
    """discover operation lists available skills/plugins from marketplace."""

    def setUp(self):
        os.environ["INTEGRAHUB_MARKETPLACE_URL"] = "https://fake.integrahub.de/marketplace.json"

    def tearDown(self):
        os.environ.pop("INTEGRAHUB_MARKETPLACE_URL", None)
        try:
            from marketplace_client import manifest as _m
            _m._CACHE.clear()
        except Exception:
            pass

    def test_discover_all_returns_all_plugins(self):
        from capabilities.marketplace_info import handle_marketplace_info

        with patch("marketplace_client.manifest.get_manifest", return_value=_SAMPLE_MANIFEST):
            result = _run(handle_marketplace_info({"operation": "discover"}))

        self.assertEqual(result["status"], "ok")
        self.assertIn("plugins", result)
        self.assertEqual(len(result["plugins"]), 3)

    def test_discover_by_category_filters(self):
        from capabilities.marketplace_info import handle_marketplace_info

        with patch("marketplace_client.manifest.get_manifest", return_value=_SAMPLE_MANIFEST):
            result = _run(handle_marketplace_info({
                "operation": "discover",
                "category": "Coding",
            }))

        self.assertEqual(result["status"], "ok")
        names = [p["name"] for p in result["plugins"]]
        self.assertIn("superpowers", names)
        self.assertNotIn("octowiz", names)

    def test_discover_default_operation_is_discover(self):
        """No operation field → defaults to discover."""
        from capabilities.marketplace_info import handle_marketplace_info

        with patch("marketplace_client.manifest.get_manifest", return_value=_SAMPLE_MANIFEST):
            result = _run(handle_marketplace_info({}))

        self.assertIn("status", result)
        # Should not be unavailable (URL is set)
        self.assertNotEqual(result["status"], "unavailable")


class TestMarketplaceInfoCompatibility(unittest.TestCase):
    """compat operation checks version compatibility."""

    def setUp(self):
        os.environ["INTEGRAHUB_MARKETPLACE_URL"] = "https://fake.integrahub.de/marketplace.json"

    def tearDown(self):
        os.environ.pop("INTEGRAHUB_MARKETPLACE_URL", None)
        try:
            from marketplace_client import manifest as _m
            _m._CACHE.clear()
        except Exception:
            pass

    def test_compat_compatible_versions(self):
        from capabilities.marketplace_info import handle_marketplace_info

        result = _run(handle_marketplace_info({
            "operation": "compat",
            "checks": [
                {"name": "superpowers", "required": "1.0.0", "available": "1.0.0"},
            ],
        }))

        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["checks"][0]["compatible"])

    def test_compat_incompatible_versions(self):
        from capabilities.marketplace_info import handle_marketplace_info

        result = _run(handle_marketplace_info({
            "operation": "compat",
            "checks": [
                {"name": "superpowers", "required": "2.0.0", "available": "1.0.0"},
            ],
        }))

        self.assertEqual(result["status"], "ok")
        self.assertFalse(result["checks"][0]["compatible"])

    def test_compat_invalid_checks_type_returns_error(self):
        from capabilities.marketplace_info import handle_marketplace_info

        result = _run(handle_marketplace_info({
            "operation": "compat",
            "checks": "not-a-list",
        }))

        self.assertEqual(result["status"], "error")
        self.assertIn("list", result["message"])


class TestMarketplaceDispatch(unittest.TestCase):
    """dispatch routes octowiz.marketplace_info to the capability."""

    def setUp(self):
        os.environ["INTEGRAHUB_MARKETPLACE_URL"] = "https://fake.integrahub.de/marketplace.json"

    def tearDown(self):
        os.environ.pop("INTEGRAHUB_MARKETPLACE_URL", None)
        try:
            from marketplace_client import manifest as _m
            _m._CACHE.clear()
        except Exception:
            pass

    def test_dispatch_routes_marketplace_info(self):
        from dispatch import dispatch

        with patch("marketplace_client.manifest.get_manifest", return_value=_SAMPLE_MANIFEST):
            result = _run(dispatch({
                "capability": "octowiz.marketplace_info",
                "operation": "discover",
            }))

        self.assertIsNotNone(result)
        self.assertNotEqual(result.get("status"), "not_implemented")


if __name__ == "__main__":
    unittest.main()
