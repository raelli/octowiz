"""JSON-RPC 2.0 helpers for the Octowiz A2A endpoint."""
import json
from typing import Any, Dict, Optional
from uuid import uuid4


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
