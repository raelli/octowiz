"""Tests for sandcastle runner — command construction and subprocess seams."""
import subprocess
import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))


class TestBuildContainerCmd(unittest.TestCase):

    def _build(self, **kwargs):
        from providers.sandcastle.runner import build_container_cmd
        defaults = dict(
            container_provider="docker",
            container_name="octowiz-abc123",
            image="sandbox:latest",
            cwd="/repo",
            task="run tests",
            branch=None,
        )
        defaults.update(kwargs)
        return build_container_cmd(**defaults)

    # ── happy paths ──────────────────────────────────────────────────────────

    def test_no_branch_uses_claude_list_form(self):
        cmd = self._build()
        self.assertIn("claude", cmd)
        self.assertIn("--print", cmd)
        self.assertIn("--", cmd)
        self.assertIn("run tests", cmd)
        # task must NOT be passed via shell
        self.assertNotIn("sh", cmd)

    def test_no_branch_task_is_last_element_after_separator(self):
        cmd = self._build(task="my task")
        # "--" sentinel must appear before the task
        sep_idx = cmd.index("--")
        self.assertEqual(cmd[-1], "my task")
        self.assertGreater(cmd.index("my task"), sep_idx)

    def test_with_branch_uses_sh_positional_params(self):
        cmd = self._build(branch="feat/my-branch")
        self.assertIn("sh", cmd)
        self.assertIn("-c", cmd)
        script = cmd[cmd.index("-c") + 1]
        self.assertIn("$1", script)
        self.assertIn("$2", script)

    def test_with_branch_passes_branch_and_task_as_positional_args(self):
        cmd = self._build(branch="feat/my-branch", task="run tests")
        self.assertIn("feat/my-branch", cmd)
        self.assertIn("run tests", cmd)

    def test_with_branch_branch_not_interpolated_into_script_string(self):
        """branch must be a positional arg, not interpolated into the sh -c script."""
        cmd = self._build(branch="feat/my-branch", task="run tests")
        script = cmd[cmd.index("-c") + 1]
        self.assertNotIn("feat/my-branch", script)

    def test_with_branch_checkout_does_not_use_pathspec_separator(self):
        """git checkout -- branch treats branch as a pathspec, not a ref — must not be present."""
        cmd = self._build(branch="feat/my-branch")
        script = cmd[cmd.index("-c") + 1]
        # 'checkout --' would make git treat the branch as a pathspec, breaking checkout
        self.assertNotIn("checkout --", script)
        self.assertIn("checkout", script)

    def test_container_name_in_name_flag(self):
        cmd = self._build(container_name="octowiz-xyz")
        self.assertTrue(any("--name=octowiz-xyz" in arg for arg in cmd))

    def test_cwd_mounted_as_rw_volume(self):
        cmd = self._build(cwd="/projects/myapp")
        volume_flag = next((a for a in cmd if "--volume=" in a), None)
        self.assertIsNotNone(volume_flag)
        self.assertIn("/projects/myapp:/projects/myapp", volume_flag)
        self.assertIn(":rw", volume_flag)

    def test_workdir_is_cwd(self):
        cmd = self._build(cwd="/projects/myapp")
        wd_idx = cmd.index("--workdir")
        self.assertEqual(cmd[wd_idx + 1], "/projects/myapp")

    def test_container_provider_is_first_element(self):
        cmd = self._build(container_provider="podman")
        self.assertEqual(cmd[0], "podman")

    def test_image_appears_in_command(self):
        cmd = self._build(image="ghcr.io/raelli/octowiz-sandbox:v1")
        self.assertIn("ghcr.io/raelli/octowiz-sandbox:v1", cmd)

    def test_run_subcommand_is_second_element(self):
        cmd = self._build()
        self.assertEqual(cmd[1], "run")

    def test_rm_flag_present(self):
        cmd = self._build()
        self.assertIn("--rm", cmd)

    def test_podman_also_supported(self):
        cmd = self._build(container_provider="podman")
        self.assertEqual(cmd[0], "podman")

    # ── validation ───────────────────────────────────────────────────────────

    def test_invalid_container_provider_raises(self):
        from providers.sandcastle.runner import build_container_cmd
        with self.assertRaises(ValueError) as ctx:
            build_container_cmd("kubectl", "n", "img", "/repo", "task")
        self.assertIn("kubectl", str(ctx.exception))

    def test_task_starting_with_dash_raises(self):
        from providers.sandcastle.runner import build_container_cmd
        with self.assertRaises(ValueError):
            build_container_cmd("docker", "n", "img", "/repo", "--inject")

    def test_branch_starting_with_dash_raises(self):
        from providers.sandcastle.runner import build_container_cmd
        with self.assertRaises(ValueError):
            build_container_cmd("docker", "n", "img", "/repo", "task", "--evil")

    def test_branch_with_spaces_raises(self):
        from providers.sandcastle.runner import build_container_cmd
        with self.assertRaises(ValueError):
            build_container_cmd("docker", "n", "img", "/repo", "task", "bad branch")

    def test_branch_with_valid_chars_accepted(self):
        from providers.sandcastle.runner import build_container_cmd
        cmd = build_container_cmd("docker", "n", "img", "/repo", "task", "feat/my-branch_v1.0")
        self.assertIn("feat/my-branch_v1.0", cmd)

    def test_no_subprocess_call_in_build(self):
        """build_container_cmd is a pure function -- must not invoke subprocess."""
        with patch("subprocess.run") as mock_run, patch("subprocess.Popen") as mock_popen:
            self._build()
        mock_run.assert_not_called()
        mock_popen.assert_not_called()


