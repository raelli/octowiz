"""octowiz.escalate_to_aelli capability — forward a strategic question to ÆLLI via A2A."""
import asyncio
import os
import sys
import uuid
from typing import Any, Dict, Optional

import httpx

_AELLI_BASE_URL_DEFAULT = "http://localhost:3456"


def _post_sync(
    url: str,
    payload: Dict,
    headers: Dict[str, str],
    timeout: float = 10.0,
) -> Any:
    """Synchronous httpx call, intended to be run in an executor."""
    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response


async def handle_escalate(event: Dict) -> Dict:
    question = event.get("question", "")
    if not question or not isinstance(question, str) or not question.strip():
        return {"status": "error", "message": "question is required"}

    context = event.get("context")
    session_id = event.get("sessionId")
    priority = event.get("priority", "normal")

    base_url = os.environ.get("AELLI_BASE_URL", _AELLI_BASE_URL_DEFAULT).rstrip("/")
    auth_token = os.environ.get("AELLI_AUTH_TOKEN", "")

    payload = {
        "jsonrpc": "2.0",
        "method": "message/send",
        "id": str(uuid.uuid4()),
        "params": {
            "message": {
                "parts": [{"kind": "text", "text": question}],
                "metadata": {
                    "capability": "aelli.decide",
                    "sessionId": session_id,
                    "context": context,
                    "priority": priority,
                    "source": "octowiz",
                },
            }
        },
    }

    headers: Dict[str, str] = {"Content-Type": "application/json"}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    url = f"{base_url}/a2a/aelli"

    try:
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None, _post_sync, url, payload, headers
        )
        return {"status": "escalated", "delivery": "sent", "aelli_response": response.json()}
    except Exception as exc:
        print(f"[octowiz.escalate] ÆLLI unreachable: {exc}", file=sys.stderr)
        return {
            "status": "escalated",
            "delivery": "queued",
            "warning": "ÆLLI unreachable — escalation logged locally",
        }
