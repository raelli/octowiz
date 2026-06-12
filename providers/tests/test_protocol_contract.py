"""Contract tests for the AgentRunProvider seam.

One suite, two adapters: every provider must structurally satisfy the
protocol, and every native status vocabulary must map onto the canonical
trio (running | completed | error) the capabilities reason about.
"""
from providers.protocol import (
    COMPLETED,
    ERROR,
    RUNNING,
    AgentRunProvider,
    RunState,
    is_error,
    is_terminal,
)


class TestCanonicalVocabulary:
    def test_completed_and_error_are_terminal(self):
        assert is_terminal(COMPLETED)
        assert is_terminal(ERROR)

    def test_running_is_not_terminal(self):
        assert not is_terminal(RUNNING)

    def test_only_error_is_error(self):
        assert is_error(ERROR)
        assert not is_error(COMPLETED)
        assert not is_error(RUNNING)


class TestProtocolConformance:
    def test_claude_agent_view_provider_satisfies_protocol(self):
        from providers.claude_agent_view.provider import ClaudeAgentViewProvider
        assert isinstance(ClaudeAgentViewProvider(), AgentRunProvider)

    def test_sandcastle_provider_satisfies_protocol(self):
        from providers.sandcastle.provider import SandcastleProvider
        assert isinstance(SandcastleProvider(), AgentRunProvider)


class TestClaudeAgentViewMapping:
    """to_run_state: claude CLI vocabulary -> canonical."""

    @staticmethod
    def _session(status, needs_input=False):
        from providers.claude_agent_view.session import AgentSession
        return AgentSession(
            id="s1", status=status, branch=None, repo=None,
            needs_input=needs_input, ready_for_review=False, created_at=None,
        )

    def test_none_session_maps_to_none(self):
        from providers.claude_agent_view.provider import to_run_state
        assert to_run_state(None) is None

    def test_native_error_maps_to_error(self):
        from providers.claude_agent_view.provider import to_run_state
        state = to_run_state(self._session("error"))
        assert state == RunState(status=ERROR, raw_status="error", needs_input=False)

    def test_native_terminal_statuses_map_to_completed(self):
        from providers.claude_agent_view.provider import to_run_state
        for native in ("idle", "stopped", "exited"):
            state = to_run_state(self._session(native))
            assert state.status == COMPLETED
            assert state.raw_status == native

    def test_active_statuses_map_to_running(self):
        from providers.claude_agent_view.provider import to_run_state
        for native in ("running", "busy", "waiting"):
            assert to_run_state(self._session(native)).status == RUNNING

    def test_needs_input_passes_through(self):
        from providers.claude_agent_view.provider import to_run_state
        state = to_run_state(self._session("busy", needs_input=True))
        assert state.needs_input is True
        assert state.status == RUNNING


class TestSandcastleMapping:
    """to_run_state: Sandcastle vocabulary -> canonical."""

    def test_completed_maps_to_completed(self):
        from providers.sandcastle.provider import to_run_state
        assert to_run_state("completed") == RunState(
            status=COMPLETED, raw_status="completed", needs_input=False
        )

    def test_error_and_timed_out_map_to_error(self):
        from providers.sandcastle.provider import to_run_state
        for native in ("error", "timed_out"):
            state = to_run_state(native)
            assert state.status == ERROR
            assert state.raw_status == native

    def test_running_maps_to_running(self):
        from providers.sandcastle.provider import to_run_state
        assert to_run_state("running").status == RUNNING

    def test_container_runs_never_need_input(self):
        from providers.sandcastle.provider import to_run_state
        for native in ("running", "completed", "error", "timed_out"):
            assert to_run_state(native).needs_input is False
