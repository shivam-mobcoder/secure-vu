import os
import asyncio
import asyncpg
from dotenv import load_dotenv

load_dotenv()

DB_USER = os.getenv("DB_USER", "cctv_user")
DB_PASS = os.getenv("DB_PASS", "StrongPassword123")
DB_NAME = os.getenv("DB_NAME", "cctv_platform")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")

USER_EMAIL = os.getenv("USER_EMAIL", "member@local")
CAMERA_ID = int(os.getenv("CAMERA_ID", "1"))


async def main():
    conn = await asyncpg.connect(
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        host=DB_HOST,
    )
    try:
        user = await conn.fetchrow("SELECT id FROM users WHERE email=$1", USER_EMAIL)
        if not user:
            print("User not found")
            return

        cam = await conn.fetchrow("SELECT id FROM cameras WHERE id=$1", CAMERA_ID)
        if not cam:
            print("Camera not found")
            return

        await conn.execute(
            """
            INSERT INTO user_cameras(user_id,camera_id)
            SELECT $1, $2
            WHERE NOT EXISTS (
                SELECT 1 FROM user_cameras WHERE user_id=$1 AND camera_id=$2
            )
            """,
            user["id"],
            CAMERA_ID,
        )
        print("Assigned", USER_EMAIL, "to camera", CAMERA_ID)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
