"""octowiz.review capability — doctrine enrichment for reviewing work."""
from typing import Any, Dict, Optional

from capabilities.doctrine_enrichment import handle_doctrine_enrichment


def _review_prompt_builder(event: Dict, context: Any) -> str:
    cwd = event.get("cwd", "")
    prompt = f"[octowiz.review] Review the work in {cwd}"
    if event.get("sessionId"):
        prompt += f" (session {event['sessionId']})"
    if context:
        prompt += f"\n\nContext:\n{context}"
    return prompt


async def handle_review(event: Dict, *, source: Optional[Any] = None) -> Dict:
    cwd = event.get("cwd", "")
    if not cwd:
        return {"status": "error", "message": "cwd is required"}
    from path_guard import validate_cwd
    try:
        cwd = validate_cwd(cwd)
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}
    enriched_event = {**event, "cwd": cwd}
    result = await handle_doctrine_enrichment(enriched_event, "reviewer", _review_prompt_builder, source=source)
    return {**result, "cwd": cwd, "sessionId": event.get("sessionId")}
