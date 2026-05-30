"""Unit tests for packages.advisor.policy — PolicyAdvisor rule-to-level mapping."""
import asyncio
import unittest


def _run(coro):
    return asyncio.run(coro)


def _make_store():
    from packages.advisor.state import SessionStore
    return SessionStore()


def _make_policy():
    from packages.advisor.policy import PolicyAdvisor
    return PolicyAdvisor()


def _event(**kwargs):
    base = {
        "type": "prompt",
        "sessionId": "sess-test",
        "branch": "main",
        "repoRoot": "/repo",
        "live_modified_files": [],
        "prompt_summary": "",
    }
    base.update(kwargs)
    return base


class TestPolicyLevels(unittest.TestCase):

    def test_no_rules_fire_returns_none(self):
        policy = _make_policy()
        store = _make_store()
        ev = _event(live_modified_files=["auth.py"], prompt_summary="auth.py")
        result = _run(policy.check(ev, None, {"store": store}))
        self.assertIsNone(result)

    def test_file_conflict_maps_to_intervene(self):
        policy = _make_policy()
        store = _make_store()
        # Register session A
        store.record_event(_event(
            sessionId="sess-a", branch="feat/a",
            live_modified_files=["core.py"], prompt_summary="core.py",
        ))
        # Session B on different branch, same file
        ev = _event(
            sessionId="sess-b", branch="feat/b",
            live_modified_files=["core.py"], prompt_summary="core.py",
        )
        result = _run(policy.check(ev, store.get_session("sess-b"), {"store": store}))
        self.assertIsNotNone(result)
        self.assertEqual(result["level"], "intervene")
        self.assertEqual(result["type"], "file-conflict")

    def test_branch_drift_maps_to_advise(self):
        from packages.advisor.state import SessionStore
        policy = _make_policy()
        store = SessionStore()
        sid = "sess-drift"
        for i in range(20):
            store.record_event({
                "type": "file-write",
                "sessionId": sid,
                "branch": "feat/big",
                "repoRoot": "/repo",
                "live_modified_files": [f"file{i}.py"],
            })
        session = store.get_session(sid)
        ev = _event(sessionId=sid, branch="feat/big",
                    live_modified_files=[], prompt_summary="something")
        result = _run(policy.check(ev, session, {"store": store}))
        self.assertIsNotNone(result)
        self.assertEqual(result["level"], "advise")
        self.assertEqual(result["type"], "branch-drift")

    def test_spec_deviation_maps_to_advise(self):
        policy = _make_policy()
        store = _make_store()
        ev = _event(
            live_modified_files=["payment.py"],
            prompt_summary="fix auth bug",
        )
        result = _run(policy.check(ev, None, {"store": store}))
        self.assertIsNotNone(result)
        self.assertEqual(result["level"], "advise")
        self.assertEqual(result["type"], "spec-deviation")

    def test_two_rules_escalate(self):
        from packages.advisor.state import SessionStore
        policy = _make_policy()
        store = SessionStore()
        sid = "sess-both"
        # Trigger branch-drift
        for i in range(20):
            store.record_event({
                "type": "file-write",
                "sessionId": sid,
                "branch": "feat/x",
                "repoRoot": "/repo",
                "live_modified_files": [f"f{i}.py"],
            })
        session = store.get_session(sid)
        # Prompt with a file not in summary (spec-deviation co-fires)
        ev = _event(
            sessionId=sid, branch="feat/x",
            live_modified_files=["secret.py"],
            prompt_summary="nothing about secret",
        )
        result = _run(policy.check(ev, session, {"store": store}))
        self.assertIsNotNone(result)
        self.assertEqual(result["level"], "escalate")
        self.assertIn("reason", result)
        self.assertIn("question", result)
        self.assertIn("branch-drift", result["reason"])
        self.assertIn("spec-deviation", result["reason"])

    def test_escalate_artifact_contains_combined_files(self):
        from packages.advisor.state import SessionStore
        policy = _make_policy()
        store = SessionStore()
        sid = "sess-both2"
        for i in range(20):
            store.record_event({
                "type": "file-write",
                "sessionId": sid,
                "branch": "feat/y",
                "repoRoot": "/repo",
                "live_modified_files": [f"g{i}.py"],
            })
        session = store.get_session(sid)
        ev = _event(
            sessionId=sid, branch="feat/y",
            live_modified_files=["mystery.py"],
            prompt_summary="irrelevant",
        )
        result = _run(policy.check(ev, session, {"store": store}))
        self.assertEqual(result["level"], "escalate")
        # escalate collects files from all firing rules
        self.assertIsInstance(result["files"], list)
