"""octowiz.dispatch capability — fire-and-observe session wrapper.

Implements an explicit DispatchSession state machine with named states and
transitions, replacing the previous while-loop with implicit branching.
"""
import asyncio
import logging
import os
import time
from enum import Enum
from typing import Any, Dict, Optional

import session_owners
from path_guard import validate_cwd
from providers.claude_agent_view.status import is_terminal, is_error

_DEFAULT_POLL_INTERVAL = float(os.environ.get("OCTOWIZ_DISPATCH_POLL_INTERVAL", "5"))
_DEFAULT_TIMEOUT = float(os.environ.get("OCTOWIZ_DISPATCH_TIMEOUT", "300"))

logger = logging.getLogger(__name__)


def _make_provider():
    from providers.claude_agent_view.provider import ClaudeAgentViewProvider
    return ClaudeAgentViewProvider()


def _dispatch_and_register(provider: Any, task: str, cwd: str, principal: str) -> str:
    """Dispatch a session and register ownership in a single thread.

    Running both steps atomically (from the event loop's perspective) prevents
    a cancellation window between the executor await and session_owners.register():
    if the coroutine is cancelled mid-await, this thread still completes and the
    session is tracked, so manage_agents log/stop/rm calls are not rejected.
    """
    session_id = provider.dispatch(task, cwd)
    if session_id:
        session_owners.register(session_id, principal)
    return session_id


class DispatchSessionState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    NEEDS_INPUT = "needs_input"
    DONE = "done"
    TIMED_OUT = "timed_out"
    ORPHANED = "orphaned"  # lease expired before terminal state


