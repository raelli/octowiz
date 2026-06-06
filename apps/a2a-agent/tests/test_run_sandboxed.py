"""Tests for octowiz.run_sandboxed capability."""
import asyncio
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _run(coro):
    return asyncio.run(coro)


_FAST = {"poll_interval": 0.001, "timeout": 5.0}
_INSTANT_TIMEOUT = {"poll_interval": 0.001, "timeout": 0.005}


class _MockSandcastleProvider:
    """Simulates SandcastleProvider for capability tests."""

    def __init__(self, run_id="sc-run-1", dispatch_exc=None, status_sequence=(), logs="container logs"):
        self._run_id = run_id
        self._dispatch_exc = dispatch_exc
        self._status_iter = iter(status_sequence)
        self._logs = logs
        self.dispatched_task = None
        self.dispatched_cwd = None
        self.dispatched_branch = None
        self.dispatched_provider = None

    def dispatch(self, task, cwd, branch=None, container_provider="docker"):
        if self._dispatch_exc:
            raise self._dispatch_exc
        self.dispatched_task = task
        self.dispatched_cwd = cwd
        self.dispatched_branch = branch
        self.dispatched_provider = container_provider
        return self._run_id

    def get_status(self, run_id):
        try:
            return next(self._status_iter)
        except StopIteration:
            return "running"

    def get_logs(self, run_id):
        return self._logs

    def stop(self, run_id):
        pass


class TestRunSandboxedValidation(unittest.TestCase):

    def _call(self, event, **kwargs):
        from capabilities.run_sandboxed import handle_run_sandboxed
        return _run(handle_run_sandboxed(event, **kwargs))

    def test_missing_task_returns_error(self):
        result = self._call({"cwd": "/repo"})
        self.assertEqual(result["status"], "error")
        self.assertIn("task", result["message"])

    def test_missing_cwd_returns_error(self):
        result = self._call({"task": "run tests"})
        self.assertEqual(result["status"], "error")
        self.assertIn("cwd", result["message"])

    def test_task_starting_with_dash_returns_error(self):
        result = self._call({"task": "--inject", "cwd": "/repo"})
        self.assertEqual(result["status"], "error")

    def test_relative_cwd_returns_error(self):
        result = self._call({"task": "run tests", "cwd": "relative/path"})
        self.assertEqual(result["status"], "error")
        self.assertIn("absolute", result["message"])

    def test_unknown_container_provider_returns_error(self):
        result = self._call({"task": "run tests", "cwd": "/repo", "container_provider": "kubectl"})
        self.assertEqual(result["status"], "error")
        self.assertIn("kubectl", result["message"])

    def test_container_provider_not_on_path_returns_error(self):
        with patch("shutil.which", return_value=None):
            result = self._call({"task": "run tests", "cwd": "/repo"})
        self.assertEqual(result["status"], "error")
        self.assertIn("not available", result["message"])

    def test_allowed_roots_blocks_outside_cwd(self):
        with patch.dict(os.environ, {"OCTOWIZ_ALLOWED_ROOTS": "/allowed"}):
            with patch("shutil.which", return_value="/usr/bin/docker"):
                result = self._call({"task": "run tests", "cwd": "/other/path"})
        self.assertEqual(result["status"], "error")
        self.assertIn("allowed root", result["message"])


