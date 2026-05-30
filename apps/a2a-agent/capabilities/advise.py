"""octowiz.advise capability — real advisor logic with invocation policy."""
from typing import Any, Dict, Optional

from packages.advisor.state import store
from packages.advisor.policy import PolicyAdvisor

_policy = PolicyAdvisor()


async def handle_advise(event: Dict) -> Optional[Dict]:
    store.record_event(event)
    session = store.get_session(event.get("sessionId"))
    return await _policy.check(event, session, {"store": store})
