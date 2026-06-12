"""SandcastleProvider — manages in-memory sandbox run state."""
from __future__ import annotations

import os
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from providers import protocol
from providers.protocol import RunState

from .runner import build_container_cmd, _run_cmd, _start_container
from .status import is_error as _native_is_error
from .status import is_terminal as _native_is_terminal


def to_run_state(raw_status: str) -> RunState:
    """Map a native Sandcastle status onto the canonical RunState.

    Native vocabulary (running/completed/error/timed_out) stays here;
    timed_out folds into canonical 'error', matching how run_sandboxed
    already treated it. Container runs never wait for input.
    """
    if _native_is_error(raw_status):
        status = protocol.ERROR
    elif _native_is_terminal(raw_status):
        status = protocol.COMPLETED
    else:
        status = protocol.RUNNING
    return RunState(status=status, raw_status=raw_status, needs_input=False)

_DEFAULT_TIMEOUT = float(os.environ.get("SANDCASTLE_TIMEOUT", "300"))
_DEFAULT_IMAGE = os.environ.get("SANDCASTLE_IMAGE", "")


@dataclass
class _SandboxRun:
    run_id: str
    container_name: str
    container_provider: str
    log_path: str
    proc: Any
    timeout: float
    status: str = "running"
    start_time: float = field(default_factory=time.monotonic)


class SandcastleProvider:
    """Execution provider backed by Docker/Podman container runs.

    State is held in memory — runs are lost on server restart (acceptable for v1).
    The sandbox image must be pre-built with `claude` CLI and `git` installed.
    Set SANDCASTLE_IMAGE to the image reference before use.
    """

    def __init__(self, image: str = "", timeout: float = 0.0):
        self._image = image or _DEFAULT_IMAGE
        self._timeout = timeout if timeout > 0 else _DEFAULT_TIMEOUT
        self._runs: Dict[str, _SandboxRun] = {}

    def dispatch(
        self,
        task: str,
        cwd: str,
        branch: Optional[str] = None,
        container_provider: str = "docker",
    ) -> str:
        """Start a sandboxed run. Returns a run_id."""
        run_id = str(uuid.uuid4())
        container_name = f"octowiz-{run_id[:12]}"
        log_dir = tempfile.mkdtemp(prefix="sandcastle-")
        log_path = os.path.join(log_dir, "output.log")

        cmd = build_container_cmd(container_provider, container_name, self._image, cwd, task, branch)
        proc = _start_container(cmd, log_path)

        run = _SandboxRun(
            run_id=run_id,
            container_name=container_name,
            container_provider=container_provider,
            log_path=log_path,
            proc=proc,
            timeout=self._timeout,
        )
        self._runs[run_id] = run
        return run_id

    def get_status(self, run_id: str) -> str:
        """Return current status: running | completed | error | timed_out."""
        run = self._runs.get(run_id)
        if run is None:
            return "error"
        if _native_is_terminal(run.status):
            return run.status

        ret = run.proc.poll()
        if ret is None:
            if time.monotonic() - run.start_time > run.timeout:
                run.status = "timed_out"
                self._kill_container(run)
            return run.status

        run.status = "completed" if ret == 0 else "error"
        return run.status

    def poll_run(self, run_id: str) -> RunState:
        """Canonical state of the run. Unknown run ids surface as error."""
        return to_run_state(self.get_status(run_id))

    def get_logs(self, run_id: str) -> str:
        """Return captured stdout/stderr from the run."""
        run = self._runs.get(run_id)
        if run is None:
            return ""
        try:
            with open(run.log_path) as f:
                return f.read()
        except OSError:
            return ""

    def stop(self, run_id: str) -> None:
        """Kill the container and mark the run as error."""
        run = self._runs.get(run_id)
        if run is None:
            return
        self._kill_container(run)
        run.status = "error"

    def _kill_container(self, run: _SandboxRun) -> None:
        _run_cmd([run.container_provider, "kill", run.container_name])
        try:
            run.proc.kill()
        except Exception:
            pass
