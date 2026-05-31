"""octowiz.manage_agents capability — wraps the `claude agents` CLI."""
import json
import os
import re
import subprocess
from typing import Callable, Dict, List, Optional, Tuple

import session_owners


Runner = Callable[[List[str]], Tuple[int, str, str]]

_CONTROL_OPS = {"logs", "stop", "rm", "respawn"}
_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def _validate_cwd(cwd: str) -> str:
    """Canonicalize cwd and enforce OCTOWIZ_ALLOWED_ROOTS when set."""
    if not os.path.isabs(cwd):
        raise ValueError(f"cwd must be an absolute path: {cwd!r}")
    canonical = os.path.realpath(cwd)
    allowed_roots_env = os.environ.get("OCTOWIZ_ALLOWED_ROOTS", "")
    if allowed_roots_env:
        roots = [r.strip() for r in allowed_roots_env.split(":") if r.strip()]
        if not any(canonical == r or canonical.startswith(r + os.sep) for r in roots):
            raise ValueError(f"cwd {canonical!r} is not within an allowed root")
    return canonical


def _default_runner(args: List[str]) -> Tuple[int, str, str]:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=30)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "operation timed out"
    except OSError as exc:
        return 1, "", str(exc)


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
        try:
            cwd = _validate_cwd(cwd)
        except ValueError as exc:
            return {"status": "error", "message": str(exc)}
        args += ["--cwd", cwd]
    try:
        rc, stdout, _stderr = runner(args)
    except Exception:
        return {"status": "ok", "sessions": [], "warning": "supervisor_unavailable"}
    if rc != 0:
        return {"status": "ok", "sessions": [], "warning": "supervisor_unavailable"}
    try:
        raw: List[Dict] = json.loads(stdout or "[]")
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
    principal = event.get("_principal", "")
    if not session_owners.check(session_id, principal):
        return {"status": "error", "message": f"session {session_id!r} is not owned by this caller"}
    try:
        rc, stdout, stderr = runner(["claude", op, "--", session_id])
    except Exception as exc:
        return {"status": "error", "message": str(exc) or "runner error"}
    if rc != 0:
        return {"status": "error", "message": stderr or f"claude {op} exited with code {rc}"}
    return {"status": "ok", "output": stdout}
