#!/usr/bin/env python3
"""
Octowiz Bridge — forwards Claude Code hook events to AELLI's dev-advisor.

Reads JSON from stdin (Claude Code hook format), normalises to an event,
POSTs to $AELLI_DEV_ADVISOR_URL (default http://localhost:3456/a2a/dev-advisor),
and writes a systemMessage to stdout if the advisor returns advice.
Exits 0 always — never blocks the developer.
"""
import datetime
import json
import os
import subprocess
import sys
import uuid
from typing import Dict, Optional

_BOLD   = "\033[1m"
_PURPLE = "\033[38;5;135m"
_DIM    = "\033[2m"
_RESET  = "\033[0m"
_BADGE       = f"{_BOLD}{_PURPLE}[--*]{_RESET}"
_AELLI_BADGE = f"{_BOLD}{_PURPLE}[æ]{_RESET}"


def _log(msg: str) -> None:
    """Write a purple-badged message to stderr — always visible."""
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"{_BADGE} {_DIM}{ts}{_RESET} {msg}", file=sys.stderr)


def _verbose_log(msg: str) -> None:
    """Write a purple-badged diagnostic message to stderr when OCTOWIZ_VERBOSE is set."""
    if os.environ.get("OCTOWIZ_VERBOSE", "").lower() in ("1", "true", "yes"):
        _log(msg)


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
        # Include live_modified_files so SpecDeviationRule can cross-reference
        # modified files against the prompt intent on the same event.
        return {
            "type": "prompt",
            "sessionId": session_id,
            "prompt_summary": data.get("prompt", "")[:200],
            "live_modified_files": _git_modified_files(cwd),
            **git_ctx,
        }

    if hook == "SessionStart":
        return {
            "type": "session-start",
            "sessionId": session_id,
            **git_ctx,
        }

    return None


def _git_modified_files(cwd: str) -> list:
    """Return list of modified file paths from git status --porcelain."""
    try:
        r = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=cwd, capture_output=True, text=True, timeout=1,
        )
        if r.returncode != 0:
            return []
        files = []
        for line in r.stdout.splitlines():
            if len(line) > 3:
                files.append(line[3:].strip())
        return files
    except Exception:
        return []


def _post_event(url: str, event: Dict) -> Optional[Dict]:
    body = {
        "jsonrpc": "2.0",
        "method": "message/send",
        "id": str(uuid.uuid4()),
        "params": {
            "message": {
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "parts": [{"kind": "text", "text": json.dumps(event)}],
            }
        },
    }
    headers = {}
    token = os.environ.get("AELLI_AUTH_TOKEN", "")
    if token:
        # Route through LiteLLM gateway → use LiteLLM virtual key auth
        # Route directly to AELLI → use AELLI inbound secret
        if os.environ.get("AELLI_LITELLM_BASE", ""):
            headers["Authorization"] = f"Bearer {token}"
        else:
            headers["x-aelli-secret"] = token
    try:
        import httpx
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


def _resolve_advisor_url() -> str:
    """Mirror the URL resolution in src/a2a-client.js:
    AELLI_LITELLM_BASE takes priority (gateway route); fall back to
    AELLI_DEV_ADVISOR_URL; final default is direct localhost dev-advisor."""
    litellm_base = os.environ.get("AELLI_LITELLM_BASE", "").rstrip("/")
    if litellm_base:
        return f"{litellm_base}/a2a/aelli-dev-advisor/message/send"
    return os.environ.get("AELLI_DEV_ADVISOR_URL", "http://localhost:3456/a2a/dev-advisor").rstrip("/")


def _resolve_router_url() -> Optional[str]:
    """Mirror ROUTER_URL resolution in src/a2a-client.js."""
    router_url = os.environ.get("AELLI_ROUTER_URL", "").rstrip("/")
    if router_url:
        return router_url
    litellm_base = os.environ.get("AELLI_LITELLM_BASE", "").rstrip("/")
    if litellm_base:
        return f"{litellm_base}/a2a/aelli-router/message/send"
    return None


def _route_event(task_kind: str, data: Dict) -> Optional[Dict]:
    """Bounded-blocking routing call — blocks up to timeout=2s, then returns None (fail-open).
    Returns the routing decision dict ({router, tier, model, workflow}) when available so
    the caller can include it in the event forwarded to the dev-advisor. Never raises."""
    url = _resolve_router_url()
    if not url:
        return None
    body = {
        "jsonrpc": "2.0",
        "method": "message/send",
        "params": {
            "message": {
                "parts": [{"kind": "text", "text": json.dumps({"type": "route", "taskKind": task_kind, **data})}],
            }
        },
    }
    headers = {}
    token = os.environ.get("AELLI_AUTH_TOKEN", "")
    if token:
        if os.environ.get("AELLI_LITELLM_BASE", ""):
            headers["Authorization"] = f"Bearer {token}"
        else:
            headers["x-aelli-secret"] = token
    try:
        import httpx
        resp = httpx.post(url, json=body, headers=headers, timeout=2)
        resp.raise_for_status()
        text = resp.text
        import re
        m = re.search(r"^data: (.+)$", text, re.MULTILINE)
        if m:
            decision = json.loads(m.group(1))
            _verbose_log(f"[octowiz - router] {json.dumps(decision)}")
            return decision
    except Exception as exc:
        _verbose_log(f"[octowiz - router] fail-open: {exc}")
    return None


def main() -> int:
    # Warn when routing through LiteLLM but auth token is missing
    if os.environ.get("AELLI_LITELLM_BASE", "") and not os.environ.get("AELLI_AUTH_TOKEN", ""):
        _log(
            "[octowiz - config] AELLI_LITELLM_BASE is set but AELLI_AUTH_TOKEN is missing. "
            "All A2A calls through the LiteLLM gateway will get 401 Unauthorized. "
            "Set AELLI_AUTH_TOKEN to a valid LiteLLM API key."
        )

    url = _resolve_advisor_url()

    # Warn on cleartext HTTP to non-local endpoints — token sent in plaintext.
    # Parse the URL to get the exact hostname; string prefix checks are bypassed by
    # hosts like localhost.evil.com or 127.0.0.1.attacker.com.
    # Warning goes to stderr to avoid corrupting the stdout JSON channel.
    try:
        from urllib.parse import urlparse as _urlparse
        _parsed = _urlparse(url)
        _local_hosts = {"localhost", "127.0.0.1", "::1", "[::1]"}
        if _parsed.scheme == "http" and _parsed.hostname not in _local_hosts:
            _log(
                "[octowiz - config] AELLI_DEV_ADVISOR_URL uses plain HTTP; "
                "the auth token will be sent in cleartext. Use HTTPS for non-local deployments."
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

    # Fire routing decision alongside advisory for UserPromptSubmit events (fail-open).
    # The returned decision is attached to the event so the dev-advisor has routing
    # context (router, tier, model, workflow) when generating its advisory.
    if data.get("hook_event_name") == "UserPromptSubmit":
        routing = _route_event("feature", {
            "content": event.get("prompt_summary", ""),
            "fileCount": len(event.get("live_modified_files", [])),
        })
        if routing:
            event["routingDecision"] = routing

    advice = _post_event(url, event)
    if advice:
        advice_type = advice.get("type", "advisory")
        message = advice.get("message", "")
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        prefix = f"{_AELLI_BADGE} {_DIM}{ts}{_RESET} {_PURPLE}[ÆLLI - {advice_type}]{_RESET}"
        print(json.dumps({"systemMessage": f"{prefix} {message}"}))

    return 0


if __name__ == "__main__":
    sys.exit(main())
