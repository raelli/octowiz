"""Tests for OCTOWIZ_INBOUND_SECRET auth middleware."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from fastapi.testclient import TestClient


def _make_client(secret=None):
    if secret is not None:
        os.environ["OCTOWIZ_INBOUND_SECRET"] = secret
    else:
        os.environ.pop("OCTOWIZ_INBOUND_SECRET", None)
    import importlib
    import main as m
    importlib.reload(m)
    return TestClient(m.app)


MINIMAL_BODY = {
    "jsonrpc": "2.0",
    "id": 1,
    "params": {"message": {"parts": [{"text": '{"type": "ping"}'}]}},
}


class TestAuthWithSecretSet(unittest.TestCase):
    def setUp(self):
        self.secret = "test-secret-abc"
        self.client = _make_client(self.secret)

    def tearDown(self):
        os.environ.pop("OCTOWIZ_INBOUND_SECRET", None)

    def test_valid_secret_returns_200(self):
        resp = self.client.post(
            "/a2a/octowiz",
            json=MINIMAL_BODY,
            headers={"x-octowiz-secret": self.secret},
        )
        self.assertEqual(resp.status_code, 200)

    def test_wrong_secret_returns_401(self):
        resp = self.client.post(
            "/a2a/octowiz",
            json=MINIMAL_BODY,
            headers={"x-octowiz-secret": "wrong-secret"},
        )
        self.assertEqual(resp.status_code, 401)

    def test_missing_secret_header_returns_401(self):
        resp = self.client.post("/a2a/octowiz", json=MINIMAL_BODY)
        self.assertEqual(resp.status_code, 401)

    def test_card_endpoint_accessible_without_secret_header(self):
        resp = self.client.get("/a2a/octowiz/.well-known/agent.json")
        self.assertEqual(resp.status_code, 200)


class TestAuthWithNoSecretEnvVar(unittest.TestCase):
    def setUp(self):
        self.client = _make_client(secret=None)

    def tearDown(self):
        os.environ.pop("OCTOWIZ_INBOUND_SECRET", None)

    def test_request_blocked_when_secret_not_configured(self):
        """Fail-closed: every POST request is rejected when the secret is unset.

        P1 fix: the response body must NOT disclose the env var name to callers.
        """
        resp = self.client.post("/a2a/octowiz", json=MINIMAL_BODY)
        self.assertEqual(resp.status_code, 401)
        # Generic response — must not leak the env var name.
        self.assertNotIn("OCTOWIZ_INBOUND_SECRET", resp.json()["error"])
        # Should be a generic unauthorized message.
        self.assertEqual(resp.json()["error"], "Unauthorized")

    def test_card_endpoint_accessible_when_secret_not_configured(self):
        resp = self.client.get("/a2a/octowiz/.well-known/agent.json")
        self.assertEqual(resp.status_code, 200)


class TestPrincipalHeader(unittest.TestCase):
    """x-octowiz-principal header: daemon-forwarded tasks pass their principal
    explicitly; direct callers (bridge.py) must still derive principal from
    the secret hash via _principal_from().
    """

    def setUp(self):
        self.secret = "test-secret-abc"
        os.environ["OCTOWIZ_INBOUND_SECRET"] = self.secret
        import importlib
        import main as m
        importlib.reload(m)
        self.client = TestClient(m.app)

    def tearDown(self):
        os.environ.pop("OCTOWIZ_INBOUND_SECRET", None)

    def test_explicit_principal_header_is_used_when_present(self):
        """When x-octowiz-principal is sent, main.py uses that value."""
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "params": {"message": {"parts": [{"text": '{"type": "ping", "capability": "octowiz.advise"}'}]}},
        }
        resp = self.client.post(
            "/a2a/octowiz",
            json=body,
            headers={
                "x-octowiz-secret": self.secret,
                "x-octowiz-principal": "explicit-principal-123",
            },
        )
        # Authentication still required even when principal header is present.
        self.assertEqual(resp.status_code, 200)

    def test_no_principal_header_falls_back_to_derived_principal(self):
        """When x-octowiz-principal is absent, falls back to _principal_from()."""
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "params": {"message": {"parts": [{"text": '{"type": "ping", "capability": "octowiz.advise"}'}]}},
        }
        resp = self.client.post(
            "/a2a/octowiz",
            json=body,
            headers={"x-octowiz-secret": self.secret},
        )
        self.assertEqual(resp.status_code, 200)

    def test_explicit_principal_does_not_bypass_auth(self):
        """Sending x-octowiz-principal with the wrong secret still returns 401."""
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "params": {"message": {"parts": [{"text": '{"type": "ping"}'}]}},
        }
        resp = self.client.post(
            "/a2a/octowiz",
            json=body,
            headers={
                "x-octowiz-secret": "wrong-secret",
                "x-octowiz-principal": "explicit-principal-123",
            },
        )
        self.assertEqual(resp.status_code, 401)
