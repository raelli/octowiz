"""Unit tests for InvocationPolicy."""
import unittest


class TestInvocationPolicy(unittest.TestCase):

    def _policy(self):
        from packages.advisor.policy import InvocationPolicy
        return InvocationPolicy()

    def test_empty_results_returns_none(self):
        decision = self._policy().decide([])
        self.assertIsNone(decision)

    def test_file_conflict_maps_to_intervene(self):
        result = [{"type": "file-conflict", "message": "conflict on a.py", "files": ["a.py"]}]
        decision = self._policy().decide(result)
        self.assertEqual(decision.level, "intervene")
        self.assertEqual(decision.type, "file-conflict")
        self.assertEqual(decision.message, "conflict on a.py")

    def test_branch_drift_maps_to_advise(self):
        result = [{"type": "branch-drift", "message": "20 changes", "files": []}]
        decision = self._policy().decide(result)
        self.assertEqual(decision.level, "advise")
        self.assertEqual(decision.type, "branch-drift")

    def test_spec_deviation_maps_to_advise(self):
        result = [{"type": "spec-deviation", "message": "unexpected file", "files": ["x.py"]}]
        decision = self._policy().decide(result)
        self.assertEqual(decision.level, "advise")
        self.assertEqual(decision.type, "spec-deviation")

    def test_unknown_type_defaults_to_advise(self):
        result = [{"type": "custom-rule", "message": "something", "files": []}]
        decision = self._policy().decide(result)
        self.assertEqual(decision.level, "advise")
        self.assertEqual(decision.type, "custom-rule")

    def test_two_rules_firing_escalates(self):
        results = [
            {"type": "file-conflict", "message": "conflict on a.py", "files": ["a.py"]},
            {"type": "branch-drift",  "message": "20 changes", "files": []},
        ]
        decision = self._policy().decide(results)
        self.assertEqual(decision.level, "escalate")
        self.assertEqual(decision.type, "multi-rule")
        self.assertIn("file-conflict", decision.reason)
        self.assertIn("branch-drift", decision.reason)
        self.assertNotEqual(decision.question, "")

    def test_three_rules_firing_escalates(self):
        results = [
            {"type": "file-conflict",  "message": "m1", "files": []},
            {"type": "branch-drift",   "message": "m2", "files": []},
            {"type": "spec-deviation", "message": "m3", "files": []},
        ]
        decision = self._policy().decide(results)
        self.assertEqual(decision.level, "escalate")

    def test_escalate_decision_has_reason_and_question(self):
        results = [
            {"type": "file-conflict", "message": "m1", "files": []},
            {"type": "spec-deviation", "message": "m2", "files": []},
        ]
        decision = self._policy().decide(results)
        self.assertIsInstance(decision.reason, str)
        self.assertGreater(len(decision.reason), 0)
        self.assertIsInstance(decision.question, str)
        self.assertGreater(len(decision.question), 0)

    def test_non_escalate_decision_has_empty_reason_and_question(self):
        result = [{"type": "branch-drift", "message": "20 changes", "files": []}]
        decision = self._policy().decide(result)
        self.assertEqual(decision.reason, "")
        self.assertEqual(decision.question, "")
