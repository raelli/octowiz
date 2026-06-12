"""Shared doctrine-enrichment logic for plan/review capabilities."""
import os
from typing import Any, Callable, Dict, Optional


async def handle_doctrine_enrichment(
    event: Dict,
    role: str,
    prompt_builder: Callable[[Dict, Any], str],
    *,
    source: Optional[Any] = None,
) -> Dict:
    """Fetch a doctrine bundle for *role* and build a suggested prompt.

    Returns {"status": "ok", "role", "namespace", "doctrine", "suggested_prompt"}.
    On fetch failure: doctrine is None and "warning" key is added.
    If LITELLM_BASE_URL is unset, doctrine is None with no warning.
    """
    namespace = event.get("namespace") or os.environ.get("OCTOWIZ_MEMORY_NAMESPACE", "gfe")
    context = event.get("context")

    doctrine = None
    warning = None

    if os.environ.get("LITELLM_BASE_URL"):
        try:
            from memory_client.cache import get_bundle
            doctrine = get_bundle(role, namespace, source=source)
        except Exception as exc:
            warning = str(exc)

    result: Dict = {
        "status": "ok",
        "role": role,
        "namespace": namespace,
        "doctrine": doctrine,
        "suggested_prompt": prompt_builder(event, context),
    }
    if warning is not None:
        result["warning"] = warning
    return result
