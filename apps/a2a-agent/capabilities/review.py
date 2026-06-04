"""octowiz.review capability — doctrine enrichment for reviewing work."""
import os
from typing import Dict


async def handle_review(event: Dict) -> Dict:
    cwd = event.get("cwd", "")
    if not cwd:
        return {"status": "error", "message": "cwd is required"}

    from path_guard import validate_cwd
    try:
        cwd = validate_cwd(cwd)
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}

    namespace = event.get("namespace") or os.environ.get("OCTOWIZ_MEMORY_NAMESPACE", "gfe")
    context = event.get("context")

    doctrine = None
    warning = None

    base_url = os.environ.get("LITELLM_BASE_URL", "")
    if base_url:
        api_key = os.environ.get("LITELLM_API_KEY", "")
        try:
            from memory_client import namespace as _ns
            doctrine = _ns.load_role_bundle(base_url, api_key, "reviewer", namespace)
        except Exception as exc:
            doctrine = None
            warning = str(exc)

    suggested_prompt = f"[octowiz.review] Review the work in {cwd}"
    if event.get("sessionId"):
        suggested_prompt += f" (session {event['sessionId']})"
    if context:
        suggested_prompt += f"\n\nContext:\n{context}"

    result: Dict = {
        "status": "ok",
        "role": "reviewer",
        "cwd": cwd,
        "sessionId": event.get("sessionId"),
        "namespace": namespace,
        "doctrine": doctrine,
        "suggested_prompt": suggested_prompt,
    }
    if warning is not None:
        result["warning"] = warning
    return result
