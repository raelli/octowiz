"""octowiz.manage_agents capability — wraps the `claude agents` CLI."""
import re
import subprocess
from typing import Any, Callable, Dict, List, Optional, Tuple


Runner = Callable[[List[str]], Tuple[int, str, str]]

_CONTROL_OPS = {"logs", "stop", "rm", "respawn"}
_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _default_runner(args: List[str]) -> Tuple[int, str, str]:
    result = subprocess.run(args, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


async def handle_manage_agents(event: Dict, runner: Optional[Runner] = None) -> Dict:
    if runner is None:
        runner = _default_runner
    op = event.get("operation", "")
    if op == "list":
        return _handle_list(event, runner)
    if op in _CONTROL_OPS:
        return _handle_control(op, event, runner)
    return {"status": "error", "message": f"unknown operation: {op}"}


def _handle_list(event: Dict, runner: Runner) -> Dict:
    args = ["claude", "agents", "--json"]
    cwd = event.get("cwd")
    if cwd:
        args += ["--cwd", cwd]
    rc, stdout, _stderr = runner(args)
    if rc != 0:
        return {"status": "ok", "sessions": [], "warning": "supervisor_unavailable"}
    try:
        raw: List[Dict] = __import__("json").loads(stdout or "[]")
    except Exception:
        return {"status": "ok", "sessions": [], "warning": "supervisor_unavailable"}
    sessions = [
        {
            "sessionId": s.get("sessionId", ""),
            "name": s.get("name", ""),
            "status": s.get("status", ""),
            "cwd": s.get("cwd", ""),
            "pid": s.get("pid"),
            "startedAt": s.get("startedAt"),
        }
        for s in raw
    ]
    return {"status": "ok", "sessions": sessions}


def _handle_control(op: str, event: Dict, runner: Runner) -> Dict:
    session_id = event.get("sessionId", "")
    if not session_id or not _SESSION_ID_RE.match(session_id):
        return {"status": "error", "message": f"invalid sessionId: {session_id!r}"}
    rc, stdout, stderr = runner(["claude", op, "--", session_id])
    if rc != 0:
        return {"status": "error", "message": stderr or f"claude {op} exited with code {rc}"}
    return {"status": "ok", "output": stdout}
