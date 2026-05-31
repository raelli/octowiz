"""octowiz.manage_agents capability — wraps the `claude agents` CLI."""
import os
import re
from typing import Dict, List, Optional

import session_owners
from capabilities.cli_adapter import CliError, ClaudeCliAdapter, SessionInfo

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


async def handle_manage_agents(event: Dict, adapter: Optional[ClaudeCliAdapter] = None) -> Dict:
    if adapter is None:
        adapter = ClaudeCliAdapter()
    op = event.get("operation", "")
    if op == "list":
        return _handle_list(event, adapter)
    if op in _CONTROL_OPS:
        return _handle_control(op, event, adapter)
    return {"status": "error", "message": f"unknown operation: {op}"}


def _handle_list(event: Dict, adapter: ClaudeCliAdapter) -> Dict:
    cwd = event.get("cwd")
    if cwd:
        try:
            cwd = _validate_cwd(cwd)
        except ValueError as exc:
            return {"status": "error", "message": str(exc)}

    result = adapter.list_sessions(cwd=cwd)
    if isinstance(result, CliError):
        return {"status": "ok", "sessions": [], "warning": "supervisor_unavailable"}

    return {
        "status": "ok",
        "sessions": [
            {
                "sessionId": s.session_id,
                "name": s.name,
                "status": s.status,
                "cwd": s.cwd,
                "pid": s.pid,
                "startedAt": s.started_at,
            }
            for s in result
        ],
    }


def _handle_control(op: str, event: Dict, adapter: ClaudeCliAdapter) -> Dict:
    session_id = event.get("sessionId", "")
    if not session_id or not _SESSION_ID_RE.match(session_id):
        return {"status": "error", "message": f"invalid sessionId: {session_id!r}"}
    principal = event.get("_principal", "")
    if not session_owners.check(session_id, principal):
        return {"status": "error", "message": f"session {session_id!r} is not owned by this caller"}

    result = adapter.control(op, session_id)
    if isinstance(result, CliError):
        return {"status": "error", "message": result.message}
    return {"status": "ok", "output": result}
