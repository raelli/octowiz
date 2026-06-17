import hmac
import os
from fastapi import Request
from fastapi.responses import JSONResponse

_PUBLIC_PATHS = {
    "/health",
    "/a2a/octowiz/.well-known/agent.json",
    "/a2a/octowiz/.well-known/agent-card.json",
}


async def auth_middleware(request: Request, call_next):
    if request.url.path in _PUBLIC_PATHS:
        return await call_next(request)

    # Trim surrounding whitespace to mirror the daemon's config.env() reader
    # (src/config.js), which sends the .trim()'d secret in x-octowiz-secret.
    # Without this, a secret configured with accidental leading/trailing
    # whitespace would 401 every forwarded capability.
    secret = (os.environ.get("OCTOWIZ_INBOUND_SECRET") or "").strip()
    if not secret:
        # P1: generic body — do not disclose env var name to the caller.
        return JSONResponse(
            status_code=401,
            content={"error": "Unauthorized"},
        )

    inbound = request.headers.get("x-octowiz-secret", "")
    try:
        # P1: rely solely on hmac.compare_digest; removed len() pre-check that
        # leaked the secret length.
        ok = hmac.compare_digest(inbound.encode(), secret.encode())
    except Exception:
        ok = False

    if not ok:
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    return await call_next(request)
