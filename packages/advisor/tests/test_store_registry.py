"""Unit tests for StoreRegistry."""
import unittest


class TestStoreRegistry(unittest.TestCase):

    def _registry(self):
        from packages.advisor.state import StoreRegistry
        return StoreRegistry()

    def _session_store(self):
        from packages.advisor.state import SessionStore
        return SessionStore()

    def test_get_creates_new_store_for_unknown_session(self):
        registry = self._registry()
        store = registry.get("sess-A")
        from packages.advisor.state import SessionStore
        self.assertIsInstance(store, SessionStore)
        self.assertEqual(len(registry), 1)

    def test_get_returns_same_store_for_same_session_id(self):
        registry = self._registry()
        store1 = registry.get("sess-A")
        store2 = registry.get("sess-A")
        self.assertIs(store1, store2)

    def test_drop_removes_store(self):
        registry = self._registry()
        registry.get("sess-A")
        self.assertEqual(len(registry), 1)
        registry.drop("sess-A")
        self.assertEqual(len(registry), 0)

    def test_drop_then_get_returns_fresh_empty_store(self):
        registry = self._registry()
        store = registry.get("sess-A")
        store.record_event({
            "type": "prompt", "sessionId": "sess-A", "branch": "feat/a",
            "repoRoot": "/repo", "live_modified_files": ["foo.py"],
        })
        registry.drop("sess-A")
        fresh = registry.get("sess-A")
        # The fresh store has no session data
        self.assertIsNone(fresh.get_session("sess-A"))

    def test_drop_removes_session_from_conflict_index(self):
        """After drop, the session must not appear as a conflict for other sessions."""
        registry = self._registry()
        store_a = registry.get("sess-A")
        store_a.record_event({
            "type": "prompt", "sessionId": "sess-A", "branch": "feat/a",
            "repoRoot": "/repo", "live_modified_files": ["src/core.py"],
        })
        registry.drop("sess-A")

        store_b = registry.get("sess-B")
        conflicts = store_b.find_conflicts("/repo", ["src/core.py"], "sess-B")
        self.assertEqual(conflicts, [])

    def test_cross_session_conflict_detection_via_shared_conflict_index(self):
        """Two sessions in the same registry can detect each other's file conflicts."""
        registry = self._registry()
        store_a = registry.get("sess-A")
        store_b = registry.get("sess-B")

        store_a.record_event({
            "type": "prompt", "sessionId": "sess-A", "branch": "feat/a",
            "repoRoot": "/repo", "live_modified_files": ["src/payment.py"],
        })
        conflicts = store_b.find_conflicts("/repo", ["src/payment.py"], "sess-B")
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["file"], "src/payment.py")
        self.assertEqual(conflicts[0]["otherSessionId"], "sess-A")

    def test_clear_removes_all_stores(self):
        registry = self._registry()
        registry.get("sess-A")
        registry.get("sess-B")
        self.assertEqual(len(registry), 2)
        registry.clear()
        self.assertEqual(len(registry), 0)

    def test_clear_resets_conflict_index(self):
        """After clear(), sessions that were tracked no longer produce conflicts."""
        registry = self._registry()
        store_a = registry.get("sess-A")
        store_a.record_event({
            "type": "prompt", "sessionId": "sess-A", "branch": "feat/a",
            "repoRoot": "/repo", "live_modified_files": ["src/core.py"],
        })
        registry.clear()

        store_b = registry.get("sess-B")
        conflicts = store_b.find_conflicts("/repo", ["src/core.py"], "sess-B")
        self.assertEqual(conflicts, [])

    def test_drop_nonexistent_session_does_not_raise(self):
        registry = self._registry()
        registry.drop("nonexistent")  # should not raise

    def test_module_level_registry_is_store_registry_instance(self):
        from packages.advisor.state import _registry, StoreRegistry
        self.assertIsInstance(_registry, StoreRegistry)


class TestHandleSessionEnd(unittest.TestCase):
    """Tests for the Python handle_session_end() integration."""

    def test_handle_session_end_drops_session_from_registry(self):
        import os
        import sys
        _A2A_DIR = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
            "apps", "a2a-agent"
        )
        _ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        if _A2A_DIR not in sys.path:
            sys.path.insert(0, _A2A_DIR)
        if _ROOT_DIR not in sys.path:
            sys.path.insert(0, _ROOT_DIR)

        from packages.advisor.state import StoreRegistry
        from packages.advisor.state import SessionStore

        # Import handle_session_end from the capability module
        # We use importlib to avoid module-level state pollution
        import importlib
        import capabilities.advise as adv_mod
        importlib.reload(adv_mod)

        registry = StoreRegistry()
        # Populate a session
        store = registry.get("sess-test")
        store.record_event({
            "type": "prompt", "sessionId": "sess-test", "branch": "feat/x",
            "repoRoot": "/repo", "live_modified_files": ["a.py"],
        })
        self.assertEqual(len(registry), 1)

        adv_mod.handle_session_end("sess-test", registry)
        self.assertEqual(len(registry), 0)
