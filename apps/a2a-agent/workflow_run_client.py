"""
Async client for the LiteLLM Workflow Runs API.

Reads AELLI_LITELLM_BASE and AELLI_AUTH_TOKEN from env — the same credentials
used by bridge.py to reach the LiteLLM proxy.

All public methods are best-effort: HTTP or network failures are logged and
swallowed so a tracking outage never interrupts a dispatch.
"""
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

_WORKFLOW_TYPE = "octowiz.dispatch"
_TIMEOUT = 10.0


def _make_from_env() -> Optional["WorkflowRunClient"]:
    """Return a client if AELLI_LITELLM_BASE and AELLI_AUTH_TOKEN are set, else None."""
    base = os.environ.get("AELLI_LITELLM_BASE", "").rstrip("/")
    token = os.environ.get("AELLI_AUTH_TOKEN", "")
    if not base or not token:
        return None
    return WorkflowRunClient(base, token)


class WorkflowRunClient:
    """Async client for /v1/workflows/runs. Failures are logged, not raised."""

    def __init__(self, base_url: str, api_key: str, timeout: float = _TIMEOUT):
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )

    async def create_run(
        self,
        *,
        task: str,
        cwd: str,
        principal: str,
    ) -> Optional[Dict[str, Any]]:
        """Create a new workflow run. Returns the run dict (includes run_id and
        session_id) on success, None on failure.

        run_id   — used for subsequent event/patch calls.
        session_id — LiteLLM-generated UUID; pass as x-litellm-session-id on
                     completions to tag spend logs to this run.
        """
        try:
            resp = await self._client.post(
                "/v1/workflows/runs",
                json={
                    "workflow_type": _WORKFLOW_TYPE,
                    "metadata": {
                        "task": task,
                        "cwd": cwd,
                        "principal": principal,
                    },
                },
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning("[octowiz] workflow_runs: create_run failed: %s", exc)
            return None

    async def transition(
        self,
        run_id: str,
        event_type: str,
        step_name: str,
        *,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Append an event to the run's event log.

        Automatically updates run.status based on event_type:
            step.started  → running
            step.failed   → failed
            hook.waiting  → paused
            hook.received → running
        """
        try:
            payload: Dict[str, Any] = {
                "event_type": event_type,
                "step_name": step_name,
            }
            if data:
                payload["data"] = data
            resp = await self._client.post(
                f"/v1/workflows/runs/{run_id}/events",
                json=payload,
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.warning(
                "[octowiz] workflow_runs: transition(%s, %s, %s) failed: %s",
                run_id,
                event_type,
                step_name,
                exc,
            )

    async def complete(self, run_id: str, *, output: Dict[str, Any]) -> None:
        """Mark the run as completed with the given output."""
        await self._patch(run_id, {"status": "completed", "output": output})

    async def fail(self, run_id: str, *, output: Dict[str, Any]) -> None:
        """Mark the run as failed with the given output."""
        await self._patch(run_id, {"status": "failed", "output": output})

    async def list_active_runs(
        self, workflow_type: str = _WORKFLOW_TYPE
    ) -> List[Dict[str, Any]]:
        """Return running/paused runs. Used for startup crash-recovery.

        Each returned run has a 'events' field with the last event; the last
        step.started event's data.claude_session_id is the --resume handle.
        Returns [] on failure.
        """
        try:
            resp = await self._client.get(
                "/v1/workflows/runs",
                params={
                    "workflow_type": workflow_type,
                    "status": "running,paused",
                },
            )
            resp.raise_for_status()
            return resp.json().get("runs", [])
        except Exception as exc:
            logger.warning(
                "[octowiz] workflow_runs: list_active_runs failed: %s", exc
            )
            return []

    async def _patch(self, run_id: str, update: Dict[str, Any]) -> None:
        try:
            resp = await self._client.patch(
                f"/v1/workflows/runs/{run_id}",
                json=update,
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.warning(
                "[octowiz] workflow_runs: patch(%s) failed: %s", run_id, exc
            )

    async def close(self) -> None:
        await self._client.aclose()
