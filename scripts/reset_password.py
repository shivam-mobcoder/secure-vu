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

EMAIL = os.getenv("RESET_EMAIL", "member@local")
NEW_PASSWORD = os.getenv("NEW_PASSWORD", "NewPass@123")


async def main():
    conn = await asyncpg.connect(
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        host=DB_HOST,
    )
    try:
        user = await conn.fetchrow("SELECT id FROM users WHERE email=$1", EMAIL)
        if not user:
            print("User not found")
            return

        pw = bcrypt.hashpw(NEW_PASSWORD.encode(), bcrypt.gensalt()).decode()

        await conn.execute(
            "UPDATE users SET password_hash=$1 WHERE id=$2",
            pw,
            user["id"],
        )

        print("Password reset for:", EMAIL)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
