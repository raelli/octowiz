"""Single authority for dispatch session terminal states."""
from __future__ import annotations

# Statuses after which a session will not progress further.
# "idle" is the real terminal state emitted by `claude agents --json`.
# "stopped" is the normalized form of "exited" (via _STATUS_MAP) and the value used in mocks.
# "exited" is included as defensive coverage for callers that bypass the parser and pass
# raw CLI status strings directly (e.g. a future provider implementation).
TERMINAL_STATUSES: frozenset[str] = frozenset({"idle", "stopped", "exited"})

# Statuses that indicate the session ended with an error.
ERROR_STATUSES: frozenset[str] = frozenset({"error"})


def is_terminal(status: str) -> bool:
    """Return True if the session has reached a terminal (completed) state."""
    return status in TERMINAL_STATUSES


def is_error(status: str) -> bool:
    """Return True if the session has reached an error terminal state."""
    return status in ERROR_STATUSES
