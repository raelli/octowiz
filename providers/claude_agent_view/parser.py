"""Parse Claude agent session output."""
from __future__ import annotations

import json
from typing import List

from .session import AgentSession

_STATUS_MAP = {
    "running": "running",
    "stopped": "stopped",
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
    """Parse a single session dict into an AgentSession."""
    raw_status = item.get("status", "")
    status = _STATUS_MAP.get(raw_status, raw_status)
    needs_input = bool(item.get("needsInput", False))
    ready_for_review = status == "stopped" and not needs_input
    return AgentSession(
        id=str(item.get("id", "")),
        status=status,
        branch=item.get("branch") or None,
        repo=item.get("repoRoot") or None,
        needs_input=needs_input,
        ready_for_review=ready_for_review,
        created_at=item.get("createdAt") or None,
    )
