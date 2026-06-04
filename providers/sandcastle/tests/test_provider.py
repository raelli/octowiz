"""Tests for SandcastleProvider — mocks _start_container and _run_cmd at seams.

Patch paths use `providers.sandcastle.provider.*` (where names are imported/used),
not `providers.sandcastle.runner.*` (where they are defined).
"""
import os
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

_PATCH_START = "providers.sandcastle.provider._start_container"
_PATCH_RUN = "providers.sandcastle.provider._run_cmd"


class _MockProc:
    """Simulates subprocess.Popen for provider tests."""

    def __init__(self, poll_sequence=(), final_returncode=0):
        self._poll_iter = iter(poll_sequence)
        self.final_returncode = final_returncode
        self.killed = False

    def poll(self):
        try:
            return next(self._poll_iter)
        except StopIteration:
            return self.final_returncode

    def kill(self):
        self.killed = True


def _make_fake_start(proc):
    """Returns a side_effect for _start_container that creates the log file and returns proc."""
    captured = []

    def side_effect(cmd, log_path):
        captured.append(log_path)
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        open(log_path, "w").close()
        return proc

    side_effect.captured = captured
    return side_effect


class TestSandcastleProviderDispatch(unittest.TestCase):

    def test_dispatch_returns_run_id_string(self):
        from providers.sandcastle.provider import SandcastleProvider
        with patch(_PATCH_START, return_value=_MockProc()):
            provider = SandcastleProvider(image="img:latest")
            run_id = provider.dispatch("task", "/repo")
        self.assertIsInstance(run_id, str)
        self.assertTrue(len(run_id) > 0)

    def test_dispatch_returns_unique_ids(self):
        from providers.sandcastle.provider import SandcastleProvider
        with patch(_PATCH_START, return_value=_MockProc()):
            provider = SandcastleProvider(image="img:latest")
            ids = [provider.dispatch("task", "/repo") for _ in range(3)]
        self.assertEqual(len(set(ids)), 3)

    def test_dispatch_calls_start_container_with_docker_run_argv(self):
        from providers.sandcastle.provider import SandcastleProvider
        with patch(_PATCH_START, return_value=_MockProc()) as mock_start:
            provider = SandcastleProvider(image="sandbox:latest")
            provider.dispatch("run tests", "/projects/myapp")

        mock_start.assert_called_once()
        cmd = mock_start.call_args.args[0]
        self.assertEqual(cmd[0], "docker")
        self.assertEqual(cmd[1], "run")
        self.assertIn("--rm", cmd)
        self.assertTrue(any("--name=" in a for a in cmd))
        self.assertTrue(any("--volume=/projects/myapp:/projects/myapp:rw" in a for a in cmd))
        self.assertIn("sandbox:latest", cmd)
        self.assertIn("run tests", cmd)

    def test_dispatch_passes_log_path_to_start_container(self):
        from providers.sandcastle.provider import SandcastleProvider
        with patch(_PATCH_START, return_value=_MockProc()) as mock_start:
            provider = SandcastleProvider(image="img:latest")
            provider.dispatch("task", "/repo")

        log_path = mock_start.call_args.args[1]
        self.assertIsInstance(log_path, str)
        self.assertTrue(log_path.endswith(".log") or "sandcastle" in log_path)

    def test_dispatch_with_branch_passes_branch_in_argv(self):
        from providers.sandcastle.provider import SandcastleProvider
        with patch(_PATCH_START, return_value=_MockProc()) as mock_start:
            provider = SandcastleProvider(image="img:latest")
            provider.dispatch("task", "/repo", branch="feat/my-branch")

        cmd = mock_start.call_args.args[0]
        self.assertIn("feat/my-branch", cmd)
        self.assertIn("sh", cmd)

    def test_dispatch_with_podman_uses_podman(self):
        from providers.sandcastle.provider import SandcastleProvider
        with patch(_PATCH_START, return_value=_MockProc()) as mock_start:
            provider = SandcastleProvider(image="img:latest")
            provider.dispatch("task", "/repo", container_provider="podman")

        cmd = mock_start.call_args.args[0]
        self.assertEqual(cmd[0], "podman")

    def test_dispatch_uses_popen_not_run_blocking(self):
        """_start_container (Popen seam) is called; _run_cmd (blocking) is not."""
        from providers.sandcastle.provider import SandcastleProvider
        with patch(_PATCH_START, return_value=_MockProc()) as mock_start:
            with patch(_PATCH_RUN) as mock_run:
                provider = SandcastleProvider(image="img:latest")
                provider.dispatch("task", "/repo")
        mock_start.assert_called_once()
        mock_run.assert_not_called()


