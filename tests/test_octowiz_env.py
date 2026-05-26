import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import octowiz_env
from octowiz_env import (
    MachineState,
    RepoState,
    load_machine_state,
    save_machine_state,
    load_repo_state,
    save_repo_state,
    init_machine_state,
    init_repo_state,
)


class TestMachineStateIO(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "machine-state.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_load_absent_returns_none(self):
        self.assertIsNone(load_machine_state(self.path))

    def test_save_and_load_roundtrip(self):
        state = MachineState(
            first_seen="2026-05-26T10:00:00Z",
            plugins={"superpowers": "verified"},
            litellm={"routing_verified_at": None, "planner_verified_at": None,
                     "implementer_verified_at": None, "reviewer_verified_at": None},
            dismissed_checks={},
        )
        save_machine_state(state, self.path)
        loaded = load_machine_state(self.path)
        self.assertEqual(loaded.plugins, {"superpowers": "verified"})
        self.assertEqual(loaded.dismissed_checks, {})

    def test_init_creates_skeleton_when_absent(self):
        state = init_machine_state(self.path)
        self.assertTrue(self.path.exists())
        self.assertIn("first_seen", json.loads(self.path.read_text()))
        self.assertEqual(state.plugins, {})

    def test_init_returns_existing_without_overwrite(self):
        state = init_machine_state(self.path)
        state.plugins["superpowers"] = "verified"
        save_machine_state(state, self.path)
        state2 = init_machine_state(self.path)
        self.assertEqual(state2.plugins, {"superpowers": "verified"})


class TestRepoStateIO(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_load_absent_returns_none(self):
        self.assertIsNone(load_repo_state(self.cwd))

    def test_save_and_load_roundtrip(self):
        state = RepoState(
            created_at="2026-05-26T10:00:00Z",
            mattpocock_setup=False,
            antfu_relevant=None,
            antfu_setup=False,
            antfu_deferred=False,
        )
        save_repo_state(state, self.cwd)
        loaded = load_repo_state(self.cwd)
        self.assertFalse(loaded.mattpocock_setup)
        self.assertIsNone(loaded.antfu_relevant)

    def test_init_creates_dir_and_files(self):
        state = init_repo_state(self.cwd)
        self.assertTrue((self.cwd / ".octowiz" / "setup-state.json").exists())
        self.assertFalse(state.antfu_setup)

    def test_init_returns_existing_without_overwrite(self):
        state = init_repo_state(self.cwd)
        state.mattpocock_setup = True
        save_repo_state(state, self.cwd)
        state2 = init_repo_state(self.cwd)
        self.assertTrue(state2.mattpocock_setup)
