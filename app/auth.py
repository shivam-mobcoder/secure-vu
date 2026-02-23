import os
import time
import bcrypt
import jwt
from aiohttp import web
from db import db_execute, db_get_user_by_email

JWT_SECRET = os.getenv("JWT_SECRET", "CHANGE_ME")
JWT_ALGO = os.getenv("JWT_ALGO", "HS256")
ALLOWED_SIGNUP_ROLES = {"super_admin", "admin", "member"}


def _normalize_role(role) -> str:
    raw = str(role or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "superadmin": "super_admin",
        "super_admin": "super_admin",
        "admin": "admin",
        "member": "member",
    }
    return aliases.get(raw, raw)


def _issue_token(user: dict) -> str:
    now = int(time.time())
    payload = {
        "user_id": user["id"],
        "role": user["role"],
        "client_id": user.get("client_id"),
        "iat": now,
        "exp": now + 86400,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

async def create_user(email, password, role, client_id):
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    await db_execute(
        """
        INSERT INTO users(email,password_hash,role,client_id)
        VALUES($1,$2,$3,$4)
        """,
        (email, pw_hash, role, client_id),
    )

async def login(request):
    try:
        data = await request.json()
    except Exception:
        return web.Response(status=400)

    email = (data or {}).get("email")
    password = (data or {}).get("password")
    if not email or not password:
        return web.Response(status=400)

    user = await db_get_user_by_email(email)
    if not user:
        return web.Response(status=401)

    if not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
        return web.Response(status=401)

    token = _issue_token(user)
    return web.json_response({"token": token, "token_type": "Bearer", "expires_in": 86400})


async def signup(request):
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "invalid_json"}, status=400)

    email = str((data or {}).get("email") or "").strip().lower()
    password = (data or {}).get("password") or ""
    role = _normalize_role((data or {}).get("role"))
    client_id = (data or {}).get("client_id")

    if not email or not password or not role:
        return web.json_response({"error": "email_password_role_required"}, status=400)
    if len(password) < 8:
        return web.json_response({"error": "password_too_short"}, status=400)
    if role not in ALLOWED_SIGNUP_ROLES:
        return web.json_response({"error": "invalid_role"}, status=400)

    existing = await db_get_user_by_email(email)
    if existing:
        return web.json_response({"error": "email_already_exists"}, status=409)

    try:
        parsed_client_id = int(client_id) if client_id not in (None, "") else None
    except Exception:
        return web.json_response({"error": "invalid_client_id"}, status=400)

    await create_user(email=email, password=password, role=role, client_id=parsed_client_id)
    user = await db_get_user_by_email(email)
    if not user:
        return web.json_response({"error": "user_create_failed"}, status=500)

    token = _issue_token(user)
    return web.json_response({
        "token": token,
        "token_type": "Bearer",
        "expires_in": 86400,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "role": user["role"],
            "client_id": user.get("client_id"),
        },
    })
