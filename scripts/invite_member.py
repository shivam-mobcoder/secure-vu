import os
import asyncio
import asyncpg
import bcrypt
from dotenv import load_dotenv

load_dotenv()

DB_USER = os.getenv("DB_USER", "cctv_user")
DB_PASS = os.getenv("DB_PASS", "StrongPassword123")
DB_NAME = os.getenv("DB_NAME", "cctv_platform")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "5432"))

EMAIL = os.getenv("INVITE_EMAIL", "newmember@local")
PASSWORD = os.getenv("INVITE_PASSWORD", "Welcome@123")
ROLE = os.getenv("INVITE_ROLE", "member")   # member | admin
CLIENT = os.getenv("INVITE_CLIENT", "Default Client")


async def main():
    conn = await asyncpg.connect(
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        host=DB_HOST,
        port=DB_PORT,
    )
    try:
        role = ROLE.strip().lower().replace("-", "_")
        if role == "customer_admin":
            role = "admin"

        client = await conn.fetchrow("SELECT id FROM clients WHERE name=$1", CLIENT)
        if not client:
            print("Client not found")
            return

        exists = await conn.fetchrow("SELECT id FROM users WHERE email=$1", EMAIL)
        if exists:
            print("User already exists")
            return

        pw = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode()

        await conn.execute(
            "INSERT INTO users(email,password_hash,role,client_id) VALUES($1,$2,$3,$4)",
            EMAIL,
            pw,
            role,
            client["id"],
        )

        print("Invited:", EMAIL, "role=", role)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
