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


class TestPrincipalIsAlwaysDerivedServerSide(unittest.TestCase):
    """Principal is always derived server-side from the authenticated secret via
    _principal_from(). No client-supplied header can override this — doing so
    would let any holder of the shared secret impersonate another principal and
    hijack session ownership.
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

    def test_x_octowiz_principal_header_is_ignored(self):
        """Sending x-octowiz-principal does not override the server-derived principal.
        Authentication is still enforced; the header is silently ignored."""
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
                "x-octowiz-principal": "attacker-chosen-principal",
            },
        )
        # Request succeeds (auth passes) but the spoofed header is not honoured.
        self.assertEqual(resp.status_code, 200)

    def test_principal_derived_from_secret_when_no_header(self):
        """Without x-octowiz-principal, principal is derived from _principal_from()."""
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
