#!/usr/bin/env python3
"""Register RTSP cameras in Postgres for the demo client (health API + RBAC)."""

import asyncio
import os

import asyncpg
from dotenv import load_dotenv

load_dotenv()

DB_USER = os.getenv("DB_USER", "cctv_user")
DB_PASS = os.getenv("DB_PASS", "StrongPassword123")
DB_NAME = os.getenv("DB_NAME", "cctv_platform")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
CLIENT_NAME = os.getenv("ADMIN_CUSTOMER", "SecureVU_Demo")


async def main():
    conn = await asyncpg.connect(
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        host=DB_HOST,
        port=DB_PORT,
    )
    try:
        client = await conn.fetchrow(
            "SELECT id FROM clients WHERE name=$1", CLIENT_NAME
        )
        if not client:
            print(f"Client not found: {CLIENT_NAME!r} — run scripts/seed_admin.py first")
            return
        client_id = client["id"]

        for cam_id in range(1, 5):
            url = os.getenv(f"RTSP_URL_{cam_id}", "").strip()
            name = f"Camera {cam_id}"
            existing = await conn.fetchrow(
                "SELECT id FROM cameras WHERE client_id=$1 AND name=$2",
                client_id,
                name,
            )
            if existing:
                await conn.execute(
                    "UPDATE cameras SET rtsp_url=$1, is_active=TRUE WHERE id=$2",
                    url or f"rtsp://placeholder/cam{cam_id}",
                    existing["id"],
                )
                print("Updated:", name, "id=", existing["id"])
            else:
                row = await conn.fetchrow(
                    """
                    INSERT INTO cameras(client_id, name, rtsp_url, is_active)
                    VALUES ($1, $2, $3, TRUE)
                    RETURNING id
                    """,
                    client_id,
                    name,
                    url or f"rtsp://placeholder/cam{cam_id}",
                )
                print("Created:", name, "id=", row["id"])

        print("Camera seeding complete.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
