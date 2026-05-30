import hmac
import os
from fastapi import Request
from fastapi.responses import JSONResponse

_WELL_KNOWN_SUFFIX = "/.well-known/"


async def auth_middleware(request: Request, call_next):
    if _WELL_KNOWN_SUFFIX in request.url.path:
        return await call_next(request)

    secret = os.environ.get("OCTOWIZ_INBOUND_SECRET")
    if not secret:
        return JSONResponse(status_code=401, content={"error": "OCTOWIZ_INBOUND_SECRET not configured"})

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
