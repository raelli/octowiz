#!/usr/bin/env python3
"""
Octowiz Bridge — forwards Claude Code hook events to AELLI's dev-advisor.

Reads JSON from stdin (Claude Code hook format), normalises to an event,
POSTs to $AELLI_DEV_ADVISOR_URL (default http://localhost:3456/a2a/dev-advisor),
and writes a systemMessage to stdout if the advisor returns advice.
Exits 0 always — never blocks the developer.
"""
import json
import os
import subprocess
import sys
import uuid
from typing import Dict, Optional


def _verbose_log(msg: str) -> None:
    """Write a diagnostic message to stderr when OCTOWIZ_VERBOSE is set."""
    if os.environ.get("OCTOWIZ_VERBOSE", "").lower() in ("1", "true", "yes"):
        print(f"[octowiz] {msg}", file=sys.stderr)


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
            "sessionId": session_id,
            "prompt_summary": data.get("prompt", "")[:200],
            **git_ctx,
        }

    if hook == "SessionStart":
        return {
            "type": "session-start",
            "sessionId": session_id,
            **git_ctx,
        }

    return None


def _post_event(url: str, event: Dict) -> Optional[Dict]:
    import httpx

    body = {
        "jsonrpc": "2.0",
        "method": "message/send",
        "id": str(uuid.uuid4()),
        "params": {"message": {"parts": [{"kind": "text", "text": json.dumps(event)}]}},
    }
    headers = {}
    token = os.environ.get("AELLI_AUTH_TOKEN", "")
    if token:
        headers["x-aelli-secret"] = token
    try:
        resp = httpx.post(url, json=body, headers=headers, timeout=5)
        resp.raise_for_status()
        artifacts = resp.json().get("result", {}).get("artifacts", [])
        if not artifacts:
            _verbose_log("advisory delivered; no advice returned")
            return None
        text = artifacts[0].get("parts", [{}])[0].get("text", "{}")
        result = json.loads(text)
        if result.get("type"):
            _verbose_log(f"advisory delivered: type={result['type']}")
            return result
        _verbose_log("advisory delivered; response has no type")
        return None
    except Exception as exc:
        _verbose_log(f"advisory delivery failed: {exc}")
        return None


def main() -> int:
    url = os.environ.get("AELLI_DEV_ADVISOR_URL", "http://localhost:3456/a2a/dev-advisor").rstrip("/")

    # Warn on cleartext HTTP to non-local endpoints — token sent in plaintext.
    # Parse the URL to get the exact hostname; string prefix checks are bypassed by
    # hosts like localhost.evil.com or 127.0.0.1.attacker.com.
    # Warning goes to stderr to avoid corrupting the stdout JSON channel.
    try:
        from urllib.parse import urlparse as _urlparse
        _parsed = _urlparse(url)
        _local_hosts = {"localhost", "127.0.0.1", "::1", "[::1]"}
        if _parsed.scheme == "http" and _parsed.hostname not in _local_hosts:
            print(
                "[octowiz] WARNING: AELLI_DEV_ADVISOR_URL uses plain HTTP; "
                "the auth token will be sent in cleartext. Use HTTPS for non-local deployments.",
                file=sys.stderr,
            )
    except Exception:
        pass

    try:
        data = json.load(sys.stdin)
    except Exception as exc:
        _verbose_log(f"could not parse stdin: {exc}")
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
