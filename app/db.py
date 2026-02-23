import os
import asyncpg

_pool: asyncpg.Pool | None = None


def set_pool(pool: asyncpg.Pool) -> None:
    global _pool
    _pool = pool


async def init_pool() -> asyncpg.Pool:
    pool = await asyncpg.create_pool(
        user=os.getenv("DB_USER", "cctv_user"),
        password=os.getenv("DB_PASS", "StrongPassword123"),
        database=os.getenv("DB_NAME", "cctv_platform"),
        host=os.getenv("DB_HOST", "127.0.0.1"),
        min_size=int(os.getenv("DB_POOL_MIN", "5")),
        max_size=int(os.getenv("DB_POOL_MAX", "20")),
    )
    set_pool(pool)
    return pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def _require_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool not initialized")
    return _pool


async def db_execute(q, args=()):
    pool = _require_pool()
    async with pool.acquire() as conn:
        await conn.execute(q, *args)


async def db_fetchrow(q, args=()):
    pool = _require_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(q, *args)


async def db_fetch(q, args=()):
    pool = _require_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(q, *args)


async def db_get_user_by_email(email):
    row = await db_fetchrow("SELECT * FROM users WHERE email=$1", (email,))
    return dict(row) if row else None


async def db_get_user_by_id(uid):
    row = await db_fetchrow("SELECT * FROM users WHERE id=$1", (uid,))
    return dict(row) if row else None


async def db_get_camera(cid):
    row = await db_fetchrow("SELECT * FROM cameras WHERE id=$1", (cid,))
    return dict(row) if row else None


async def db_get_camera_for_client(cid, client_id):
    row = await db_fetchrow(
        "SELECT * FROM cameras WHERE id=$1 AND client_id=$2",
        (cid, client_id),
    )
    return dict(row) if row else None


async def db_user_camera_exists(uid, cid):
    row = await db_fetchrow(
        "SELECT 1 FROM user_cameras WHERE user_id=$1 AND camera_id=$2",
        (uid, cid),
    )
    return row is not None
