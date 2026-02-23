import jwt
import time
from aiohttp import web
from auth import JWT_SECRET, JWT_ALGO

try:
    from db import db_get_user_by_id  # type: ignore
except Exception:
    db_get_user_by_id = None

PUBLIC_PATHS = (
    "/login",
    "/signup",
    "/",
    "/client.html",
    "/favicon.ico",
)


PUBLIC_PREFIXES = (
    "/static/",
    "/docs/",
    "/super-admin/dashboard",
    "/event-clips/",
)


# Require re-login after server restart
SERVER_START_TS = int(time.time())


@web.middleware
async def auth_middleware(request, handler):
    if request.method == "OPTIONS":
        return web.Response(status=204)

    if request.path in PUBLIC_PATHS or any(
        request.path.startswith(p) for p in PUBLIC_PREFIXES
    ):
        return await handler(request)

    # Allow public access to enrollment links, but keep /enroll/create protected.
    if request.path.startswith("/enroll/") and request.path != "/enroll/create":
        return await handler(request)

    token = ""
    hdr = request.headers.get("Authorization")
    if hdr:
        token = hdr.strip()
        if token.lower().startswith("bearer "):
            token = token[7:].strip()
    if not token:
        token = (request.query.get("token") or "").strip()
    if not token:
        return web.Response(status=401)

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except Exception:
        return web.Response(status=401)

    try:
        issued_at = int(payload.get("iat", 0))
    except Exception:
        issued_at = 0
    if issued_at < SERVER_START_TS:
        return web.Response(status=401)

    if db_get_user_by_id and (
        not payload.get("role") or payload.get("client_id") is None
    ):
        try:
            user = await db_get_user_by_id(payload.get("user_id"))
            if user:
                payload["role"] = user.get("role")
                payload["client_id"] = user.get("client_id")
        except Exception:
            pass

    request["user"] = payload
    return await handler(request)
