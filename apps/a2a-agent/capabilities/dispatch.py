"""octowiz.dispatch capability — fire-and-observe session wrapper."""
import asyncio
import os
import time
from typing import Any, Dict, Optional

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

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        await asyncio.sleep(poll_interval)

        session = provider.get_status(session_id)
        if session is None:
            continue

        if session.needs_input:
            output = provider.get_logs(session_id)
            return {"status": "needs-input", "session_id": session_id, "output": output}

        if session.status == "stopped":
            output = provider.get_logs(session_id)
            return {"status": "completed", "session_id": session_id, "output": output}

        if session.status == "error":
            output = provider.get_logs(session_id)
            return {"status": "error", "session_id": session_id, "output": output}

    return {
        "status": "error",
        "session_id": session_id,
        "message": f"timeout after {timeout}s waiting for session to complete",
    }
