"""Unit tests for RulesAdvisor.advise_all()."""
import asyncio
import unittest


def _run(coro):
    return asyncio.run(coro)


class MockStore:
    def find_conflicts(self, repo, files, session_id):
        return []


class MockSession:
    def __init__(self, branch="main", events=None):
        self.branch = branch
        self.events = events or []


CTX = {"store": MockStore()}


class TestAdviseAll(unittest.TestCase):

    def test_returns_empty_list_when_no_rules_fire(self):
        from packages.advisor.rules import RulesAdvisor
        advisor = RulesAdvisor()
        event = {"type": "file-edit", "sessionId": "s1", "repoRoot": "/r",
                 "branch": "main", "live_modified_files": ["a.py"]}
        results = _run(advisor.advise_all(event, None, CTX))
        self.assertEqual(results, [])

    def test_returns_all_matching_rules(self):
        from packages.advisor.rules import RulesAdvisor, BRANCH_DRIFT_THRESHOLD

        class ConflictStore:
            def find_conflicts(self, repo, files, sid):
                return [{"file": "a.py", "otherSessionId": "s2", "otherBranch": "feat/b"}]

        advisor = RulesAdvisor()
        many_events = [{"type": "file-edit"}] * BRANCH_DRIFT_THRESHOLD
        session = MockSession(branch="feat/a", events=many_events)
        event = {
            "type": "prompt", "sessionId": "s1", "branch": "feat/a",
            "repoRoot": "/r", "live_modified_files": ["a.py"],
            "prompt_summary": "unrelated description",
        }
        ctx = {"store": ConflictStore()}
        results = _run(advisor.advise_all(event, session, ctx))
        types = {r["type"] for r in results}
        self.assertIn("file-conflict", types)
        self.assertIn("branch-drift", types)
        self.assertIn("spec-deviation", types)
        self.assertEqual(len(results), 3)

    def test_returns_single_result_when_one_rule_fires(self):
        from packages.advisor.rules import RulesAdvisor, BRANCH_DRIFT_THRESHOLD
        advisor = RulesAdvisor()
        many_events = [{"type": "file-edit"}] * BRANCH_DRIFT_THRESHOLD
        session = MockSession(branch="main", events=many_events)
        event = {"type": "prompt", "sessionId": "s1", "repoRoot": "/r",
                 "branch": "main", "live_modified_files": [], "prompt_summary": ""}
        results = _run(advisor.advise_all(event, session, CTX))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["type"], "branch-drift")
