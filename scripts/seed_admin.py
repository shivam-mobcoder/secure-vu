import os
import asyncio
import bcrypt
import asyncpg
from dotenv import load_dotenv
from pathlib import Path
from datetime import date, timedelta

BASE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH)

DB_USER = os.getenv("DB_USER", "cctv_user")
DB_PASS = os.getenv("DB_PASS", "StrongPassword123")
DB_NAME = os.getenv("DB_NAME", "cctv_platform")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")

SUPER_EMAIL = os.getenv("SUPER_EMAIL")
SUPER_PASSWORD = os.getenv("SUPER_PASSWORD")

CLIENT_NAME = os.getenv("ADMIN_CUSTOMER")
CLIENT_EMAIL = os.getenv("CLIENT_EMAIL", "client@example.com")
CLIENT_TYPE = os.getenv("CLIENT_TYPE", "business")
CLIENT_PLAN = os.getenv("CLIENT_PLAN", "standard")
CLIENT_BILLING = os.getenv("CLIENT_BILLING", "monthly")

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

MEMBER_EMAIL = os.getenv("MEMBER_EMAIL")
MEMBER_PASSWORD = os.getenv("MEMBER_PASSWORD")

required = {
    "SUPER_EMAIL": SUPER_EMAIL,
    "SUPER_PASSWORD": SUPER_PASSWORD,
    "ADMIN_CUSTOMER": CLIENT_NAME,
    "ADMIN_EMAIL": ADMIN_EMAIL,
    "ADMIN_PASSWORD": ADMIN_PASSWORD,
    "MEMBER_EMAIL": MEMBER_EMAIL,
    "MEMBER_PASSWORD": MEMBER_PASSWORD,
}

missing = [k for k, v in required.items() if not v]
if missing:
    raise RuntimeError(f"Missing env vars: {', '.join(missing)}")


async def ensure_user(conn, email, password, role, client_id):
    row = await conn.fetchrow("SELECT id FROM users WHERE email=$1", email)
    if row:
        print("User exists:", email)
        return row["id"]

    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    await conn.execute(
        "INSERT INTO users(email,password_hash,role,client_id) VALUES($1,$2,$3,$4)",
        email,
        pw_hash,
        role,
        client_id,
    )
    uid = (await conn.fetchrow("SELECT id FROM users WHERE email=$1", email))["id"]
    print("Created:", email, "role=", role)
    return uid


async def main():
    conn = await asyncpg.connect(
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        host=DB_HOST,
    )

    try:
        row = await conn.fetchrow("SELECT id FROM clients WHERE name=$1", CLIENT_NAME)
        if row:
            client_id = row["id"]
        else:
            client_pw = bcrypt.hashpw(ADMIN_PASSWORD.encode(), bcrypt.gensalt()).decode()
            next_billing = date.today() + timedelta(days=30)
            row = await conn.fetchrow(
                """
                INSERT INTO clients(
                    name, email, phone, customer_type, subscription_plan,
                    billing_cycle, next_billing_date, password_hash, is_active
                )
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,TRUE)
                RETURNING id
                """,
                CLIENT_NAME,
                CLIENT_EMAIL,
                os.getenv("CLIENT_PHONE"),
                CLIENT_TYPE,
                CLIENT_PLAN,
                CLIENT_BILLING,
                next_billing,
                client_pw,
            )
            client_id = row["id"]
            print("Created client:", CLIENT_NAME)

        await ensure_user(conn, SUPER_EMAIL, SUPER_PASSWORD, "super_admin", None)
        admin_id = await ensure_user(conn, ADMIN_EMAIL, ADMIN_PASSWORD, "admin", client_id)
        member_id = await ensure_user(conn, MEMBER_EMAIL, MEMBER_PASSWORD, "member", client_id)

        try:
            cam = await conn.fetchrow("SELECT id FROM cameras WHERE client_id=$1 LIMIT 1", client_id)
            if cam:
                await conn.execute(
                    """
                    INSERT INTO user_cameras(user_id,camera_id)
                    SELECT $1, $2
                    WHERE NOT EXISTS (
                        SELECT 1 FROM user_cameras WHERE user_id=$1 AND camera_id=$2
                    )
                    """,
                    member_id,
                    cam["id"],
                )
                print("Assigned member to camera", cam["id"])
        except Exception:
            pass

        print("Seeding complete.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
