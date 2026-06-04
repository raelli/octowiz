"""octowiz.plan capability — doctrine enrichment for planning tasks."""
import os
from typing import Dict


async def handle_plan(event: Dict) -> Dict:
    task = event.get("task", "")
    if not task:
        return {"status": "error", "message": "task is required"}

    namespace = event.get("namespace") or os.environ.get("OCTOWIZ_MEMORY_NAMESPACE", "gfe")
    context = event.get("context")

    doctrine = None
    warning = None

    base_url = os.environ.get("LITELLM_BASE_URL", "")
    if base_url:
        api_key = os.environ.get("LITELLM_API_KEY", "")
        try:
            from memory_client import namespace as _ns
            doctrine = _ns.load_role_bundle(base_url, api_key, "planner", namespace)
        except Exception as exc:
            doctrine = None
            warning = str(exc)

    suggested_prompt = f"[octowiz.plan] {task}"
    if context:
        suggested_prompt += f"\n\nContext:\n{context}"

    result: Dict = {
        "status": "ok",
        "role": "planner",
        "task": task,
        "namespace": namespace,
        "doctrine": doctrine,
        "suggested_prompt": suggested_prompt,
    }
    if warning is not None:
        result["warning"] = warning
    return result
