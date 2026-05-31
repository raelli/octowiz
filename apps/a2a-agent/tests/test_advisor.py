"""Tests for octowiz.advise capability — all three rules."""
import json
import os
import sys
_A2A_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ROOT_DIR = os.path.dirname(os.path.dirname(_A2A_DIR))
sys.path.insert(0, _A2A_DIR)
sys.path.insert(0, _ROOT_DIR)

import unittest
from fastapi.testclient import TestClient

_SECRET = "test-secret"


def _fresh_client():
    os.environ["OCTOWIZ_INBOUND_SECRET"] = _SECRET
    import importlib
    import packages.advisor.state as _state_mod
    importlib.reload(_state_mod)
    import packages.advisor.policy as _policy_mod
    importlib.reload(_policy_mod)
    import capabilities.advise as _adv_mod
    importlib.reload(_adv_mod)
    import main as m
    importlib.reload(m)
    return TestClient(m.app)


def _post_advise(client, event):
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "params": {"message": {"parts": [{"text": json.dumps({**event, "capability": "octowiz.advise"})}]}},
    }
    resp = client.post("/a2a/octowiz", json=body, headers={"x-octowiz-secret": _SECRET})
    text = resp.json()["result"]["artifacts"][0]["parts"][0]["text"]
    return json.loads(text)


class TestFileConflictRule(unittest.TestCase):
    def setUp(self):
        self.client = _fresh_client()

    def tearDown(self):
        os.environ.pop("OCTOWIZ_INBOUND_SECRET", None)

    def test_same_branch_sessions_do_not_trigger_conflict(self):
        # Two sessions on the SAME branch touching the same file should not conflict
        _post_advise(self.client, {
            "type": "prompt", "sessionId": "sess-x", "branch": "main",
            "repoRoot": "/repo", "live_modified_files": ["utils.py"],
            "prompt_summary": "utils.py",
        })
        result = _post_advise(self.client, {
            "type": "prompt", "sessionId": "sess-y", "branch": "main",
            "repoRoot": "/repo", "live_modified_files": ["utils.py"],
            "prompt_summary": "utils.py",
        })
        self.assertIsNone(result.get("type"))
        self.assertIsNone(result.get("level"))

    def test_cleared_files_do_not_remain_in_conflict_index(self):
        # Session registers files, then sends event with empty files — conflict should clear
        _post_advise(self.client, {
            "type": "prompt", "sessionId": "sess-old", "branch": "feat/a",
            "repoRoot": "/repo", "live_modified_files": ["foo.py"],
            "prompt_summary": "foo.py",
        })
        # Same session clears its files
        _post_advise(self.client, {
            "type": "prompt", "sessionId": "sess-old", "branch": "feat/a",
            "repoRoot": "/repo", "live_modified_files": [],
            "prompt_summary": "",
        })
        # New session on different branch — should see no conflict
        result = _post_advise(self.client, {
            "type": "prompt", "sessionId": "sess-new", "branch": "feat/b",
            "repoRoot": "/repo", "live_modified_files": ["foo.py"],
            "prompt_summary": "foo.py",
        })
        self.assertIsNone(result.get("type"))
        self.assertIsNone(result.get("level"))

    def test_two_sessions_touching_same_file_different_branches_triggers_conflict(self):
        # Session A registers file on branch-a
        _post_advise(self.client, {
            "type": "prompt", "sessionId": "sess-a", "branch": "branch-a",
            "repoRoot": "/repo", "live_modified_files": ["src/payment.py"],
            "prompt_summary": "src/payment.py",
        })
        # Session B on branch-b asks about same file
        result = _post_advise(self.client, {
            "type": "prompt", "sessionId": "sess-b", "branch": "branch-b",
            "repoRoot": "/repo", "live_modified_files": ["src/payment.py"],
            "prompt_summary": "src/payment.py",
        })
        self.assertEqual(result["type"], "file-conflict")
        self.assertEqual(result.get("level"), "intervene")
        self.assertIn("src/payment.py", result["files"])
        self.assertEqual(result["level"], "intervene")