class TestSandcastleProviderGetStatus(unittest.TestCase):

    def _dispatch(self, poll_sequence=(), final_returncode=0, timeout=60.0):
        from providers.sandcastle.provider import SandcastleProvider
        mock_proc = _MockProc(poll_sequence, final_returncode)
        fake_start = _make_fake_start(mock_proc)
        with patch(_PATCH_START, side_effect=fake_start):
            provider = SandcastleProvider(image="img:latest", timeout=timeout)
            run_id = provider.dispatch("task", "/repo")
        return provider, run_id, mock_proc

    def test_get_status_unknown_id_returns_error(self):
        from providers.sandcastle.provider import SandcastleProvider
        provider = SandcastleProvider(image="img:latest")
        self.assertEqual(provider.get_status("nonexistent"), "error")

    def test_get_status_returns_running_when_proc_alive(self):
        provider, run_id, _ = self._dispatch(poll_sequence=[None])
        with patch(_PATCH_RUN):
            status = provider.get_status(run_id)
        self.assertEqual(status, "running")

    def test_get_status_returns_completed_when_proc_exits_zero(self):
        provider, run_id, _ = self._dispatch(poll_sequence=[0])
        status = provider.get_status(run_id)
        self.assertEqual(status, "completed")

    def test_get_status_returns_error_when_proc_exits_nonzero(self):
        provider, run_id, _ = self._dispatch(poll_sequence=[1])
        status = provider.get_status(run_id)
        self.assertEqual(status, "error")

    def test_get_status_returns_timed_out_when_timeout_exceeded(self):
        provider, run_id, _ = self._dispatch(
            poll_sequence=[None] * 100,
            timeout=0.001,
        )
        time.sleep(0.005)
        with patch(_PATCH_RUN):
            status = provider.get_status(run_id)
        self.assertEqual(status, "timed_out")

    def test_get_status_idempotent_for_terminal_states(self):
        provider, run_id, _ = self._dispatch(poll_sequence=[0])
        provider.get_status(run_id)  # transitions to completed
        status = provider.get_status(run_id)
        self.assertEqual(status, "completed")


class TestSandcastleProviderGetLogs(unittest.TestCase):

    def test_get_logs_unknown_id_returns_empty_string(self):
        from providers.sandcastle.provider import SandcastleProvider
        provider = SandcastleProvider(image="img:latest")
        self.assertEqual(provider.get_logs("nonexistent"), "")

    def test_get_logs_returns_file_content(self):
        from providers.sandcastle.provider import SandcastleProvider
        mock_proc = _MockProc()
        fake_start = _make_fake_start(mock_proc)
        with patch(_PATCH_START, side_effect=fake_start):
            provider = SandcastleProvider(image="img:latest")
            run_id = provider.dispatch("task", "/repo")

        with open(fake_start.captured[0], "w") as f:
            f.write("container output here")

        self.assertEqual(provider.get_logs(run_id), "container output here")

    def test_get_logs_returns_empty_when_file_missing(self):
        from providers.sandcastle.provider import SandcastleProvider
        mock_proc = _MockProc()
        fake_start = _make_fake_start(mock_proc)
        with patch(_PATCH_START, side_effect=fake_start):
            provider = SandcastleProvider(image="img:latest")
            run_id = provider.dispatch("task", "/repo")

        os.remove(fake_start.captured[0])
        self.assertEqual(provider.get_logs(run_id), "")


class TestSandcastleProviderStop(unittest.TestCase):

    def _dispatch(self, container_provider="docker"):
        from providers.sandcastle.provider import SandcastleProvider
        mock_proc = _MockProc(poll_sequence=[None])
        fake_start = _make_fake_start(mock_proc)
        with patch(_PATCH_START, side_effect=fake_start):
            provider = SandcastleProvider(image="img:latest")
            run_id = provider.dispatch("task", "/repo", container_provider=container_provider)
        return provider, run_id, mock_proc

    def test_stop_calls_run_cmd_with_kill_args(self):
        provider, run_id, _ = self._dispatch()
        with patch(_PATCH_RUN) as mock_run:
            provider.stop(run_id)
        mock_run.assert_called_once()
        kill_cmd = mock_run.call_args.args[0]
        self.assertEqual(kill_cmd[0], "docker")
        self.assertEqual(kill_cmd[1], "kill")
        self.assertTrue(kill_cmd[2].startswith("octowiz-"))

    def test_stop_kills_proc(self):
        provider, run_id, mock_proc = self._dispatch()
        with patch(_PATCH_RUN):
            provider.stop(run_id)
        self.assertTrue(mock_proc.killed)

    def test_stop_sets_status_to_error(self):
        provider, run_id, _ = self._dispatch()
        with patch(_PATCH_RUN):
            provider.stop(run_id)
        self.assertEqual(provider.get_status(run_id), "error")

    def test_stop_is_no_op_for_unknown_id(self):
        from providers.sandcastle.provider import SandcastleProvider
        provider = SandcastleProvider(image="img:latest")
        with patch(_PATCH_RUN) as mock_run:
            provider.stop("nonexistent")
        mock_run.assert_not_called()

    def test_stop_uses_correct_container_provider_for_kill(self):
        provider, run_id, _ = self._dispatch(container_provider="podman")
        with patch(_PATCH_RUN) as mock_run:
            provider.stop(run_id)
        self.assertEqual(mock_run.call_args.args[0][0], "podman")


class TestSandcastleStatus(unittest.TestCase):

    def test_terminal_statuses(self):
        from providers.sandcastle.status import is_terminal, is_error
        self.assertTrue(is_terminal("completed"))
        self.assertTrue(is_terminal("error"))
        self.assertTrue(is_terminal("timed_out"))
        self.assertFalse(is_terminal("running"))
        self.assertFalse(is_terminal("pending"))

    def test_error_statuses(self):
        from providers.sandcastle.status import is_error
        self.assertFalse(is_error("completed"))
        self.assertTrue(is_error("error"))
        self.assertTrue(is_error("timed_out"))


if __name__ == "__main__":
    unittest.main()
