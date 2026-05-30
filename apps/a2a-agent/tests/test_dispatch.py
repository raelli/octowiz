"""Tests for capability dispatch and /a2a/dev-advisor alias."""
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["OCTOWIZ_INBOUND_SECRET"] = "test-secret"

import unittest
from fastapi.testclient import TestClient
from main import app

_SECRET = "test-secret"


def _post_event(client, event, path="/a2a/octowiz"):
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "params": {"message": {"parts": [{"text": json.dumps(event)}]}},
    }
    return client.post(path, json=body, headers={"x-octowiz-secret": _SECRET})


class TestDispatch(unittest.TestCase):
    def setUp(self):
        os.environ["OCTOWIZ_INBOUND_SECRET"] = _SECRET
        self.client = TestClient(app)

    def tearDown(self):
        os.environ.pop("OCTOWIZ_INBOUND_SECRET", None)

    def test_unknown_capability_returns_not_implemented(self):
        resp = _post_event(self.client, {"capability": "octowiz.plan", "type": "ping"})
        self.assertEqual(resp.status_code, 200)
        artifact = json.loads(resp.json()["result"]["artifacts"][0]["parts"][0]["text"])
        self.assertEqual(artifact["status"], "not_implemented")
        self.assertEqual(artifact["capability"], "octowiz.plan")

    def test_dev_advisor_alias_returns_same_shape(self):
        event = {"capability": "octowiz.plan", "type": "ping"}
        r1 = _post_event(self.client, event, "/a2a/octowiz")
        r2 = _post_event(self.client, event, "/a2a/dev-advisor")
        self.assertEqual(r1.status_code, r2.status_code)
        a1 = json.loads(r1.json()["result"]["artifacts"][0]["parts"][0]["text"])
        a2 = json.loads(r2.json()["result"]["artifacts"][0]["parts"][0]["text"])
        self.assertEqual(a1["status"], a2["status"])
