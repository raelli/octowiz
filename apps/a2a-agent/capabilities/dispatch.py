"""octowiz.dispatch capability — starts Claude Code background sessions for ÆLLI."""
import re
import subprocess
from typing import Callable, Dict, List, Optional, Tuple

Runner = Callable[[List[str], str], Tuple[int, str, str]]

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
_SESSION_RE = re.compile(r"backgrounded\s*[·•]\s*(\S+)")


def _default_runner(args: List[str], cwd: str = "") -> Tuple[int, str, str]:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=10, cwd=cwd or None)
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return 1, "", "operation timed out"
    except OSError as exc:
        return 1, "", str(exc)


def _parse_session_id(stdout: str) -> Optional[str]:
    clean = _ANSI_RE.sub("", stdout)
    m = _SESSION_RE.search(clean)
    return m.group(1) if m else None


async def handle_dispatch(event: Dict, runner: Optional[Runner] = None) -> Dict:
    if runner is None:
        runner = _default_runner

    op = str(event.get("operation", ""))

    if op != "start":
        return {"status": "error", "message": f"unknown operation: {op}"}

    task = str(event.get("task") or "")
    cwd = str(event.get("cwd") or "")
    name = event.get("name")

    if not task:
        return {"status": "error", "message": "task is required"}
    if not cwd:
        return {"status": "error", "message": "cwd is required"}

    args = ["claude", "--bg"]
    if name:
        args += ["--name", str(name)]
    args += ["--", task]

    try:
        returncode, stdout, stderr = runner(args, cwd)
    except Exception as exc:
        return {"status": "error", "message": str(exc) or "runner error"}

    if returncode != 0:
        return {"status": "error", "message": stderr or f"claude --bg exited with code {returncode}"}

    session_id = _parse_session_id(stdout)
    if not session_id:
        return {"status": "error", "message": "could not parse session id from output"}

    return {"status": "ok", "sessionId": session_id}
