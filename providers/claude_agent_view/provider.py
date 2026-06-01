# providers/claude_agent_view/provider.py
from __future__ import annotations

import re
import subprocess
import time
from typing import List, Optional

from .parser import parse_sessions
from .session import AgentSession

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
_SESSION_RE = re.compile(r"backgrounded\s*[·•]\s*(\S+)")


def _run_claude(args: List[str], cwd: Optional[str] = None) -> str:
    """Run `claude <args>` and return stdout. Single mock seam for all subprocess calls."""
    result = subprocess.run(
        ["claude"] + args,
        capture_output=True,
        text=True,
        timeout=30,
        cwd=cwd,
    )
    return result.stdout.strip()


_RUN_ID_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$')


def _validate_run_id(run_id: str) -> None:
    if not _RUN_ID_RE.fullmatch(run_id):
        raise ValueError(f"Invalid run_id format: {run_id!r}")


def _resolve_full_session_id(
    short_id: str,
    provider: "ClaudeAgentViewProvider",
    retries: int = 5,
    delay: float = 0.5,
) -> str:
    """Resolve a banner short-prefix to the full session UUID.

    The claude --bg banner emits only the UUID prefix (e.g. 'e5694b8e') while
    claude agents --json returns the full UUID. We retry briefly to bridge the
    gap between session start and it appearing in the agent list.

    Exact match is checked before prefix match so that a session whose ID merely
    starts with short_id (e.g. 'bg-xyz-old') is not returned ahead of an exact
    match ('bg-xyz') that appears later in the list.
    """
    for _ in range(retries):
        sessions = provider.list_sessions()
        for s in sessions:
            if s.id == short_id:
                return s.id
        for s in sessions:
            if s.id.startswith(short_id):
                return s.id
        time.sleep(delay)
    return short_id  # fall back; get_status exact-then-prefix will still work


class ClaudeAgentViewProvider:
    """Execution provider backed by Claude Code Agent View (claude agents CLI)."""

    def list_sessions(self) -> List[AgentSession]:
        """Return all current agent sessions. Returns [] if claude CLI is absent or errors."""
        try:
            output = _run_claude(["agents", "--json"])
            return parse_sessions(output)
        except Exception:
            return []

    def dispatch(self, task: str, repo: str) -> str:
        """Start a new background session for task in repo. Returns the full session id."""
        if repo.startswith("-"):
            raise ValueError(f"Invalid repo path: {repo!r}")
        if task.startswith("-"):
            raise ValueError(f"task must not start with '-': {task!r}")
        output = _run_claude(["--bg", "--", task], cwd=repo)
        clean = _ANSI_RE.sub("", output)
        m = _SESSION_RE.search(clean)
        if not m:
            return ""
        # Resolve banner short-prefix to the full UUID in claude agents --json.
        return _resolve_full_session_id(m.group(1), self)

    def get_status(self, run_id: str) -> Optional[AgentSession]:
        """Return the session for run_id, or None if not found."""
        sessions = self.list_sessions()
        # Exact match first — avoids returning a prefix-collision session.
        for s in sessions:
            if s.id == run_id:
                return s
        # Prefix fallback for short IDs that weren't resolved at dispatch time.
        for s in sessions:
            if s.id.startswith(run_id):
                return s
        return None

    def get_logs(self, run_id: str) -> str:
        """Return stdout log for run_id."""
        _validate_run_id(run_id)
        return _run_claude(["logs", "--", run_id])

    def stop(self, run_id: str) -> None:
        """Stop the session with run_id."""
        _validate_run_id(run_id)
        _run_claude(["stop", "--", run_id])
