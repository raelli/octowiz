import hashlib
import os

from fastapi import FastAPI, Request
from fastapi.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware

from a2a import make_response, parse_event
from auth import auth_middleware
from card import AGENT_CARD
from dispatch import dispatch

app = FastAPI(title="Octowiz A2A Agent")
app.add_middleware(BaseHTTPMiddleware, dispatch=auth_middleware)


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
    # When the Node.js daemon forwards a queue task it passes the pre-resolved
    # principal in x-octowiz-principal (the daemon has the principal from the
    # queue task record).  Direct callers such as bridge.py send no such header
    # and continue to derive the principal from the shared secret via
    # _principal_from().  This is additive: authentication is still enforced by
    # auth_middleware regardless of which path sets the principal.
    explicit_principal = request.headers.get("x-octowiz-principal", "")
    event["_principal"] = explicit_principal if explicit_principal else _principal_from(request)
    artifact = await dispatch(event)
    return make_response(req_id, artifact, session_id=event.get("sessionId"))


@app.post("/a2a/octowiz")
async def octowiz_handler(request: Request):
    return await _handle(request)


@app.post("/a2a/dev-advisor")
async def dev_advisor_alias(request: Request):
    return await _handle(request)
