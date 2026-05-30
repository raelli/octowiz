"""octowiz.advise capability — real advisor logic."""
from typing import Any, Dict, Optional

from advisor.state import store
from advisor.rules import RulesAdvisor

_advisor = RulesAdvisor()


async def handle_advise(event: Dict) -> Optional[Dict]:
    store.record_event(event)
    session = store.get_session(event.get("sessionId"))
    return await _advisor.advise(event, session, {"store": store})
