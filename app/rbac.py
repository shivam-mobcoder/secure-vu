from aiohttp import web
from functools import wraps
from db import db_get_camera, db_user_camera_exists

ROLE_ALIASES = {
    "admin": "admin",
    "customer_admin": "admin",
    "operator": "member",
    "viewer": "member",
    "member": "member",
    "superadmin": "super_admin",
    "super_admin": "super_admin",
    "super-admin": "super_admin",
    "super admin": "super_admin",
}


def _normalize_role(role) -> str:
    raw = str(role or "").strip().lower()
    raw = raw.replace("-", "_").replace(" ", "_")
    return ROLE_ALIASES.get(raw, raw)

ROLE_PERMISSIONS = {
    "super_admin": {
        "clients": {"view"},
    },
    "admin": {
        "cameras": {"view", "manage"},
        "rules": {"view", "manage"},
        "users": {"manage"},
        "faces": {"view", "enroll", "delete"},
        "webrtc": {"connect"},
        "alerts": {"view"},
    },
    "member": {
        "cameras": {"view"},
        "rules": {"view"},
        "faces": {"view"},
        "webrtc": {"connect"},
        "alerts": {"view"},
    },
}


def can(user, resource: str, action: str) -> bool:
    if not user:
        return False
    role = user.get("role")
    if not role:
        return False
    role = _normalize_role(role)
    perms = ROLE_PERMISSIONS.get(role, {})
    if "*" in perms:
        allowed = perms.get("*")
        if allowed and ("*" in allowed or action in allowed):
            return True
    allowed = perms.get(resource)
    if not allowed:
        return False
    return "*" in allowed or action in allowed

def require_admin(handler):
    @wraps(handler)
    async def wrapper(request):
        role = _normalize_role(request["user"].get("role"))
        if role not in ("admin", "super_admin"):
            return web.Response(status=403)
        return await handler(request)
    return wrapper

async def user_can_access_camera(user, camera_id):
    role = _normalize_role(user.get("role"))
    if role == "super_admin":
        return False

    cam = await db_get_camera(camera_id)
    if not cam:
        return False
    if cam.get("client_id") != user.get("client_id"):
        return False

    if role == "admin":
        return True

    return await db_user_camera_exists(user.get("user_id"), camera_id)
