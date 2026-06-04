"""Single authority for Sandcastle run terminal states."""
from __future__ import annotations

TERMINAL_STATUSES: frozenset[str] = frozenset({"completed", "error", "timed_out"})

ERROR_STATUSES: frozenset[str] = frozenset({"error", "timed_out"})


def is_terminal(status: str) -> bool:
    return status in TERMINAL_STATUSES


def is_error(status: str) -> bool:
    return status in ERROR_STATUSES