class DispatchSession:
    """Explicit state machine for a single dispatched Claude CLI session.

    States:
        PENDING    — created, not yet started
        RUNNING    — session started, polling for completion
        NEEDS_INPUT — session is waiting for user input (terminal for this session)
        DONE       — session reached a terminal status (completed or error)
        TIMED_OUT  — deadline elapsed before terminal state was reached
        ORPHANED   — lease expired before terminal state (server restart scenario)
    """

    def __init__(
        self,
        task: str,
        cwd: str,
        principal: str,
        *,
        provider: Any,
        poll_interval: float,
        timeout: float,
    ):
        self.task = task
        self.cwd = cwd
        self.principal = principal
        self._provider = provider
        self._poll_interval = poll_interval
        self._timeout = timeout

        self.session_id: Optional[str] = None
        self.state: DispatchSessionState = DispatchSessionState.PENDING
        self._output: str = ""
        self._is_session_error: bool = False
        # Tracks whether get_status has ever returned a non-None session object.
        # A session that was never observed when the deadline elapses is ORPHANED
        # (the lease was held but the supervisor never acknowledged the session —
        # indicating the server restarted or the session was lost before it could
        # be picked up). A session that was observed at least once but did not
        # reach a terminal state within the deadline is TIMED_OUT.
        self._ever_observed: bool = False

    async def start(self) -> None:
        """Start the Claude CLI session. Transitions PENDING -> RUNNING.

        Raises RuntimeError if the session fails to start (no session ID).
        The caller is responsible for converting the exception to an error artifact.
        """
        _loop = asyncio.get_running_loop()
        session_id = await _loop.run_in_executor(
            None, _dispatch_and_register,
            self._provider, self.task, self.cwd, self.principal,
        )
        if not session_id:
            raise RuntimeError("no session ID returned")

        self.session_id = session_id
        self.state = DispatchSessionState.RUNNING

    async def poll(self) -> DispatchSessionState:
        """Single poll tick. Fetches output exactly once, evaluates state.

        Returns the new state. Callers should stop looping when the returned
        state is terminal (DONE, NEEDS_INPUT, TIMED_OUT, ORPHANED).
        """
        _loop = asyncio.get_running_loop()

        # Fetch status.
        session = await _loop.run_in_executor(
            None, self._provider.get_status, self.session_id
        )
        if session is None:
            # Session not yet visible in the supervisor — stay RUNNING.
            return DispatchSessionState.RUNNING

        # Mark that we have successfully observed a real session object at least once.
        self._ever_observed = True

        # Fetch output exactly once per poll tick.
        try:
            self._output = await _loop.run_in_executor(
                None, self._provider.get_logs, self.session_id
            )
        except Exception:
            self._output = ""

        if session.needs_input:
            self.state = DispatchSessionState.NEEDS_INPUT
            return self.state

        if is_error(session.status):
            self._is_session_error = True
            self.state = DispatchSessionState.DONE
            return self.state

        if is_terminal(session.status):
            self.state = DispatchSessionState.DONE
            return self.state

        return DispatchSessionState.RUNNING

    async def run(self) -> Dict:
        """Drive the session to a terminal state. Returns the result artifact.

        Owner registration happens in start(); deregistration happens only
        for ORPHANED (via mark_orphaned()). TIMED_OUT, DONE, and NEEDS_INPUT
        all retain ownership so the caller can still invoke manage_agents
        logs/rm (issue #55).
        """
        deadline = time.monotonic() + self._timeout

        while time.monotonic() < deadline:
            await asyncio.sleep(self._poll_interval)
            current_state = await self.poll()

            if current_state == DispatchSessionState.NEEDS_INPUT:
                # Retain ownership — caller may still interact via manage_agents.
                return {
                    "status": "needs-input",
                    "session_id": self.session_id,
                    "output": self._output,
                }

            if current_state == DispatchSessionState.DONE:
                if self._is_session_error:
                    # Retain ownership — caller may still retrieve logs via manage_agents.
                    return {
                        "status": "error",
                        "session_id": self.session_id,
                        "output": self._output,
                    }
                # Retain ownership — caller may still run manage_agents logs/rm.
                return {
                    "status": "completed",
                    "session_id": self.session_id,
                    "output": self._output,
                }

        # Deadline elapsed. If the session was never observed by the supervisor
        # (get_status always returned None), the lease is held but the session is
        # lost — this is the ORPHANED state (e.g., server restarted mid-poll).
        # If the session was observed at least once, it simply ran too long: TIMED_OUT.
        if not self._ever_observed:
            return self.mark_orphaned()

        # TIMED_OUT — session was running but did not complete within the deadline.
        # Retain ownership for caller cleanup.
        self.state = DispatchSessionState.TIMED_OUT
        return {
            "status": "error",
            "session_id": self.session_id,
            "message": f"timeout after {self._timeout}s waiting for session to complete",
        }

    def mark_orphaned(self) -> Dict:
        """Transition to ORPHANED state and return the error artifact.

        Called when the lease is known to have expired before a terminal state
        was reached (e.g., server restart detected mid-poll). Deregisters
        ownership since the session is no longer recoverable.
        """
        self.state = DispatchSessionState.ORPHANED
        logger.warning(
            "[octowiz] dispatch orphaned: session %s — lease expired before terminal state",
            self.session_id,
        )
        if self.session_id:
            session_owners.deregister(self.session_id)
        return {"status": "error", "session_id": self.session_id, "message": "dispatch timed out (orphaned)"}


async def handle_dispatch(
    event: Dict,
    *,
    provider: Any = None,
    poll_interval: Optional[float] = None,
    timeout: Optional[float] = None,
) -> Dict:
    task = event.get("task", "")
    cwd = event.get("cwd", "")

    if not task:
        return {"status": "error", "message": "task is required"}
    if not cwd:
        return {"status": "error", "message": "cwd is required"}
    if task.startswith("-"):
        return {"status": "error", "message": "task must not start with '-'"}

    # P1: validate cwd against OCTOWIZ_ALLOWED_ROOTS before dispatching.
    try:
        cwd = validate_cwd(cwd)
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}

    if provider is None:
        provider = _make_provider()
    if poll_interval is None:
        poll_interval = _DEFAULT_POLL_INTERVAL
    if timeout is None:
        timeout = _DEFAULT_TIMEOUT

    principal = event.get("_principal", "")

    session = DispatchSession(
        task,
        cwd,
        principal,
        provider=provider,
        poll_interval=poll_interval,
        timeout=timeout,
    )

    try:
        await session.start()
    except Exception as exc:
        return {"status": "error", "message": f"failed to start session: {exc}"}

    return await session.run()