class TestRunSandboxedWaitFalse(unittest.TestCase):

    def setUp(self):
        self._orig_allowed_roots = os.environ.get("OCTOWIZ_ALLOWED_ROOTS")
        os.environ["OCTOWIZ_ALLOWED_ROOTS"] = "/repo:/projects"

    def tearDown(self):
        if self._orig_allowed_roots is None:
            os.environ.pop("OCTOWIZ_ALLOWED_ROOTS", None)
        else:
            os.environ["OCTOWIZ_ALLOWED_ROOTS"] = self._orig_allowed_roots

    def test_wait_false_returns_dispatched_immediately(self):
        from capabilities.run_sandboxed import handle_run_sandboxed
        provider = _MockSandcastleProvider(run_id="sc-1", status_sequence=["running"])
        with patch("shutil.which", return_value="/usr/bin/docker"):
            result = _run(handle_run_sandboxed(
                {"task": "run tests", "cwd": "/repo", "wait": False},
                provider=provider, **_FAST,
            ))
        self.assertEqual(result["status"], "dispatched")
        self.assertEqual(result["run_id"], "sc-1")

    def test_wait_false_does_not_poll_provider(self):
        from capabilities.run_sandboxed import handle_run_sandboxed
        provider = _MockSandcastleProvider(run_id="sc-2")
        with patch("shutil.which", return_value="/usr/bin/docker"):
            _run(handle_run_sandboxed(
                {"task": "run tests", "cwd": "/repo", "wait": False},
                provider=provider, **_FAST,
            ))
        self.assertEqual(provider.dispatched_task, "run tests")

    def test_wait_false_watchdog_stops_container_after_timeout(self):
        """wait=False must spawn a background watchdog that calls provider.stop after SANDCASTLE_TIMEOUT."""
        from capabilities.run_sandboxed import handle_run_sandboxed
        stopped_ids = []

        class _TrackingProvider(_MockSandcastleProvider):
            def stop(self, run_id):
                stopped_ids.append(run_id)

        provider = _TrackingProvider(run_id="watchdog-1")

        async def _scenario():
            with patch("shutil.which", return_value="/usr/bin/docker"):
                with patch.dict(os.environ, {"SANDCASTLE_TIMEOUT": "0.05"}):
                    result = await handle_run_sandboxed(
                        {"task": "run tests", "cwd": "/repo", "wait": False},
                        provider=provider, **_FAST,
                    )
            await asyncio.sleep(0.12)  # wait for the 0.05s watchdog to fire
            return result

        result = asyncio.run(_scenario())
        self.assertEqual(result["status"], "dispatched")
        self.assertIn("watchdog-1", stopped_ids)


