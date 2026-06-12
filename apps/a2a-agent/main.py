import hashlib
import json
import os
import pathlib

from fastapi import FastAPI, Request
from fastapi.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware

from a2a import make_response, parse_event
from auth import auth_middleware
from card import AGENT_CARD
from dispatch import dispatch

app = FastAPI(title="Octowiz A2A Agent")
app.add_middleware(BaseHTTPMiddleware, dispatch=auth_middleware)


def _read_plugin_version() -> str:
    here = pathlib.Path(__file__).resolve().parent
    for candidate in [here, *here.parents]:
        p = candidate / ".claude-plugin" / "plugin.json"
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8")).get("version", "unknown")
            except Exception:
                break
    return "unknown"


_PLUGIN_VERSION = _read_plugin_version()


@app.get("/health")
async def health():
    return {"status": "ok", "version": _PLUGIN_VERSION}


@app.get("/a2a/octowiz/.well-known/agent.json")
@app.get("/a2a/octowiz/.well-known/agent-card.json")
async def agent_card():
    return AGENT_CARD


def _principal_from(request: Request) -> str:
    """Derive a stable principal identifier from the authenticated request.

    Uses a short hash of the secret header so the raw secret is never stored
    in session ownership records. In v1 (single secret) all callers map to the
    same principal — ownership checks still provide correct infrastructure for
    future multi-caller deployments.
    """
    inbound = request.headers.get("x-octowiz-secret", "")
    if not inbound:
        return "anonymous"
    return hashlib.sha256(inbound.encode()).hexdigest()[:16]


async def _handle(request: Request):
    body = await request.json()
    req_id = body.get("id")
    event = parse_event(body)
    if event is None:
        return make_response(req_id, {})
    # Principal is always derived from the authenticated secret, never from a
    # client-supplied header.  In v1 (single shared secret) all callers —
    # daemon and bridge.py alike — map to the same principal, so there is no
    # need for caller-supplied identity.  A client-supplied field would allow
    # any holder of the shared secret to spoof session ownership.
    event["_principal"] = _principal_from(request)
    artifact = await dispatch(event)
    return make_response(req_id, artifact, session_id=event.get("sessionId"))


@app.post("/a2a/octowiz")
async def octowiz_handler(request: Request):
    return await _handle(request)


@app.post("/a2a/dev-advisor")
async def dev_advisor_alias(request: Request):
    return await _handle(request)
