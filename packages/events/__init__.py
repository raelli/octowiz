# packages/events/__init__.py
from __future__ import annotations

from typing import List, Literal, TypedDict

EventType = Literal[
    "prompt",
    "file-edit",
    "file-write",
    "tool-used",
    "agent-run-started",
    "agent-run-finished",
    "risk-detected",
]


class OctowizEvent(TypedDict, total=False):
    type: EventType
    capability: str
    sessionId: str
    repoRoot: str
    branch: str
    live_modified_files: List[str]
    prompt_summary: str
