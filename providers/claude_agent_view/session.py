"""AgentSession data model."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class AgentSession:
    """Represents a Claude agent background session."""

    id: str
    status: str               # busy | idle (real CLI values); stopped | error (test mocks)
    branch: Optional[str]
    repo: Optional[str]
    needs_input: bool
    ready_for_review: bool
    created_at: Optional[str]
