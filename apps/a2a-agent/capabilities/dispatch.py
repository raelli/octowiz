"""octowiz.dispatch capability — starts Claude Code background sessions for ÆLLI."""
import asyncio
import re
import subprocess
from typing import Callable, Dict, List, Optional, Tuple

Runner = Callable[[List[str]], Tuple[int, str, str]]

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
_SESSION_RE = re.compile(r"backgrounded\s*[·•]\s*(\S+)")

POLL_INTERVAL_S: float = 2.0
MAX_WAIT_S: float = 300.0
_TERMINAL_STATUSES = {"stopped", "error"}


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


async def _handle_start(event: Dict, runner: Runner) -> Dict:
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

    return {"status": "ok", "sessionId": session_id}


async def _handle_observe(
    event: Dict,
    runner: Runner,
    *,
    _provider=None,
    _poll_interval: float = POLL_INTERVAL_S,
    _max_wait: float = MAX_WAIT_S,
) -> Dict:
    """Start a session and poll until terminal state, then return result."""
    # Step 1: start the session using existing start logic
    start_result = await _handle_start(event, runner)
    if start_result.get("status") != "ok":
        return start_result  # propagate error from start

    run_id = start_result["sessionId"]

    # Step 2: import provider (injectable for tests)
    if _provider is None:
        from providers.claude_agent_view.provider import ClaudeAgentViewProvider
        _provider = ClaudeAgentViewProvider()

    # Step 3: poll until terminal
    elapsed: float = 0.0
    while elapsed < _max_wait:
        await asyncio.sleep(_poll_interval)
        elapsed += _poll_interval

        session = _provider.get_status(run_id)
        if session is None:
            continue

        if session.needs_input:
            return {"status": "needs-input", "sessionId": run_id, "output": _provider.get_logs(run_id)}

        if session.status in _TERMINAL_STATUSES:
            final = "completed" if session.status == "stopped" else "failed"
            return {"status": final, "sessionId": run_id, "output": _provider.get_logs(run_id)}

    return {"status": "timeout", "sessionId": run_id, "output": ""}


async def handle_dispatch(event: Dict, runner: Optional[Runner] = None, **kwargs) -> Dict:
    if runner is None:
        runner = _default_runner

    op = str(event.get("operation", ""))

    if op == "start":
        return await _handle_start(event, runner)
    if op == "observe":
        return await _handle_observe(event, runner, **kwargs)
    return {"status": "error", "message": f"unknown operation: {op}"}
