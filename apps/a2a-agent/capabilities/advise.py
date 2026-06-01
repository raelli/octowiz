"""octowiz.advise capability — all-rules advisor with invocation policy."""
from typing import Dict, List, Optional

from packages.advisor.policy import InvocationPolicy
from packages.advisor.rules import RulesAdvisor
from packages.advisor.state import StoreRegistry, _registry

_advisor = RulesAdvisor()
_policy = InvocationPolicy()


async def handle_advise(event: Dict, registry: Optional[StoreRegistry] = None) -> Optional[Dict]:
    """Process an advise event.

    Args:
        event: The incoming event dict (must contain ``sessionId``).
        registry: Optional registry to use. Defaults to the module-level
            ``_registry`` so production callers need not pass anything.
            Pass a fresh ``StoreRegistry()`` in tests for full isolation.
    """
    reg = registry if registry is not None else _registry
    session_id = event.get("sessionId", "")
    store = reg.get(session_id) if session_id else None

    if store is None:
        # No sessionId — still run rules without store-backed conflict detection.
        from packages.advisor.state import SessionStore
        store = SessionStore()

    store.record_event(event)
    session = store.get_session(session_id)
    results = await _advisor.advise_all(event, session, {"store": store})
    decision = _policy.decide(results)
    if decision is None:
        return None

    # Collect files from all matching rule results for downstream consumers.
    files: List[str] = []
    for r in results:
        for f in r.get("files", []):
            if f not in files:
                files.append(f)

    return {
        "level":    decision.level,
        "type":     decision.type,
        "message":  decision.message,
        "reason":   decision.reason,
        "question": decision.question,
        "files":    files,
    }


def handle_session_end(session_id: str, registry: Optional[StoreRegistry] = None) -> None:
    """Drop the store for session_id, freeing per-session state and purging
    the session from the shared ConflictIndex to prevent memory leaks.

    Args:
        session_id: The session that has ended.
        registry: Optional registry to use. Defaults to the module-level
            ``_registry``.
    """
    reg = registry if registry is not None else _registry
    reg.drop(session_id)
