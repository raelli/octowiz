import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from octowiz_env import (
    MachineState,
    RepoState,
    load_machine_state,
    save_machine_state,
    load_repo_state,
    save_repo_state,
    init_machine_state,
    init_repo_state,
    _now_iso,
)
from octowiz_env import detect_plugin, detect_all_plugins, REQUIRED_PLUGINS
from octowiz_env import RepoScan, scan_repo
from octowiz_env import (
    CheckResult,
    run_live_check,
    dismiss_check,
    _litellm_env_ok,
    _litellm_cache_ok,
    _antfu_gap,
    CACHE_TTL_HOURS,
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


class TestPluginDetection(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.plugins_base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_absent_plugin_returns_false(self):
        self.assertFalse(detect_plugin("superpowers", self.plugins_base))

    def test_present_plugin_under_marketplace_returns_true(self):
        # simulate ~/.claude/plugins/cache/claude-plugins-official/superpowers/
        plugin_dir = self.plugins_base / "claude-plugins-official" / "superpowers" / "5.1.0"
        plugin_dir.mkdir(parents=True)
        self.assertTrue(detect_plugin("superpowers", self.plugins_base))

    def test_present_under_different_marketplace(self):
        plugin_dir = self.plugins_base / "integrahub" / "mattpo-skills" / "1.0.0"
        plugin_dir.mkdir(parents=True)
        self.assertTrue(detect_plugin("mattpo-skills", self.plugins_base))

    def test_detect_all_returns_dict_for_each_required(self):
        result = detect_all_plugins(REQUIRED_PLUGINS, self.plugins_base)
        self.assertEqual(set(result.keys()), set(REQUIRED_PLUGINS))
        self.assertTrue(all(v is False for v in result.values()))

    def test_detect_all_reflects_partial_install(self):
        (self.plugins_base / "integrahub" / "superpowers" / "1.0.0").mkdir(parents=True)
        result = detect_all_plugins(REQUIRED_PLUGINS, self.plugins_base)
        self.assertTrue(result["superpowers"])
        self.assertFalse(result["mattpo-skills"])
        self.assertFalse(result["antfu-skills"])

    def test_plugin_detected_without_version_subdir(self):
        # glob matches plugin_id at depth 1 under marketplace; no version dir needed
        plugin_dir = self.plugins_base / "integrahub" / "mattpo-skills"
        plugin_dir.mkdir(parents=True)
        self.assertTrue(detect_plugin("mattpo-skills", self.plugins_base))


class TestRepoScan(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, relpath: str, content: str = "") -> None:
        p = self.cwd / relpath
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)

    def test_empty_repo_has_no_agent_file(self):
        result = scan_repo(self.cwd)
        self.assertIsNone(result.agent_file)
        self.assertFalse(result.agent_has_skills_section)
        self.assertEqual(result.stack, "empty")

    def test_agents_md_takes_priority_over_claude_md(self):
        self._write("AGENTS.md", "## Agent skills\n- something")
        self._write("CLAUDE.md", "## Agent skills\n- other")
        result = scan_repo(self.cwd)
        self.assertEqual(result.agent_file, "AGENTS.md")

    def test_claude_md_used_when_no_agents_md(self):
        self._write("CLAUDE.md", "## Agent skills\n- skill")
        result = scan_repo(self.cwd)
        self.assertEqual(result.agent_file, "CLAUDE.md")

    def test_gemini_md_used_when_neither(self):
        self._write("GEMINI.md", "## Agent skills\n- skill")
        result = scan_repo(self.cwd)
        self.assertEqual(result.agent_file, "GEMINI.md")

    def test_agent_skills_section_detected(self):
        self._write("AGENTS.md", "# Project\n\n## Agent skills\n- /octowiz")
        result = scan_repo(self.cwd)
        self.assertTrue(result.agent_has_skills_section)

    def test_agent_skills_section_absent(self):
        self._write("AGENTS.md", "# Just a project doc")
        result = scan_repo(self.cwd)
        self.assertFalse(result.agent_has_skills_section)

    def test_typescript_vue_stack_detected(self):
        self._write("package.json", '{"dependencies": {"vue": "^3", "typescript": "^5"}}')
        result = scan_repo(self.cwd)
        self.assertEqual(result.stack, "ts_vue")

    def test_react_stack_detected(self):
        self._write("package.json", '{"dependencies": {"react": "^18"}}')
        result = scan_repo(self.cwd)
        self.assertEqual(result.stack, "react")

    def test_generic_js_when_no_ts_vue_react(self):
        self._write("package.json", '{"dependencies": {"lodash": "^4"}}')
        result = scan_repo(self.cwd)
        self.assertEqual(result.stack, "generic_js")

    def test_python_stack_detected(self):
        self._write("pyproject.toml", "[project]\nname = 'myapp'")
        result = scan_repo(self.cwd)
        self.assertEqual(result.stack, "python")

    def test_polyglot_when_both_package_json_and_pyproject(self):
        self._write("package.json", '{"dependencies": {"typescript": "^5"}}')
        self._write("pyproject.toml", "[project]\nname = 'myapp'")
        result = scan_repo(self.cwd)
        self.assertEqual(result.stack, "polyglot")

    def test_context_md_detected(self):
        self._write("CONTEXT.md", "# Context")
        result = scan_repo(self.cwd)
        self.assertTrue(result.has_context_md)

    def test_adr_dir_detected(self):
        self._write("docs/adr/0001-example.md", "# ADR")
        result = scan_repo(self.cwd)
        self.assertTrue(result.has_adr)

    def test_no_context_or_adr(self):
        result = scan_repo(self.cwd)
        self.assertFalse(result.has_context_md)
        self.assertFalse(result.has_adr)

    def test_typescript_only_is_generic_js_not_ts_vue(self):
        self._write("package.json", '{"devDependencies": {"typescript": "^5"}}')
        result = scan_repo(self.cwd)
        self.assertEqual(result.stack, "generic_js")

    def test_has_github_remote_when_github_in_output(self):
        from unittest.mock import patch, MagicMock
        mock_result = MagicMock()
        mock_result.stdout = "origin\tgit@github.com:user/repo.git (fetch)\n"
        with patch("subprocess.run", return_value=mock_result):
            result = scan_repo(self.cwd)
        self.assertTrue(result.has_github_remote)

    def test_no_github_remote_when_not_in_output(self):
        from unittest.mock import patch, MagicMock
        mock_result = MagicMock()
        mock_result.stdout = "origin\tgit@gitlab.com:user/repo.git (fetch)\n"
        with patch("subprocess.run", return_value=mock_result):
            result = scan_repo(self.cwd)
        self.assertFalse(result.has_github_remote)

    def test_no_github_remote_when_subprocess_fails(self):
        from unittest.mock import patch
        with patch("subprocess.run", side_effect=FileNotFoundError("git not found")):
            result = scan_repo(self.cwd)
        self.assertFalse(result.has_github_remote)


class TestLiveCheck(unittest.TestCase):
    def setUp(self):
        self.repo_tmp = tempfile.TemporaryDirectory()
        self.state_tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self.repo_tmp.name)
        self.machine_state_path = Path(self.state_tmp.name) / "machine-state.json"
        self.plugins_base = Path(self.state_tmp.name) / "plugins"

    def tearDown(self):
        self.repo_tmp.cleanup()
        self.state_tmp.cleanup()

    # --- _litellm_env_ok ---

    def test_litellm_env_ok_requires_base_url_and_key(self):
        # Test with both vars set
        with patch.dict(os.environ, {
            "LITELLM_BASE_URL": "http://localhost:4000",
            "LITELLM_ADMIN_API_KEY": "sk-test",
        }, clear=False):
            self.assertTrue(_litellm_env_ok())

    def test_litellm_env_ok_accepts_litellm_api_key(self):
        env = {"LITELLM_BASE_URL": "http://localhost:4000", "LITELLM_API_KEY": "sk-test"}
        # Remove LITELLM_ADMIN_API_KEY if present
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("LITELLM_ADMIN_API_KEY", None)
            self.assertTrue(_litellm_env_ok())

    def test_litellm_env_missing_base_url_returns_false(self):
        with patch.dict(os.environ, {"LITELLM_ADMIN_API_KEY": "sk-test"}, clear=False):
            os.environ.pop("LITELLM_BASE_URL", None)
            self.assertFalse(_litellm_env_ok())

    def test_litellm_env_missing_api_key_returns_false(self):
        with patch.dict(os.environ, {"LITELLM_BASE_URL": "http://localhost:4000"}, clear=False):
            os.environ.pop("LITELLM_ADMIN_API_KEY", None)
            os.environ.pop("LITELLM_API_KEY", None)
            self.assertFalse(_litellm_env_ok())

    # --- _litellm_cache_ok ---

    def test_litellm_cache_ok_none_state_returns_false(self):
        self.assertFalse(_litellm_cache_ok(None))

    def test_litellm_cache_ok_absent_timestamp_returns_false(self):
        state = MachineState()
        # routing_verified_at is None by default
        self.assertFalse(_litellm_cache_ok(state))

    def test_litellm_cache_ok_fresh_timestamp_returns_true(self):
        state = MachineState()
        state.litellm["routing_verified_at"] = _now_iso()  # just now
        self.assertTrue(_litellm_cache_ok(state))

    def test_litellm_cache_ok_stale_timestamp_returns_false(self):
        from datetime import timedelta
        state = MachineState()
        stale = datetime.now(timezone.utc) - timedelta(hours=25)
        state.litellm["routing_verified_at"] = stale.strftime("%Y-%m-%dT%H:%M:%SZ")
        self.assertFalse(_litellm_cache_ok(state))

    # --- _antfu_gap ---

    def test_antfu_gap_python_stack_returns_false(self):
        scan = RepoScan(agent_file=None, agent_has_skills_section=False,
                        stack="python", has_context_md=False, has_adr=False, has_github_remote=False)
        self.assertFalse(_antfu_gap(scan, None))

    def test_antfu_gap_ts_vue_no_state_returns_true(self):
        scan = RepoScan(agent_file=None, agent_has_skills_section=False,
                        stack="ts_vue", has_context_md=False, has_adr=False, has_github_remote=False)
        self.assertTrue(_antfu_gap(scan, None))

    def test_antfu_gap_ts_vue_setup_done_returns_false(self):
        scan = RepoScan(agent_file=None, agent_has_skills_section=False,
                        stack="ts_vue", has_context_md=False, has_adr=False, has_github_remote=False)
        repo_state = RepoState(antfu_setup=True)
        self.assertFalse(_antfu_gap(scan, repo_state))

    def test_antfu_gap_ts_vue_deferred_returns_false(self):
        scan = RepoScan(agent_file=None, agent_has_skills_section=False,
                        stack="ts_vue", has_context_md=False, has_adr=False, has_github_remote=False)
        repo_state = RepoState(antfu_deferred=True)
        self.assertFalse(_antfu_gap(scan, repo_state))

    def test_antfu_gap_polyglot_not_done_returns_true(self):
        scan = RepoScan(agent_file=None, agent_has_skills_section=False,
                        stack="polyglot", has_context_md=False, has_adr=False, has_github_remote=False)
        self.assertTrue(_antfu_gap(scan, None))

    # --- run_live_check ---

    def test_run_live_check_all_gaps_on_fresh_environment(self):
        # No plugins, no env vars, no machine state, ts_vue stack triggers antfu
        (self.cwd / "package.json").write_text('{"dependencies": {"vue": "^3"}}')
        with patch.dict(os.environ, {}, clear=True):
            result = run_live_check(self.cwd, self.machine_state_path, self.plugins_base)
        self.assertTrue(result.machine_state_absent)
        self.assertTrue(result.repo_state_absent)
        self.assertIn("plugin_superpowers", result.hard_gaps)
        self.assertIn("plugin_mattpo-skills", result.hard_gaps)
        self.assertIn("plugin_antfu-skills", result.hard_gaps)
        self.assertIn("litellm_env", result.hard_gaps)
        self.assertIn("litellm_cache", result.hard_gaps)
        self.assertIn("antfu", result.hard_gaps)
        self.assertIn("agent_file", result.advisory_gaps)

    def test_run_live_check_no_gaps_when_all_present(self):
        # All plugins present
        for plugin_id in REQUIRED_PLUGINS:
            (self.plugins_base / "marketplace" / plugin_id).mkdir(parents=True)
        # Set env vars
        # Create machine state with fresh routing_verified_at
        machine_state = MachineState(first_seen=_now_iso())
        machine_state.litellm["routing_verified_at"] = _now_iso()
        save_machine_state(machine_state, self.machine_state_path)
        # Create repo state with antfu done
        repo_state = RepoState(antfu_setup=True)
        save_repo_state(repo_state, self.cwd)
        # Agent file with skills section
        (self.cwd / "AGENTS.md").write_text("## Agent skills\n- /octowiz")
        # Python stack (no antfu needed)
        (self.cwd / "pyproject.toml").write_text("[project]\nname='test'")

        with patch.dict(os.environ, {
            "LITELLM_BASE_URL": "http://localhost:4000",
            "LITELLM_ADMIN_API_KEY": "sk-test",
        }, clear=False):
            result = run_live_check(self.cwd, self.machine_state_path, self.plugins_base)

        self.assertFalse(result.machine_state_absent)
        self.assertFalse(result.repo_state_absent)
        self.assertEqual(result.hard_gaps, [])
        self.assertEqual(result.advisory_gaps, [])

    def test_run_live_check_dismissed_check_excluded(self):
        # Dismiss litellm_env for this cwd
        from unittest.mock import patch as mpatch, MagicMock
        mock_result = MagicMock()
        mock_result.stdout = str(self.cwd) + "\n"
        machine_state = MachineState(first_seen=_now_iso())
        machine_state.dismissed_checks[str(self.cwd)] = ["litellm_env"]
        save_machine_state(machine_state, self.machine_state_path)

        with mpatch("subprocess.run", return_value=mock_result):
            with patch.dict(os.environ, {}, clear=True):
                result = run_live_check(self.cwd, self.machine_state_path, self.plugins_base)

        self.assertNotIn("litellm_env", result.hard_gaps)

    def test_run_live_check_advisory_mattpo_when_agent_has_no_skills(self):
        # Agent file exists but no ## Agent skills section
        (self.cwd / "AGENTS.md").write_text("# Just a project doc\nNo skills here.")
        # All plugins present, env vars set, fresh litellm cache, python stack
        for plugin_id in REQUIRED_PLUGINS:
            (self.plugins_base / "marketplace" / plugin_id).mkdir(parents=True)
        machine_state = MachineState(first_seen=_now_iso())
        machine_state.litellm["routing_verified_at"] = _now_iso()
        save_machine_state(machine_state, self.machine_state_path)
        (self.cwd / "pyproject.toml").write_text("[project]\nname='test'")

        with patch.dict(os.environ, {
            "LITELLM_BASE_URL": "http://localhost:4000",
            "LITELLM_ADMIN_API_KEY": "sk-test",
        }, clear=False):
            result = run_live_check(self.cwd, self.machine_state_path, self.plugins_base)

        self.assertIn("mattpo_skills_setup", result.advisory_gaps)
        self.assertNotIn("agent_file", result.advisory_gaps)

    # --- dismiss_check ---

    def test_dismiss_check_records_in_machine_state(self):
        from unittest.mock import patch as mpatch, MagicMock
        mock_result = MagicMock()
        mock_result.stdout = "/some/repo\n"
        with mpatch("subprocess.run", return_value=mock_result):
            dismiss_check("litellm_env", self.cwd, self.machine_state_path)
        state = load_machine_state(self.machine_state_path)
        self.assertIn("litellm_env", state.dismissed_checks.get("/some/repo", []))

    def test_dismiss_check_idempotent(self):
        from unittest.mock import patch as mpatch, MagicMock
        mock_result = MagicMock()
        mock_result.stdout = "/some/repo\n"
        with mpatch("subprocess.run", return_value=mock_result):
            dismiss_check("litellm_env", self.cwd, self.machine_state_path)
            dismiss_check("litellm_env", self.cwd, self.machine_state_path)
        state = load_machine_state(self.machine_state_path)
        self.assertEqual(state.dismissed_checks["/some/repo"].count("litellm_env"), 1)
