from aiohttp import web

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


def require_role(user, allowed_roles):
    role = _normalize_role((user or {}).get("role"))
    allowed = {_normalize_role(r) for r in (allowed_roles or [])}
    if role not in allowed:
        raise web.HTTPForbidden(text="Forbidden")