class TestBranchDriftRule(unittest.TestCase):
    def setUp(self):
        self.client = _fresh_client()

    def tearDown(self):
        os.environ.pop("OCTOWIZ_INBOUND_SECRET", None)

    def test_20_file_events_triggers_drift_warning(self):
        sid = "sess-drift"
        for i in range(20):
            _post_advise(self.client, {
                "type": "file-write", "sessionId": sid, "branch": "feat/big-change",
                "repoRoot": "/repo", "live_modified_files": [f"file{i}.py"],
                "prompt_summary": "",
            })
        result = _post_advise(self.client, {
            "type": "prompt", "sessionId": sid, "branch": "feat/big-change",
            "repoRoot": "/repo", "live_modified_files": [], "prompt_summary": "something",
        })
        self.assertEqual(result["type"], "branch-drift")
        self.assertEqual(result.get("level"), "advise")

    def test_19_file_events_does_not_trigger_drift(self):
        sid = "sess-nodrift"
        for i in range(19):
            _post_advise(self.client, {
                "type": "file-write", "sessionId": sid, "branch": "feat/ok",
                "repoRoot": "/repo", "live_modified_files": [f"f{i}.py"],
                "prompt_summary": "",
            })
        result = _post_advise(self.client, {
            "type": "prompt", "sessionId": sid, "branch": "feat/ok",
            "repoRoot": "/repo", "live_modified_files": [], "prompt_summary": "ok",
        })
        self.assertIsNone(result.get("type"))
        self.assertIsNone(result.get("level"))


class TestSpecDeviationRule(unittest.TestCase):
    def setUp(self):
        self.client = _fresh_client()

    def tearDown(self):
        os.environ.pop("OCTOWIZ_INBOUND_SECRET", None)

    def test_files_absent_from_prompt_summary_triggers_deviation(self):
        result = _post_advise(self.client, {
            "type": "prompt", "sessionId": "sess-dev",
            "branch": "main", "repoRoot": "/repo",
            "live_modified_files": ["auth.py", "payment.py"],
            "prompt_summary": "update auth.py — fix login flow",
        })
        self.assertEqual(result["type"], "spec-deviation")
        self.assertEqual(result.get("level"), "advise")
        self.assertIn("payment.py", result["files"])
        self.assertNotIn("auth.py", result["files"])
        self.assertEqual(result["level"], "advise")


class TestInvocationPolicy(unittest.TestCase):
    def setUp(self):
        self.client = _fresh_client()

    def test_no_rule_fires_returns_empty_artifact(self):
        result = _post_advise(self.client, {
            "type": "prompt", "sessionId": "sess-clean",
            "branch": "main", "repoRoot": "/repo",
            "live_modified_files": ["auth.py"],
            "prompt_summary": "update auth.py",
        })
        self.assertIsNone(result.get("type"))
        self.assertIsNone(result.get("level"))

    def test_two_rules_escalate(self):
        # Trigger both branch-drift (20 file writes) AND spec-deviation (file not in summary)
        sid = "sess-escalate"
        for i in range(20):
            _post_advise(self.client, {
                "type": "file-write", "sessionId": sid, "branch": "feat/x",
                "repoRoot": "/repo", "live_modified_files": [f"file{i}.py"],
                "prompt_summary": "",
            })
        # prompt that also triggers spec-deviation: live_modified_files not in summary
        result = _post_advise(self.client, {
            "type": "prompt", "sessionId": sid, "branch": "feat/x",
            "repoRoot": "/repo",
            "live_modified_files": ["payment.py"],
            "prompt_summary": "fix login bug",  # payment.py not mentioned
        })
        self.assertEqual(result["level"], "escalate")
        self.assertIn("reason", result)
        self.assertIn("question", result)

    def test_file_conflict_maps_to_intervene(self):
        _post_advise(self.client, {
            "type": "prompt", "sessionId": "s-alpha", "branch": "feat/a",
            "repoRoot": "/repo", "live_modified_files": ["core.py"],
            "prompt_summary": "core.py",
        })
        result = _post_advise(self.client, {
            "type": "prompt", "sessionId": "s-beta", "branch": "feat/b",
            "repoRoot": "/repo", "live_modified_files": ["core.py"],
            "prompt_summary": "core.py",
        })
        self.assertEqual(result["level"], "intervene")

    def test_branch_drift_maps_to_advise(self):
        sid = "sess-drift2"
        for i in range(20):
            _post_advise(self.client, {
                "type": "file-write", "sessionId": sid, "branch": "feat/big",
                "repoRoot": "/repo", "live_modified_files": [f"f{i}.py"],
                "prompt_summary": "",
            })
        result = _post_advise(self.client, {
            "type": "prompt", "sessionId": sid, "branch": "feat/big",
            "repoRoot": "/repo", "live_modified_files": [], "prompt_summary": "ok",
        })
        self.assertEqual(result["level"], "advise")
