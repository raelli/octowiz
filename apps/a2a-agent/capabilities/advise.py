"""octowiz.advise capability — all-rules advisor with invocation policy."""
from typing import Dict, List, Optional

from packages.advisor.policy import InvocationPolicy
from packages.advisor.rules import RulesAdvisor
from packages.advisor.state import store

_advisor = RulesAdvisor()
_policy = InvocationPolicy()


async def handle_advise(event: Dict) -> Optional[Dict]:
    store.record_event(event)
    session = store.get_session(event.get("sessionId"))
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
