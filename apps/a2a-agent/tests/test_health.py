"""Tests for /health endpoint."""
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

os.environ.setdefault("OCTOWIZ_INBOUND_SECRET", "test-secret")

from fastapi.testclient import TestClient
from main import app

client = TestClient(app, raise_server_exceptions=True)


class TestHealthEndpoint(unittest.TestCase):

    def test_returns_200(self):
        resp = client.get("/health")
        self.assertEqual(resp.status_code, 200)

    def test_status_is_ok(self):
        resp = client.get("/health")
        self.assertEqual(resp.json()["status"], "ok")

    def test_version_present_and_string(self):
        resp = client.get("/health")
        version = resp.json().get("version")
        self.assertIsInstance(version, str)
        self.assertTrue(len(version) > 0)

    def test_version_matches_plugin_json(self):
        import json, pathlib
        here = pathlib.Path(__file__).resolve().parent
        plugin_json = None
        for candidate in [here, *here.parents]:
            p = candidate / ".claude-plugin" / "plugin.json"
            if p.exists():
                plugin_json = json.loads(p.read_text())
                break
        if plugin_json is None:
            self.skipTest("plugin.json not found in directory tree")
        expected = plugin_json.get("version")
        actual = client.get("/health").json().get("version")
        self.assertEqual(actual, expected)

    def test_health_requires_no_auth(self):
        # /health must be reachable without OCTOWIZ_INBOUND_SECRET header
        from fastapi.testclient import TestClient
        unauthenticated_client = TestClient(app, raise_server_exceptions=True)
        resp = unauthenticated_client.get("/health", headers={})
        self.assertEqual(resp.status_code, 200)


if __name__ == "__main__":
    unittest.main()
