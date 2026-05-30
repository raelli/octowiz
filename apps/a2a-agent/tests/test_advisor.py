"""Tests for octowiz.advise capability — all three rules."""
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.pop("OCTOWIZ_INBOUND_SECRET", None)

import unittest
from fastapi.testclient import TestClient


def _fresh_client():
    import importlib
    import advisor.state as _state_mod
    importlib.reload(_state_mod)
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
    resp = client.post("/a2a/octowiz", json=body)
    text = resp.json()["result"]["artifacts"][0]["parts"][0]["text"]
    return json.loads(text)


class TestFileConflictRule(unittest.TestCase):
    def setUp(self):
        self.client = _fresh_client()

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
        self.assertIn("src/payment.py", result["files"])


class TestBranchDriftRule(unittest.TestCase):
    def setUp(self):
        self.client = _fresh_client()

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


class TestSpecDeviationRule(unittest.TestCase):
    def setUp(self):
        self.client = _fresh_client()

    def test_files_absent_from_prompt_summary_triggers_deviation(self):
        result = _post_advise(self.client, {
            "type": "prompt", "sessionId": "sess-dev",
            "branch": "main", "repoRoot": "/repo",
            "live_modified_files": ["auth.py", "payment.py"],
            "prompt_summary": "update auth.py — fix login flow",
        })
        self.assertEqual(result["type"], "spec-deviation")
        self.assertIn("payment.py", result["files"])
        self.assertNotIn("auth.py", result["files"])
