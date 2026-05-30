"""octowiz.dispatch capability — starts Claude Code background sessions for ÆLLI.

Operations:
  start  — fire-and-forget: starts a session and returns the session ID immediately.
  run    — fire-and-observe: starts a session, polls until a terminal state
           (completed / needs-input / failed), and returns the final status,
           session output, and session ID in a single response.
"""
import asyncio
import re
import subprocess
from typing import Callable, Dict, List, Optional, Tuple

import session_owners

Runner = Callable[[List[str]], Tuple[int, str, str]]

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
_SESSION_RE = re.compile(r"backgrounded\s*[·•]\s*(\S+)")

_DEFAULT_POLL_INTERVAL = 5.0
_DEFAULT_TIMEOUT = 300.0
# Grace period before treating a missing session as a start failure.
_START_GRACE = 30.0


def _default_runner(args: List[str]) -> Tuple[int, str, str]:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=10)
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return 1, "", "operation timed out"
    except OSError as exc:
        return 1, "", str(exc)


def _parse_session_id(stdout: str) -> Optional[str]:
    clean = _ANSI_RE.sub("", stdout)
    m = _SESSION_RE.search(clean)
    return m.group(1) if m else None


def _start_session(event: Dict, runner: Runner) -> Dict:
    """Start a background session. Returns {status, sessionId} or {status, message}."""
    task = str(event.get("task") or "")
    cwd = str(event.get("cwd") or "")
    name = event.get("name")

    if not task:
        return {"status": "error", "message": "task is required"}
    if not cwd:
        return {"status": "error", "message": "cwd is required"}

    args = ["claude", "--bg", "--cwd", cwd]
    if name:
        args += ["--name", str(name)]
    args += ["--", task]

    try:
        returncode, stdout, stderr = runner(args)
    except Exception as exc:
        return {"status": "error", "message": str(exc) or "runner error"}

    if returncode != 0:
        return {"status": "error", "message": stderr or f"claude --bg exited with code {returncode}"}

    session_id = _parse_session_id(stdout)
    if not session_id:
        return {"status": "error", "message": "could not parse session id from output"}

    principal = event.get("_principal", "")
    session_owners.register(session_id, principal)

    return {"status": "ok", "sessionId": session_id}


async def _observe(
    session_id: str,
    provider,
    poll_interval: float = _DEFAULT_POLL_INTERVAL,
    timeout: float = _DEFAULT_TIMEOUT,
    sleep_fn=None,
) -> Dict:
    """Poll until session reaches a terminal state. Returns the result artifact."""
    if sleep_fn is None:
        sleep_fn = asyncio.sleep

    elapsed = 0.0
    while True:
        try:
            status = provider.get_status(session_id)
        except Exception as exc:
            return {"status": "error", "sessionId": session_id, "message": str(exc)}

        if status is not None:
            if status.needs_input:
                logs = _safe_logs(provider, session_id)
                return {"status": "needs-input", "sessionId": session_id, "output": logs}
            if status.status in ("stopped",) and not status.needs_input:
                logs = _safe_logs(provider, session_id)
                return {"status": "completed", "sessionId": session_id, "output": logs}
            if status.status == "error":
                logs = _safe_logs(provider, session_id)
                return {"status": "failed", "sessionId": session_id, "output": logs}
        elif elapsed > _START_GRACE:
            return {
                "status": "error",
                "sessionId": session_id,
                "message": f"session {session_id!r} not found after {_START_GRACE}s",
            }

        if elapsed >= timeout:
            return {
                "status": "error",
                "sessionId": session_id,
                "message": f"dispatch timed out after {timeout}s",
            }

        await sleep_fn(poll_interval)
        elapsed += max(poll_interval, 1e-9)  # always advance to prevent infinite loop


def _safe_logs(provider, session_id: str) -> str:
    try:
        return provider.get_logs(session_id)
    except Exception:
        return ""


async def handle_dispatch(
    event: Dict,
    runner: Optional[Runner] = None,
    provider=None,
    _sleep_fn=None,
) -> Dict:
    if runner is None:
        runner = _default_runner

    op = str(event.get("operation", ""))

    if op == "start":
        return _start_session(event, runner)

    if op == "run":
        start_result = _start_session(event, runner)
        if start_result["status"] != "ok":
            return start_result
        session_id = start_result["sessionId"]

        if provider is None:
            from providers.claude_agent_view.provider import ClaudeAgentViewProvider
            provider = ClaudeAgentViewProvider()

        poll_interval = float(event.get("_poll_interval", _DEFAULT_POLL_INTERVAL))
        timeout = float(event.get("_timeout", _DEFAULT_TIMEOUT))
        return await _observe(
            session_id, provider,
            poll_interval=poll_interval,
            timeout=timeout,
            sleep_fn=_sleep_fn,
        )

    return {"status": "error", "message": f"unknown operation: {op}"}
