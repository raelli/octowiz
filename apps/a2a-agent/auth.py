import hmac
import os
from fastapi import Request
from fastapi.responses import JSONResponse

# Agent card discovery endpoints are always public.
_EXEMPT_PATH_FRAGMENT = "/.well-known/"


async def auth_middleware(request: Request, call_next):
    if _EXEMPT_PATH_FRAGMENT in request.url.path:
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
