"""Routes A2A capability requests to handlers."""
from typing import Any, Dict, Optional


async def dispatch(event: Dict) -> Optional[Dict]:
    capability = event.get("capability", "")
    event_type = event.get("type", "")

    if capability == "octowiz.advise":
        from capabilities.advise import handle_advise
        return await handle_advise(event)
    if capability == "octowiz.dispatch":
        from capabilities.dispatch import handle_dispatch
        return await handle_dispatch(event)
    if capability == "octowiz.manage_agents":
        from capabilities.manage_agents import handle_manage_agents
        return await handle_manage_agents(event)
    if event_type == "session-end":
        from capabilities.advise import handle_session_end
        session_id = event.get("sessionId", "")
        if session_id:
            handle_session_end(session_id)
        return {"status": "ok"}
    return {"status": "not_implemented", "capability": capability}