class TestEnvVarPassthrough(unittest.TestCase):
    """Env var passthrough -- name-only form so secrets never appear in argv."""

    def _build(self, **kwargs):
        from providers.sandcastle.runner import build_container_cmd
        defaults = dict(
            container_provider="docker",
            container_name="octowiz-abc123",
            image="sandbox:latest",
            cwd="/repo",
            task="run tests",
            branch=None,
        )
        defaults.update(kwargs)
        return build_container_cmd(**defaults)

    def test_anthropic_api_key_name_only_flag_present_no_branch(self):
        """--env ANTHROPIC_API_KEY must appear in the no-branch command."""
        cmd = self._build()
        env_idx = [i for i, x in enumerate(cmd) if x == "--env"]
        env_vars = [cmd[i + 1] for i in env_idx]
        self.assertIn("ANTHROPIC_API_KEY", env_vars)

    def test_anthropic_api_key_name_only_flag_present_with_branch(self):
        """--env ANTHROPIC_API_KEY must appear in the with-branch command."""
        cmd = self._build(branch="feat/my-branch")
        env_idx = [i for i, x in enumerate(cmd) if x == "--env"]
        env_vars = [cmd[i + 1] for i in env_idx]
        self.assertIn("ANTHROPIC_API_KEY", env_vars)

    def test_anthropic_base_url_name_only_flag_present(self):
        """--env ANTHROPIC_BASE_URL must appear (for LiteLLM proxy support)."""
        cmd = self._build()
        env_idx = [i for i, x in enumerate(cmd) if x == "--env"]
        env_vars = [cmd[i + 1] for i in env_idx]
        self.assertIn("ANTHROPIC_BASE_URL", env_vars)

    def test_aelli_auth_token_name_only_flag_present(self):
        """--env AELLI_AUTH_TOKEN must appear (for AELLI advisory calls inside container)."""
        cmd = self._build()
        env_idx = [i for i, x in enumerate(cmd) if x == "--env"]
        env_vars = [cmd[i + 1] for i in env_idx]
        self.assertIn("AELLI_AUTH_TOKEN", env_vars)

    def test_env_values_not_in_argv(self):
        """Secret values must never appear in the command line (name-only form)."""
        sentinel = "sk-ant-SUPERSECRET123"
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": sentinel}):
            cmd = self._build()
        self.assertNotIn(sentinel, cmd)
        # Also make sure no element contains 'ANTHROPIC_API_KEY=...'
        for arg in cmd:
            self.assertFalse(arg.startswith("ANTHROPIC_API_KEY="),
                             f"Found value-form env arg: {arg!r}")

    def test_env_flags_appear_before_image(self):
        """--env flags must come before the image name in the command."""
        cmd = self._build(image="sandbox:latest")
        image_idx = cmd.index("sandbox:latest")
        env_indices = [i for i, x in enumerate(cmd) if x == "--env"]
        self.assertTrue(all(i < image_idx for i in env_indices),
                        f"Some --env flags appear after image. cmd={cmd}")

    def test_cmd_identical_regardless_of_env_value(self):
        """Command structure must be identical regardless of host env value (name-only)."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "key-aaa"}):
            cmd_a = self._build()
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "key-bbb"}):
            cmd_b = self._build()
        self.assertEqual(cmd_a, cmd_b)

    def test_no_subprocess_call_in_build_with_env_passthrough(self):
        """build_container_cmd must remain a pure function after env passthrough added."""
        with patch("subprocess.run") as mock_run, patch("subprocess.Popen") as mock_popen:
            self._build()
        mock_run.assert_not_called()
        mock_popen.assert_not_called()


class TestStartContainerSeam(unittest.TestCase):

    def test_start_container_calls_popen(self):
        import tempfile
        log_path = os.path.join(tempfile.mkdtemp(), "out.log")
        mock_proc = MagicMock()

        with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
            from providers.sandcastle.runner import _start_container
            result = _start_container(["docker", "run", "img"], log_path)

        mock_popen.assert_called_once()
        call_args = mock_popen.call_args
        self.assertEqual(call_args.args[0], ["docker", "run", "img"])
        self.assertEqual(result, mock_proc)

    def test_start_container_opens_log_file_for_stdout(self):
        import tempfile
        log_dir = tempfile.mkdtemp()
        log_path = os.path.join(log_dir, "out.log")
        mock_proc = MagicMock()

        with patch("subprocess.Popen", return_value=mock_proc):
            from providers.sandcastle.runner import _start_container
            _start_container(["docker", "run", "img"], log_path)

        # Log file must have been created (opened for writing by _start_container)
        self.assertTrue(os.path.exists(log_path))


class TestRunCmdSeam(unittest.TestCase):

    def test_run_cmd_returns_returncode(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            from providers.sandcastle.runner import _run_cmd
            rc = _run_cmd(["docker", "kill", "octowiz-abc"])
        self.assertEqual(rc, 0)
        mock_run.assert_called_once_with(
            ["docker", "kill", "octowiz-abc"],
            capture_output=True,
            timeout=30,
        )

    def test_run_cmd_propagates_nonzero_returncode(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch("subprocess.run", return_value=mock_result):
            from providers.sandcastle.runner import _run_cmd
            rc = _run_cmd(["docker", "kill", "missing"])
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
