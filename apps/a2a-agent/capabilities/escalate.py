"""octowiz.escalate_to_aelli capability — forward a strategic question to ÆLLI via A2A."""
import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

_AELLI_BASE_URL_DEFAULT = "http://localhost:3456"


def _make_auth_headers(auth_token: str) -> Dict[str, str]:
    """Return auth headers matching bridge.py's routing logic.

    Direct AELLI (no AELLI_LITELLM_BASE) uses x-aelli-secret.
    LiteLLM gateway uses Authorization: Bearer.
    """
    if not auth_token:
        return {}
    if os.environ.get("AELLI_LITELLM_BASE", ""):
        return {"Authorization": f"Bearer {auth_token}"}
    return {"x-aelli-secret": auth_token}


def _persist_queued(question: str, context: Any, session_id: Optional[str],
                    priority: str, reason: str) -> None:
    """Write a failed escalation to the local durable queue before returning queued status."""
    queue_dir = Path.home() / ".cache" / "octowiz"
    queue_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "question": question,
        "context": context,
        "sessionId": session_id,
        "priority": priority,
        "ts": int(time.time()),
        "reason": reason,
    }
    queue_path = queue_dir / "escalation-queue.jsonl"
    with open(queue_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


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

    headers: Dict[str, str] = {"Content-Type": "application/json", **_make_auth_headers(auth_token)}
    url = f"{base_url}/a2a/aelli"

    try:
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None, _post_sync, url, payload, headers
        )
        return {"status": "escalated", "delivery": "sent", "aelli_response": response.json()}
    except Exception as exc:
        reason = str(exc)
        print(f"[octowiz.escalate] ÆLLI unreachable: {reason}", file=sys.stderr)
        await asyncio.get_running_loop().run_in_executor(
            None, _persist_queued, question, context, session_id, priority, reason
        )
        return {
            "status": "escalated",
            "delivery": "queued",
            "warning": "ÆLLI unreachable — escalation logged locally",
        }
