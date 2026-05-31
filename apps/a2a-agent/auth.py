import hmac
import os
from fastapi import Request
from fastapi.responses import JSONResponse

_PUBLIC_PATHS = {
    "/a2a/octowiz/.well-known/agent.json",
    "/a2a/octowiz/.well-known/agent-card.json",
}


async def auth_middleware(request: Request, call_next):
    if request.url.path in _PUBLIC_PATHS:
        return await call_next(request)

    secret = os.environ.get("OCTOWIZ_INBOUND_SECRET")
    if not secret:
        return JSONResponse(
            status_code=401,
            content={"error": "OCTOWIZ_INBOUND_SECRET not configured"},
        )

    inbound = request.headers.get("x-octowiz-secret", "")
    try:
        ok = (
            len(inbound) == len(secret)
            and hmac.compare_digest(inbound.encode(), secret.encode())
        )
    except Exception:
        ok = False

    if not ok:
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    return await call_next(request)
