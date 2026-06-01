"""Parse Claude agent session output."""
from __future__ import annotations

import json
from typing import List

from .session import AgentSession

_STATUS_MAP = {
    "running": "running",
    "busy": "running",        # real CLI value for an active session
    "stopped": "stopped",
    "idle": "idle",           # real CLI value for a completed/waiting session
    "waiting_for_input": "waiting",
    "error": "error",
    "exited": "stopped",
}


def parse_sessions(json_output: str) -> List[AgentSession]:
    """Parse `claude agents --json` output into a list of AgentSession. Never raises."""
    try:
        data = json.loads(json_output)
        if not isinstance(data, list):
            return []
        return [_parse_one(item) for item in data if isinstance(item, dict)]
    except Exception:
        return []


def _parse_one(item: dict) -> AgentSession:
    """Parse a single session dict into an AgentSession.

    Handles both the legacy format (id, repoRoot, createdAt, needsInput) used in
    tests/mocks and the real `claude agents --json` format (sessionId, cwd, startedAt).
    """
    # sessionId is the real CLI field; id is the legacy/mock field
    session_id = str(item.get("sessionId") or item.get("id") or "")
    raw_status = item.get("status", "")
    status = _STATUS_MAP.get(raw_status, raw_status)
    needs_input = bool(item.get("needsInput", False))
    ready_for_review = status == "stopped" and not needs_input
    return AgentSession(
        id=session_id,
        status=status,
        branch=item.get("branch") or None,
        # repoRoot is legacy; real CLI uses cwd
        repo=item.get("repoRoot") or item.get("cwd") or None,
        needs_input=needs_input,
        ready_for_review=ready_for_review,
        # createdAt is legacy; real CLI uses startedAt
        created_at=item.get("createdAt") or str(item.get("startedAt") or "") or None,
    )
