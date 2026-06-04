"""octowiz.run_sandboxed capability — run a task in an isolated Sandcastle environment."""
from __future__ import annotations

import asyncio
import os
import shutil
import time
from typing import Any, Dict, Optional

from path_guard import validate_cwd
from providers.sandcastle.status import is_terminal

_DEFAULT_POLL_INTERVAL = float(os.environ.get("OCTOWIZ_DISPATCH_POLL_INTERVAL", "5"))
_DEFAULT_TIMEOUT = float(os.environ.get("OCTOWIZ_DISPATCH_TIMEOUT", "300"))

_VALID_CONTAINER_PROVIDERS = frozenset({"docker", "podman"})


def _make_provider():
    from providers.sandcastle.provider import SandcastleProvider
    return SandcastleProvider()


async def handle_run_sandboxed(
    event: Dict,
    *,
    provider: Any = None,
    poll_interval: Optional[float] = None,
    timeout: Optional[float] = None,
) -> Dict:
    task = event.get("task", "")
    cwd = event.get("cwd", "")
    branch = event.get("branch")
    container_provider = event.get("container_provider", "docker")
    wait = event.get("wait", True)

    if not task:
        return {"status": "error", "message": "task is required"}
    if not cwd:
        return {"status": "error", "message": "cwd is required"}
    if task.startswith("-"):
        return {"status": "error", "message": "task must not start with '-'"}
    if container_provider not in _VALID_CONTAINER_PROVIDERS:
        return {"status": "error", "message": f"unsupported container_provider: {container_provider!r}"}
    if not shutil.which(container_provider):
        return {"status": "error", "message": f"{container_provider} not available"}

    try:
        cwd = validate_cwd(cwd)
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}

    if provider is None:
        provider = _make_provider()
    if poll_interval is None:
        poll_interval = _DEFAULT_POLL_INTERVAL
    if timeout is None:
        timeout = _DEFAULT_TIMEOUT

    try:
        run_id = provider.dispatch(task, cwd, branch=branch, container_provider=container_provider)
    except Exception as exc:
        return {"status": "error", "message": f"failed to start container: {exc}"}

    if not wait:
        return {"status": "dispatched", "run_id": run_id}

    _loop = asyncio.get_running_loop()
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        await asyncio.sleep(poll_interval)
        status = await _loop.run_in_executor(None, provider.get_status, run_id)
        if is_terminal(status):
            logs = await _loop.run_in_executor(None, provider.get_logs, run_id)
            return {"status": "ok", "run_id": run_id, "exit_status": status, "logs": logs}

    return {"status": "error", "run_id": run_id, "message": f"timeout after {timeout}s"}
