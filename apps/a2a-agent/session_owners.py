"""Session-to-principal ownership registry.

Records which principal (authenticated caller) started each session. Control
operations (logs, stop, rm, respawn) verify that the requesting principal
matches the owner before proceeding.

In v1 a single OCTOWIZ_INBOUND_SECRET means all callers share one principal,
so ownership checks always pass. The infrastructure is in place for multi-
caller deployments where different secrets map to different principals.
"""
from typing import Dict, Optional

# session_id → principal identifier
_owners: Dict[str, str] = {}


def register(session_id: str, principal: str) -> None:
    _owners[session_id] = principal


def check(session_id: str, principal: str) -> bool:
    """Return True if principal owns session_id. Returns False for unregistered sessions."""
    owner = _owners.get(session_id)
    if owner is None:
        return False
    return owner == principal


def clear() -> None:
    """Remove all ownership records (used in tests)."""
    _owners.clear()
