"""Routes A2A capability requests to handlers."""
from typing import Any, Dict, Optional


async def dispatch(event: Dict) -> Optional[Dict]:
    capability = event.get("capability", "")
    if capability == "octowiz.advise":
        from capabilities.advise import handle_advise
        return await handle_advise(event)
    return {"status": "not_implemented", "capability": capability}
