"""JSON-RPC 2.0 helpers and the capability artifact contract.

This module owns the wire vocabulary of the A2A server: the JSON-RPC
request/response shapes (parse_event / make_response) and the capability
error artifact (err / require). The Node daemon maps artifact
status == "error" to the task queue's error state (src/daemon.js) — that
cross-language contract is built here and nowhere else.
"""
import json
from typing import Any, Dict, Optional
from uuid import uuid4


def err(message: Optional[str] = None, **fields) -> Dict:
    """Canonical capability error artifact: {"status": "error", ...}."""
    artifact: Dict[str, Any] = {"status": "error", **fields}
    if message is not None:
        artifact["message"] = message
    return artifact


def require(event: Dict, *names: str) -> Optional[Dict]:
    """Error artifact for the first missing/empty field, or None if all present."""
    for name in names:
        if not event.get(name):
            return err(f"{name} is required")
    return None


def parse_event(body: Dict) -> Optional[Dict]:
    """Extract the Octowiz event from an A2A JSON-RPC request body."""
    try:
        text = body["params"]["message"]["parts"][0]["text"]
        return json.loads(text)
    except (KeyError, TypeError, json.JSONDecodeError):
        return None


def make_response(req_id: Any, artifact: Any, session_id: Optional[str] = None) -> Dict:
    """Build a JSON-RPC 2.0 task result."""
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "kind": "task",
            "id": str(uuid4()),
            "contextId": session_id or str(uuid4()),
            "status": {"state": "completed"},
            "artifacts": [
                {
                    "artifactId": str(uuid4()),
                    "name": "advisory",
                    "parts": [{"kind": "text", "text": json.dumps(artifact or {})}],
                }
            ],
        },
    }
