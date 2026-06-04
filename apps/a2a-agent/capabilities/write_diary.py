"""octowiz.write_diary capability — writes agent diary entries to LiteLLM Memory or local JSONL."""
import asyncio
import json
import os
import time
from pathlib import Path
from typing import Dict, Optional

_VALID_ENTRY_TYPES = {"working", "long_term"}


def _write_to_litellm(
    base_url: str,
    api_key: Optional[str],
    entry_type: str,
    content: str,
    session_id: Optional[str],
    metadata: Optional[dict],
) -> dict:
    import httpx

    slug = (session_id or "unknown").replace("/", "-")[:32]
    bucket = str(int(time.time() // 3600))  # 1-hour buckets
    key = f"agent:octowiz:diary:{entry_type}:{slug}:{bucket}"
    value = json.dumps({
        "content": content,
        "sessionId": session_id,
        "metadata": metadata or {},
        "ts": int(time.time()),
    })
    url = f"{base_url.rstrip('/')}/v1/memory/{key}"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    with httpx.Client(timeout=10) as client:
        resp = client.put(url, json={"value": value}, headers=headers)
        resp.raise_for_status()
    return {"backend": "litellm", "key": key}


def _write_to_local(
    entry_type: str,
    content: str,
    session_id: Optional[str],
    metadata: Optional[dict],
) -> dict:
    cache_dir = Path.home() / ".cache" / "octowiz" / "diary"
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{entry_type}.jsonl"
    record = {
        "content": content,
        "sessionId": session_id,
        "metadata": metadata or {},
        "ts": int(time.time()),
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    return {"backend": "local", "path": str(path)}


async def handle_write_diary(event: Dict) -> Dict:
    entry_type = event.get("entry_type", "")
    content = event.get("content", "")
    session_id = event.get("sessionId") or None
    metadata = event.get("metadata") or None

    if entry_type not in _VALID_ENTRY_TYPES:
        return {"status": "error", "message": "entry_type must be 'working' or 'long_term'"}

    if not content or not isinstance(content, str):
        return {"status": "error", "message": "content is required"}

    base_url = os.environ.get("LITELLM_BASE_URL", "")
    api_key = os.environ.get("LITELLM_API_KEY") or None

    warning: Optional[str] = None

    if base_url:
        try:
            backend_info = await asyncio.to_thread(
                _write_to_litellm, base_url, api_key, entry_type, content, session_id, metadata
            )
            return {"status": "ok", "entry_type": entry_type, **backend_info}
        except Exception as exc:
            warning = f"LiteLLM write failed, used local fallback: {exc}"

    backend_info = await asyncio.to_thread(
        _write_to_local, entry_type, content, session_id, metadata
    )
    result: Dict = {"status": "ok", "entry_type": entry_type, **backend_info}
    if warning is not None:
        result["warning"] = warning
    return result
