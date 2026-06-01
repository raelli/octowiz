"""octowiz.manage_agents capability — wraps the `claude agents` CLI."""
import os
import re
from typing import Dict, List, Optional

import session_owners
from capabilities.cli_adapter import CliError, ClaudeCliAdapter, SessionInfo
from path_guard import validate_cwd

_CONTROL_OPS = {"logs", "stop", "rm", "respawn"}
_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")

# Keep the old name as an alias so existing tests importing it directly still work.
_validate_cwd = validate_cwd


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
            cwd = validate_cwd(cwd)
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

    # Remove ownership record after a successful rm so the registry doesn't grow unbounded.
    if op == "rm":
        session_owners.deregister(session_id)

    return {"status": "ok", "output": result}
