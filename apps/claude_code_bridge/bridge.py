#!/usr/bin/env python3
"""
Octowiz Bridge — forwards Claude Code hook events to the Octowiz A2A server.

Reads JSON from stdin (Claude Code hook format), normalises to an OctowizEvent,
POSTs to $OCTOWIZ_A2A_URL/a2a/octowiz, and writes a systemMessage to stdout
if the advisor returns advice. Exits 0 always — never blocks the developer.
"""
import json
import os
import subprocess
import sys
import uuid
from typing import Dict, Optional

TOOL_EVENT_MAP = {
    "Edit": "file-edit",
    "Write": "file-write",
    "MultiEdit": "file-edit",
    "NotebookEdit": "file-edit",
}


def _git_context(cwd: str) -> Dict[str, str]:
    ctx: Dict[str, str] = {"repoRoot": cwd, "branch": ""}
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd, capture_output=True, text=True, timeout=1,
        )
        if r.returncode == 0:
            ctx["repoRoot"] = r.stdout.strip()
    except Exception:
        pass
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd, capture_output=True, text=True, timeout=1,
        )
        if r.returncode == 0:
            ctx["branch"] = r.stdout.strip()
    except Exception:
        pass
    return ctx


def _build_event(data: Dict) -> Optional[Dict]:
    hook = data.get("hook_event_name", "")
    session_id = data.get("session_id", "")
    cwd = data.get("cwd", os.getcwd())
    git_ctx = _git_context(cwd)

    if hook == "PostToolUse":
        tool = data.get("tool_name", "")
        tool_input = data.get("tool_input", {})
        event_type = TOOL_EVENT_MAP.get(tool, "tool-used")
        event: Dict = {
            "type": event_type,
            "capability": "octowiz.advise",
            "sessionId": session_id,
            **git_ctx,
        }
        path = tool_input.get("file_path") or tool_input.get("notebook_path")
        if path:
            event["live_modified_files"] = [path]
        return event

    if hook == "UserPromptSubmit":
        return {
            "type": "prompt",
            "capability": "octowiz.advise",
            "sessionId": session_id,
            "prompt_summary": data.get("prompt", "")[:200],
            **git_ctx,
        }

    if hook == "SessionStart":
        return {
            "type": "session-start",
            "capability": "octowiz.advise",
            "sessionId": session_id,
            **git_ctx,
        }

    return None


def _post_event(url: str, event: Dict) -> Optional[Dict]:
    import httpx

    body = {
        "jsonrpc": "2.0",
        "method": "octowiz/event",
        "id": str(uuid.uuid4()),
        "params": {"message": {"parts": [{"text": json.dumps(event)}]}},
    }
    headers = {}
    secret = os.environ.get("OCTOWIZ_INBOUND_SECRET", "")
    if secret:
        headers["x-octowiz-secret"] = secret
    try:
        resp = httpx.post(f"{url}/a2a/octowiz", json=body, headers=headers, timeout=5)
        resp.raise_for_status()
        artifacts = resp.json().get("result", {}).get("artifacts", [])
        if not artifacts:
            return None
        text = artifacts[0].get("parts", [{}])[0].get("text", "{}")
        result = json.loads(text)
        return result if result.get("type") else None
    except Exception:
        return None


def main() -> int:
    url = os.environ.get("OCTOWIZ_A2A_URL", "").rstrip("/")
    if not url:
        return 0

    # Warn on cleartext HTTP to non-local endpoints — secret sent in plaintext.
    # Parse the URL to get the exact hostname; string prefix checks are bypassed by
    # hosts like localhost.evil.com or 127.0.0.1.attacker.com (issue #53).
    # Warning goes to stderr to avoid corrupting the stdout JSON channel.
    try:
        from urllib.parse import urlparse as _urlparse
        _parsed = _urlparse(url)
        _local_hosts = {"localhost", "127.0.0.1", "::1", "[::1]"}
        if _parsed.scheme == "http" and _parsed.hostname not in _local_hosts:
            print(
                "[octowiz] WARNING: OCTOWIZ_A2A_URL uses plain HTTP; "
                "the inbound secret will be sent in cleartext. Use HTTPS for non-local deployments.",
                file=sys.stderr,
            )
    except Exception:
        pass

    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0

    event = _build_event(data)
    if event is None:
        return 0

    advice = _post_event(url, event)
    if advice:
        advice_type = advice.get("type", "advisory")
        message = advice.get("message", "")
        print(json.dumps({"systemMessage": f"[octowiz/{advice_type}] {message}"}))

    return 0


if __name__ == "__main__":
    sys.exit(main())
