"""AgentRunProvider — the named seam every execution provider satisfies.

Both adapters (ClaudeAgentViewProvider, SandcastleProvider) run an agent task
somewhere, expose its progress, and stop it. Capabilities consume this
protocol and the canonical status vocabulary below; they never import a
provider's native status module.

Native status vocabularies stay inside each provider (the Claude CLI speaks
busy/idle/stopped, Sandcastle speaks running/completed/timed_out) — each
provider's ``to_run_state`` maps them onto the canonical trio, and ``RunState``
keeps the native value in ``raw_status`` for artifacts and diagnostics.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable

# Canonical run statuses — the only vocabulary capabilities reason about.
RUNNING = "running"
COMPLETED = "completed"
ERROR = "error"

TERMINAL_STATUSES: frozenset = frozenset({COMPLETED, ERROR})
ERROR_STATUSES: frozenset = frozenset({ERROR})


def is_terminal(status: str) -> bool:
    """True if the run will not progress further."""
    return status in TERMINAL_STATUSES


def is_error(status: str) -> bool:
    """True if the run ended in failure (including timeouts)."""
    return status in ERROR_STATUSES


@dataclass
class RunState:
    """Canonical snapshot of one agent run.

    status:      canonical — running | completed | error
    raw_status:  the provider-native status, preserved for artifacts
    needs_input: the run is blocked waiting for human input
    """

    status: str
    raw_status: str
    needs_input: bool = False


@runtime_checkable
class AgentRunProvider(Protocol):
    """Run an agent task somewhere, watch it, stop it."""

    def dispatch(self, task: str, cwd: str, **kwargs) -> str:
        """Start a run; returns its run/session id."""
        ...

    def poll_run(self, run_id: str) -> Optional[RunState]:
        """Canonical state of the run, or None if not yet observable."""
        ...

    def get_logs(self, run_id: str) -> str:
        """Captured output so far ('' when unavailable)."""
        ...

    def stop(self, run_id: str) -> None:
        """Terminate the run. Idempotent; unknown ids are a no-op."""
        ...