class TestRunSandboxedWaitTrue(unittest.TestCase):

    def setUp(self):
        self._orig_allowed_roots = os.environ.get("OCTOWIZ_ALLOWED_ROOTS")
        os.environ["OCTOWIZ_ALLOWED_ROOTS"] = "/repo:/projects"

    def tearDown(self):
        if self._orig_allowed_roots is None:
            os.environ.pop("OCTOWIZ_ALLOWED_ROOTS", None)
        else:
            os.environ["OCTOWIZ_ALLOWED_ROOTS"] = self._orig_allowed_roots

    def test_wait_true_polls_until_completed(self):
        from capabilities.run_sandboxed import handle_run_sandboxed
        provider = _MockSandcastleProvider(
            run_id="sc-3",
            status_sequence=["running", "running", "completed"],
            logs="all tests passed",
        )
        with patch("shutil.which", return_value="/usr/bin/docker"):
            result = _run(handle_run_sandboxed(
                {"task": "run tests", "cwd": "/repo"},
                provider=provider, **_FAST,
            ))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["run_id"], "sc-3")
        self.assertEqual(result["exit_status"], "completed")
        self.assertEqual(result["logs"], "all tests passed")

    def test_wait_true_polls_until_error_returns_status_error(self):
        from capabilities.run_sandboxed import handle_run_sandboxed
        provider = _MockSandcastleProvider(
            run_id="sc-4",
            status_sequence=["running", "error"],
            logs="crash output",
        )
        with patch("shutil.which", return_value="/usr/bin/docker"):
            result = _run(handle_run_sandboxed(
                {"task": "run tests", "cwd": "/repo"},
                provider=provider, **_FAST,
            ))
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["exit_status"], "error")
        self.assertEqual(result["logs"], "crash output")

    def test_wait_true_polls_until_timed_out_returns_status_error(self):
        from capabilities.run_sandboxed import handle_run_sandboxed
        provider = _MockSandcastleProvider(
            run_id="sc-5",
            status_sequence=["running", "timed_out"],
        )
        with patch("shutil.which", return_value="/usr/bin/docker"):
            result = _run(handle_run_sandboxed(
                {"task": "run tests", "cwd": "/repo"},
                provider=provider, **_FAST,
            ))
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["exit_status"], "timed_out")

    def test_wait_true_completed_still_returns_status_ok(self):
        from capabilities.run_sandboxed import handle_run_sandboxed
        provider = _MockSandcastleProvider(
            run_id="sc-ok",
            status_sequence=["completed"],
            logs="all green",
        )
        with patch("shutil.which", return_value="/usr/bin/docker"):
            result = _run(handle_run_sandboxed(
                {"task": "run tests", "cwd": "/repo"},
                provider=provider, **_FAST,
            ))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["exit_status"], "completed")

    def test_wait_true_capability_timeout_returns_error(self):
        from capabilities.run_sandboxed import handle_run_sandboxed
        provider = _MockSandcastleProvider(
            run_id="sc-6",
            status_sequence=["running"] * 200,
        )
        with patch("shutil.which", return_value="/usr/bin/docker"):
            result = _run(handle_run_sandboxed(
                {"task": "run tests", "cwd": "/repo"},
                provider=provider, **_INSTANT_TIMEOUT,
            ))
        self.assertEqual(result["status"], "error")
        self.assertIn("timeout", result["message"].lower())

    def test_task_and_cwd_forwarded_to_provider(self):
        from capabilities.run_sandboxed import handle_run_sandboxed
        provider = _MockSandcastleProvider(status_sequence=["completed"])
        with patch("shutil.which", return_value="/usr/bin/docker"):
            _run(handle_run_sandboxed(
                {"task": "run integration tests", "cwd": "/projects/myapp"},
                provider=provider, **_FAST,
            ))
        self.assertEqual(provider.dispatched_task, "run integration tests")
        self.assertEqual(provider.dispatched_cwd, "/projects/myapp")

    def test_branch_forwarded_to_provider(self):
        from capabilities.run_sandboxed import handle_run_sandboxed
        provider = _MockSandcastleProvider(status_sequence=["completed"])
        with patch("shutil.which", return_value="/usr/bin/docker"):
            _run(handle_run_sandboxed(
                {"task": "run tests", "cwd": "/repo", "branch": "feat/new"},
                provider=provider, **_FAST,
            ))
        self.assertEqual(provider.dispatched_branch, "feat/new")

    def test_container_provider_forwarded_to_provider(self):
        from capabilities.run_sandboxed import handle_run_sandboxed
        provider = _MockSandcastleProvider(status_sequence=["completed"])
        with patch("shutil.which", return_value="/usr/bin/podman"):
            _run(handle_run_sandboxed(
                {"task": "run tests", "cwd": "/repo", "container_provider": "podman"},
                provider=provider, **_FAST,
            ))
        self.assertEqual(provider.dispatched_provider, "podman")


class TestRunSandboxedBranchValidation(unittest.TestCase):

    def setUp(self):
        self._orig_allowed_roots = os.environ.get("OCTOWIZ_ALLOWED_ROOTS")
        os.environ["OCTOWIZ_ALLOWED_ROOTS"] = "/repo:/projects"

    def tearDown(self):
        if self._orig_allowed_roots is None:
            os.environ.pop("OCTOWIZ_ALLOWED_ROOTS", None)
        else:
            os.environ["OCTOWIZ_ALLOWED_ROOTS"] = self._orig_allowed_roots

    def _call(self, event, **kwargs):
        from capabilities.run_sandboxed import handle_run_sandboxed
        return asyncio.run(handle_run_sandboxed(event, **kwargs))

    def test_branch_starting_with_dash_returns_error(self):
        with patch("shutil.which", return_value="/usr/bin/docker"):
            result = self._call({"task": "run tests", "cwd": "/repo", "branch": "--evil"})
        self.assertEqual(result["status"], "error")
        self.assertIn("branch", result["message"])

    def test_branch_with_spaces_returns_error(self):
        with patch("shutil.which", return_value="/usr/bin/docker"):
            result = self._call({"task": "run tests", "cwd": "/repo", "branch": "bad branch"})
        self.assertEqual(result["status"], "error")
        self.assertIn("branch", result["message"])

    def test_valid_branch_passes_validation(self):
        from capabilities.run_sandboxed import handle_run_sandboxed
        provider = _MockSandcastleProvider(status_sequence=["completed"])
        with patch("shutil.which", return_value="/usr/bin/docker"):
            result = asyncio.run(handle_run_sandboxed(
                {"task": "run tests", "cwd": "/repo", "branch": "feat/my-branch"},
                provider=provider, **_FAST,
            ))
        self.assertNotEqual(result["status"], "error")


