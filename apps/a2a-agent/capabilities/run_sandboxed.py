"""octowiz.run_sandboxed capability — run a task in an isolated Sandcastle environment."""
from __future__ import annotations

import asyncio
import os
import re
import shutil
import time
from typing import Any, Dict, Optional

from a2a import err, require
from path_guard import validate_cwd
from providers.protocol import is_error, is_terminal

_DEFAULT_POLL_INTERVAL = float(os.environ.get("OCTOWIZ_DISPATCH_POLL_INTERVAL", "5"))
_DEFAULT_TIMEOUT = float(os.environ.get("OCTOWIZ_DISPATCH_TIMEOUT", "600"))

_VALID_CONTAINER_PROVIDERS = frozenset({"docker", "podman"})
_BRANCH_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_./-]{0,127}$')

# Singleton provider so wait=False run state persists across calls.
_shared_provider: Optional[Any] = None


def _get_provider() -> Any:
    global _shared_provider
    if _shared_provider is None:
        from providers.sandcastle.provider import SandcastleProvider
        _shared_provider = SandcastleProvider(timeout=_DEFAULT_TIMEOUT)
    return _shared_provider


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

    missing = require(event, "task", "cwd")
    if missing:
        return missing
    if task.startswith("-"):
        return err("task must not start with '-'")
    if container_provider not in _VALID_CONTAINER_PROVIDERS:
        return err(f"unsupported container_provider: {container_provider!r}")
    if not shutil.which(container_provider):
        return err(f"{container_provider} not available")
    if branch is not None:
        if branch.startswith("-"):
            return err("branch must not start with '-'")
        if not _BRANCH_RE.fullmatch(branch):
            return err(f"invalid branch name: {branch!r}")

    try:
        cwd = validate_cwd(cwd)
    except ValueError as exc:
        return err(str(exc))

    if provider is None:
        provider = _get_provider()
    if poll_interval is None:
        poll_interval = _DEFAULT_POLL_INTERVAL
    if timeout is None:
        timeout = _DEFAULT_TIMEOUT

    try:
        run_id = provider.dispatch(task, cwd, branch=branch, container_provider=container_provider)
    except Exception as exc:
        return err(f"failed to start container: {exc}")

    if not wait:
        # Spawn a background watchdog to enforce SANDCASTLE_TIMEOUT on this unsupervised run.
        watchdog_secs = float(os.environ.get("SANDCASTLE_TIMEOUT", "300"))

        async def _watchdog(_run_id: str = run_id, _p: Any = provider, _t: float = watchdog_secs) -> None:
            await asyncio.sleep(_t)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _p.stop, _run_id)

        asyncio.create_task(_watchdog())
        return {"status": "dispatched", "run_id": run_id}

    _loop = asyncio.get_running_loop()
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        await asyncio.sleep(poll_interval)
        run_state = await _loop.run_in_executor(None, provider.poll_run, run_id)
        if run_state is not None and is_terminal(run_state.status):
            logs = await _loop.run_in_executor(None, provider.get_logs, run_id)
            top_status = "error" if is_error(run_state.status) else "ok"
            # exit_status keeps the provider-native status (e.g. timed_out)
            # so artifacts stay byte-identical to the pre-protocol shape.
            return {"status": top_status, "run_id": run_id, "exit_status": run_state.raw_status, "logs": logs}

    # Stop the container before returning — don't orphan it.
    await _loop.run_in_executor(None, provider.stop, run_id)
    return err(f"timeout after {timeout}s", run_id=run_id)
