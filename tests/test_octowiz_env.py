import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

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
)
from octowiz_env import detect_plugin, detect_all_plugins, REQUIRED_PLUGINS
from octowiz_env import RepoScan, scan_repo


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