class TestRunSandboxedTimeoutStopsContainer(unittest.TestCase):

    def setUp(self):
        self._orig_allowed_roots = os.environ.get("OCTOWIZ_ALLOWED_ROOTS")
        os.environ["OCTOWIZ_ALLOWED_ROOTS"] = "/repo:/projects"

    def tearDown(self):
        if self._orig_allowed_roots is None:
            os.environ.pop("OCTOWIZ_ALLOWED_ROOTS", None)
        else:
            os.environ["OCTOWIZ_ALLOWED_ROOTS"] = self._orig_allowed_roots

    def test_capability_timeout_stops_provider_container(self):
        from capabilities.run_sandboxed import handle_run_sandboxed
        provider = _MockSandcastleProvider(
            run_id="sc-timeout",
            status_sequence=["running"] * 200,
        )
        stopped_ids = []
        original_stop = provider.get_status

        class _TrackingProvider(_MockSandcastleProvider):
            def stop(self, run_id):
                stopped_ids.append(run_id)

        tracking = _TrackingProvider(run_id="sc-timeout", status_sequence=["running"] * 200)
        with patch("shutil.which", return_value="/usr/bin/docker"):
            asyncio.run(handle_run_sandboxed(
                {"task": "run tests", "cwd": "/repo"},
                provider=tracking, **_INSTANT_TIMEOUT,
            ))
        self.assertIn("sc-timeout", stopped_ids)


class TestRunSandboxedDispatchError(unittest.TestCase):

    def setUp(self):
        self._orig_allowed_roots = os.environ.get("OCTOWIZ_ALLOWED_ROOTS")
        os.environ["OCTOWIZ_ALLOWED_ROOTS"] = "/repo:/projects"

    def tearDown(self):
        if self._orig_allowed_roots is None:
            os.environ.pop("OCTOWIZ_ALLOWED_ROOTS", None)
        else:
            os.environ["OCTOWIZ_ALLOWED_ROOTS"] = self._orig_allowed_roots

    def test_dispatch_exception_returns_error(self):
        from capabilities.run_sandboxed import handle_run_sandboxed
        provider = _MockSandcastleProvider(dispatch_exc=RuntimeError("image not found"))
        with patch("shutil.which", return_value="/usr/bin/docker"):
            result = _run(handle_run_sandboxed(
                {"task": "run tests", "cwd": "/repo"},
                provider=provider, **_FAST,
            ))
        self.assertEqual(result["status"], "error")
        self.assertIn("image not found", result["message"])


class TestRunSandboxedRouting(unittest.TestCase):

    def test_dispatch_routes_run_sandboxed(self):
        from unittest.mock import AsyncMock
        import importlib
        import dispatch as dispatch_mod
        importlib.reload(dispatch_mod)

        mock_result = {"status": "ok", "run_id": "sc-1", "exit_status": "completed", "logs": ""}
        with patch(
            "capabilities.run_sandboxed.handle_run_sandboxed",
            new=AsyncMock(return_value=mock_result),
        ) as mock_h:
            result = _run(dispatch_mod.dispatch({
                "capability": "octowiz.run_sandboxed",
                "task": "run tests",
                "cwd": "/repo",
            }))
        self.assertEqual(result["status"], "ok")
        mock_h.assert_called_once()


if __name__ == "__main__":
    unittest.main()
