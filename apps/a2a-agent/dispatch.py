"""Routes A2A capability requests to handlers."""
from typing import Any, Dict, Optional


async def dispatch(event: Dict) -> Optional[Dict]:
    capability = event.get("capability", "")

    if capability == "octowiz.dispatch":
        from capabilities.dispatch import handle_dispatch
        return await handle_dispatch(event)
    if capability == "octowiz.manage_agents":
        from capabilities.manage_agents import handle_manage_agents
        return await handle_manage_agents(event)
    if capability == "octowiz.load_memory":
        from capabilities.load_memory import handle_load_memory
        return await handle_load_memory(event)
    if capability == "octowiz.escalate_to_aelli":
        from capabilities.escalate import handle_escalate
        return await handle_escalate(event)
    if capability == "octowiz.plan":
        from capabilities.plan import handle_plan
        return await handle_plan(event)
    if capability == "octowiz.review":
        from capabilities.review import handle_review
        return await handle_review(event)
    if capability == "octowiz.write_diary":
        from capabilities.write_diary import handle_write_diary
        return await handle_write_diary(event)
    if capability == "octowiz.run_sandboxed":
        from capabilities.run_sandboxed import handle_run_sandboxed
        return await handle_run_sandboxed(event)
    if capability == "octowiz.marketplace_info":
        from capabilities.marketplace_info import handle_marketplace_info
        return await handle_marketplace_info(event)
    return {"status": "not_implemented", "capability": capability}
