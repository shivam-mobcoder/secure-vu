from aiohttp import web


def _normalize_role(role) -> str:
    raw = str(role or "").strip().lower()
    return raw.replace("-", "_").replace(" ", "_")


def require_role(user, allowed_roles):
    role = _normalize_role((user or {}).get("role"))
    allowed = {_normalize_role(r) for r in (allowed_roles or [])}
    if role not in allowed:
        raise web.HTTPForbidden(text="Forbidden")
