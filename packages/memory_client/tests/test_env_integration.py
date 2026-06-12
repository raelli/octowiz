"""
Integration test for the full first-run setup sequence.

Simulates a developer's machine from scratch:
  1. First /octowiz invocation in a new repo — all gaps present
  2. Developer installs plugins, sets env vars, configures litellm cache
  3. Invokes /octowiz again — no gaps, normal workflow proceeds
  4. Second invocation is a no-op (state file preserved)
  5. Plugin removed → live check re-detects it on next invocation
"""
import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

from packages.memory_client.env import (
    MachineState, RepoState,
    load_machine_state, save_machine_state,
    load_repo_state, save_repo_state,
    init_machine_state, init_repo_state,
    run_live_check, dismiss_check,
    REQUIRED_PLUGINS, MACHINE_STATE_PATH, PLUGINS_CACHE_BASE,
    _now_iso,
)


def _git_mock(repo_root: str):
    """Return a subprocess.run mock that returns repo_root for git rev-parse."""
    m = MagicMock()
    m.returncode = 0
    m.stdout = repo_root + "\n"
    return m


class TestFirstRunIntegration(unittest.TestCase):
    def setUp(self):
        self.repo_tmp = tempfile.TemporaryDirectory()
        self.state_tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self.repo_tmp.name)
        self.machine_state_path = Path(self.state_tmp.name) / "machine-state.json"
        self.plugins_base = Path(self.state_tmp.name) / "plugins"

    def tearDown(self):
        self.repo_tmp.cleanup()
        self.state_tmp.cleanup()

    def test_fresh_environment_has_all_gaps(self):
        # No plugins, no env vars, no machine state, no repo state, python stack (no antfu)
        (self.cwd / "pyproject.toml").write_text("[project]\nname='myapp'")

        with patch("subprocess.run", return_value=_git_mock(str(self.cwd))):
            with patch.dict(os.environ, {}, clear=True):
                result = run_live_check(self.cwd, self.machine_state_path, self.plugins_base)

        self.assertTrue(result.machine_state_absent)
        self.assertTrue(result.repo_state_absent)
        # All three plugin gaps
        self.assertIn("plugin_superpowers", result.hard_gaps)
        self.assertIn("plugin_mattpocock-skills", result.hard_gaps)
        self.assertIn("plugin_antfu-skills", result.hard_gaps)
        # Both litellm gaps
        self.assertIn("litellm_env", result.hard_gaps)
        self.assertIn("litellm_cache", result.hard_gaps)
        # Python stack → no antfu gap
        self.assertNotIn("antfu", result.hard_gaps)
        # Advisory: no agent file
        self.assertIn("agent_file", result.advisory_gaps)

    def test_no_gaps_after_complete_setup(self):
        # Create all plugin dirs
        for plugin_id in REQUIRED_PLUGINS:
            (self.plugins_base / "official" / plugin_id).mkdir(parents=True)

        # Create machine state with fresh litellm cache
        machine_state = init_machine_state(self.machine_state_path)
        machine_state.litellm["routing_verified_at"] = _now_iso()
        save_machine_state(machine_state, self.machine_state_path)

        # Create repo state with antfu done (not needed for python, but set it anyway)
        repo_state = init_repo_state(self.cwd)

        # Agent file with skills section
        (self.cwd / "AGENTS.md").write_text("## Agent skills\n- /octowiz\n")

        # Python stack
        (self.cwd / "pyproject.toml").write_text("[project]\nname='myapp'")

        with patch("subprocess.run", return_value=_git_mock(str(self.cwd))):
            with patch.dict(os.environ, {
                "LITELLM_BASE_URL": "http://localhost:4000",
                "LITELLM_ADMIN_API_KEY": "sk-test",
            }, clear=False):
                result = run_live_check(self.cwd, self.machine_state_path, self.plugins_base)

        self.assertFalse(result.machine_state_absent)
        self.assertFalse(result.repo_state_absent)
        self.assertEqual(result.hard_gaps, [])
        self.assertEqual(result.advisory_gaps, [])

    def test_live_check_does_not_mutate_state_files(self):
        # Set up complete environment
        for plugin_id in REQUIRED_PLUGINS:
            (self.plugins_base / "official" / plugin_id).mkdir(parents=True)
        machine_state = init_machine_state(self.machine_state_path)
        machine_state.litellm["routing_verified_at"] = _now_iso()
        machine_state.plugins = {pid: "verified" for pid in REQUIRED_PLUGINS}
        save_machine_state(machine_state, self.machine_state_path)
        (self.cwd / "AGENTS.md").write_text("## Agent skills\n- /octowiz\n")
        (self.cwd / "pyproject.toml").write_text("[project]\nname='myapp'")

        state_mtime_before = self.machine_state_path.stat().st_mtime

        with patch("subprocess.run", return_value=_git_mock(str(self.cwd))):
            with patch.dict(os.environ, {
                "LITELLM_BASE_URL": "http://localhost:4000",
                "LITELLM_ADMIN_API_KEY": "sk-test",
            }, clear=False):
                run_live_check(self.cwd, self.machine_state_path, self.plugins_base)

        state_mtime_after = self.machine_state_path.stat().st_mtime
        self.assertEqual(state_mtime_before, state_mtime_after,
                         "run_live_check should not write to machine-state.json")

    def test_plugin_removal_detected_on_next_check(self):
        # Start with all plugins
        for plugin_id in REQUIRED_PLUGINS:
            (self.plugins_base / "official" / plugin_id).mkdir(parents=True)
        machine_state = init_machine_state(self.machine_state_path)
        machine_state.litellm["routing_verified_at"] = _now_iso()
        save_machine_state(machine_state, self.machine_state_path)
        (self.cwd / "AGENTS.md").write_text("## Agent skills\n- /octowiz\n")
        (self.cwd / "pyproject.toml").write_text("[project]\nname='myapp'")

        # Verify: clean
        with patch("subprocess.run", return_value=_git_mock(str(self.cwd))):
            with patch.dict(os.environ, {
                "LITELLM_BASE_URL": "http://localhost:4000",
                "LITELLM_ADMIN_API_KEY": "sk-test",
            }, clear=False):
                result1 = run_live_check(self.cwd, self.machine_state_path, self.plugins_base)
        self.assertEqual(result1.hard_gaps, [])

        # Developer removes superpowers plugin
        shutil.rmtree(self.plugins_base / "official" / "superpowers")

        # Next check detects the gap
        with patch("subprocess.run", return_value=_git_mock(str(self.cwd))):
            with patch.dict(os.environ, {
                "LITELLM_BASE_URL": "http://localhost:4000",
                "LITELLM_ADMIN_API_KEY": "sk-test",
            }, clear=False):
                result2 = run_live_check(self.cwd, self.machine_state_path, self.plugins_base)
        self.assertIn("plugin_superpowers", result2.hard_gaps)
        self.assertNotIn("plugin_mattpocock-skills", result2.hard_gaps)

    def test_dismissed_check_survives_reinvocation(self):
        # Dismiss litellm_env
        with patch("subprocess.run", return_value=_git_mock(str(self.cwd))):
            dismiss_check("litellm_env", self.cwd, self.machine_state_path)

        # Re-invoke — litellm_env should not appear even though env vars are absent
        with patch("subprocess.run", return_value=_git_mock(str(self.cwd))):
            with patch.dict(os.environ, {}, clear=True):
                result = run_live_check(self.cwd, self.machine_state_path, self.plugins_base)

        self.assertNotIn("litellm_env", result.hard_gaps)
        # Other gaps still present
        self.assertIn("litellm_cache", result.hard_gaps)

    def test_stale_litellm_cache_triggers_gap(self):
        for plugin_id in REQUIRED_PLUGINS:
            (self.plugins_base / "official" / plugin_id).mkdir(parents=True)
        machine_state = init_machine_state(self.machine_state_path)
        stale_ts = datetime.now(timezone.utc) - timedelta(hours=25)
        machine_state.litellm["routing_verified_at"] = stale_ts.strftime("%Y-%m-%dT%H:%M:%SZ")
        save_machine_state(machine_state, self.machine_state_path)
        (self.cwd / "AGENTS.md").write_text("## Agent skills\n- /octowiz\n")
        (self.cwd / "pyproject.toml").write_text("[project]\nname='myapp'")

        with patch("subprocess.run", return_value=_git_mock(str(self.cwd))):
            with patch.dict(os.environ, {
                "LITELLM_BASE_URL": "http://localhost:4000",
                "LITELLM_ADMIN_API_KEY": "sk-test",
            }, clear=False):
                result = run_live_check(self.cwd, self.machine_state_path, self.plugins_base)

        self.assertIn("litellm_cache", result.hard_gaps)
        self.assertNotIn("litellm_env", result.hard_gaps)
        self.assertNotIn("plugin_superpowers", result.hard_gaps)

    def test_ts_vue_repo_antfu_gap_resolved_by_state(self):
        (self.cwd / "package.json").write_text('{"dependencies": {"vue": "^3"}}')

        # Without any state → antfu gap
        with patch("subprocess.run", return_value=_git_mock(str(self.cwd))):
            with patch.dict(os.environ, {}, clear=True):
                result1 = run_live_check(self.cwd, self.machine_state_path, self.plugins_base)
        self.assertIn("antfu", result1.hard_gaps)

        # After antfu setup done
        repo_state = init_repo_state(self.cwd)
        repo_state.antfu_setup = True
        save_repo_state(repo_state, self.cwd)

        with patch("subprocess.run", return_value=_git_mock(str(self.cwd))):
            with patch.dict(os.environ, {}, clear=True):
                result2 = run_live_check(self.cwd, self.machine_state_path, self.plugins_base)
        self.assertNotIn("antfu", result2.hard_gaps)

    def test_new_machine_cloned_repo_has_machine_gaps_only(self):
        # Simulate a committed setup-state.json (repo setup already done)
        repo_state = RepoState(
            created_at="2026-05-20T00:00:00Z",
            mattpocock_setup=True,
            antfu_relevant=False,
            antfu_setup=False,
            antfu_deferred=False,
        )
        save_repo_state(repo_state, self.cwd)
        (self.cwd / "AGENTS.md").write_text("## Agent skills\n- /octowiz\n")
        (self.cwd / "pyproject.toml").write_text("[project]\nname='myapp'")
        # NO machine-state.json (new machine)

        with patch("subprocess.run", return_value=_git_mock(str(self.cwd))):
            with patch.dict(os.environ, {}, clear=True):
                result = run_live_check(self.cwd, self.machine_state_path, self.plugins_base)

        self.assertTrue(result.machine_state_absent)
        self.assertFalse(result.repo_state_absent)
        # Only machine-level gaps
        self.assertIn("plugin_superpowers", result.hard_gaps)
        self.assertIn("litellm_env", result.hard_gaps)
        self.assertIn("litellm_cache", result.hard_gaps)
        # No repo-level gaps (mattpocock_setup=True, python stack → no antfu)
        self.assertNotIn("antfu", result.hard_gaps)
        self.assertEqual(result.advisory_gaps, [])


if __name__ == "__main__":
    unittest.main()
