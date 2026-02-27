import jwt
import time
from aiohttp import web
from auth import JWT_SECRET, JWT_ALGO

try:
    from db import db_get_user_by_id  # type: ignore
except Exception:
    db_get_user_by_id = None

import logging
logger = logging.getLogger("middleware")

PUBLIC_PATHS = (
    "/login",
    "/signup",
    "/",
    "/home",
    "/auth",
    "/client.html",
    "/favicon.ico",
)


PUBLIC_PREFIXES = (
    "/static/",
    "/assets/",
    "/docs/",
    "/super-admin/dashboard",
    "/admin/dashboard",
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

    # Always fetch latest user info from DB to get dynamic permissions
    if db_get_user_by_id:
        try:
            live_user = await db_get_user_by_id(payload.get("user_id"))
            if live_user:
                # Merge DB data into the request user object
                payload["role"] = live_user.get("role")
                payload["client_id"] = live_user.get("client_id")
                payload["permissions"] = live_user.get("permissions") or []
            else:
                return web.Response(status=401)
        except Exception as e:
            logger.error(f"Middleware DB user fetch error: {e}")

    request["user"] = payload
    return await handler(request)
