import hmac
import os
import sys
from fastapi import Request
from fastapi.responses import JSONResponse


def _warn_once():
    print("[octowiz] WARNING: OCTOWIZ_INBOUND_SECRET not set — inbound auth disabled", file=sys.stderr)


_warned = False


async def auth_middleware(request: Request, call_next):
    global _warned
    secret = os.environ.get("OCTOWIZ_INBOUND_SECRET")
    if not secret:
        if not _warned:
            _warn_once()
            _warned = True
        return await call_next(request)

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
