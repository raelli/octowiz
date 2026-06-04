"""octowiz.load_memory capability — fetches doctrine bundles and project rules from LiteLLM Memory."""
import asyncio
import os
from typing import Optional

import httpx

# Import as module object so patches on memory_client.namespace.* take effect at call time.
from memory_client import namespace as _ns


async def handle_load_memory(event: dict) -> dict:
    base_url = os.environ.get("LITELLM_BASE_URL", "")
    if not base_url:
        return {"status": "unavailable", "message": "LITELLM_BASE_URL not configured"}

    api_key = os.environ.get("LITELLM_API_KEY", "")
    role = event.get("role", "implementer")
    ns = event.get("namespace") or os.environ.get("OCTOWIZ_MEMORY_NAMESPACE", "gfe")
    project_id: Optional[str] = event.get("project_id")

    loop = asyncio.get_event_loop()

    try:
        bundle = await loop.run_in_executor(
            None, _ns.load_role_bundle, base_url, api_key, role, ns
        )

        result: dict = {"status": "ok", "role": role, "namespace": ns, "bundle": bundle}

        if project_id:
            rules = await loop.run_in_executor(
                None, _ns.load_project_rules, base_url, api_key, project_id
            )
            result["rules"] = rules

        return result

    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        return {"status": "error", "message": str(exc)}
