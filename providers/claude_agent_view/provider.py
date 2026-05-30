# providers/claude_agent_view/provider.py
from __future__ import annotations

import re
import subprocess
from typing import List, Optional

from .parser import parse_sessions
from .session import AgentSession


def _run_claude(args: List[str]) -> str:
    """Run `claude <args>` and return stdout. Single mock seam for all subprocess calls."""
    result = subprocess.run(
        ["claude"] + args,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout.strip()


_RUN_ID_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$')


def _validate_run_id(run_id: str) -> None:
    if not _RUN_ID_RE.fullmatch(run_id):
        raise ValueError(f"Invalid run_id format: {run_id!r}")


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
        """Start a new background session for task in repo. Returns the session id."""
        if repo.startswith("-"):
            raise ValueError(f"Invalid repo path: {repo!r}")
        if task.startswith("-"):
            raise ValueError(f"task must not start with '-': {task!r}")
        output = _run_claude(["--bg", "--cwd", repo, "--", task])
        return output.splitlines()[0].strip() if output else ""

    def get_status(self, run_id: str) -> Optional[AgentSession]:
        """Return the session for run_id, or None if not found."""
        for s in self.list_sessions():
            if s.id == run_id:
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
