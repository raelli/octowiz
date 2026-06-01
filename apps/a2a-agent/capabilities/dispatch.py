"""octowiz.dispatch capability — fire-and-observe session wrapper."""
import asyncio
import os
import time
from typing import Any, Dict, Optional

import session_owners
from path_guard import validate_cwd

_DEFAULT_POLL_INTERVAL = float(os.environ.get("OCTOWIZ_DISPATCH_POLL_INTERVAL", "5"))
_DEFAULT_TIMEOUT = float(os.environ.get("OCTOWIZ_DISPATCH_TIMEOUT", "300"))


def _make_provider():
    from providers.claude_agent_view.provider import ClaudeAgentViewProvider
    return ClaudeAgentViewProvider()


async def handle_dispatch(
    event: Dict,
    *,
    provider: Any = None,
    poll_interval: Optional[float] = None,
    timeout: Optional[float] = None,
) -> Dict:
    task = event.get("task", "")
    cwd = event.get("cwd", "")

    if not task:
        return {"status": "error", "message": "task is required"}
    if not cwd:
        return {"status": "error", "message": "cwd is required"}
    if task.startswith("-"):
        return {"status": "error", "message": "task must not start with '-'"}

    # P1: validate cwd against OCTOWIZ_ALLOWED_ROOTS before dispatching.
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
        session_id = provider.dispatch(task, cwd)
    except Exception as exc:
        return {"status": "error", "message": f"failed to start session: {exc}"}

    if not session_id:
        return {"status": "error", "message": "session failed to start: no session ID returned"}

    principal = event.get("_principal", "")
    session_owners.register(session_id, principal)

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        await asyncio.sleep(poll_interval)

        # P1: run blocking provider calls in a thread to avoid blocking the event loop.
        session = await asyncio.to_thread(provider.get_status, session_id)
        if session is None:
            continue

        if session.needs_input:
            try:
                output = await asyncio.to_thread(provider.get_logs, session_id)
            except Exception:
                output = ""
            return {"status": "needs-input", "session_id": session_id, "output": output}

        if session.status == "stopped":
            try:
                output = await asyncio.to_thread(provider.get_logs, session_id)
            except Exception:
                output = ""
            session_owners.deregister(session_id)
            return {"status": "completed", "session_id": session_id, "output": output}

        if session.status == "error":
            try:
                output = await asyncio.to_thread(provider.get_logs, session_id)
            except Exception:
                output = ""
            session_owners.deregister(session_id)
            return {"status": "error", "session_id": session_id, "output": output}

    return {
        "status": "error",
        "session_id": session_id,
        "message": f"timeout after {timeout}s waiting for session to complete",
    }
