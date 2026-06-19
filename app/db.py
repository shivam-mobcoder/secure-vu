import json
import os
import asyncpg

_pool: asyncpg.Pool | None = None


def set_pool(pool: asyncpg.Pool) -> None:
    global _pool
    _pool = pool


def _require_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool not initialized")
    return _pool


async def db_execute(q, args=()):
    pool = _require_pool()
    async with pool.acquire() as conn:
        await conn.execute(q, *args)


async def db_fetch(q, args=()):
    pool = _require_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(q, *args)
        return [dict(r) for r in rows]


async def db_fetchrow(q, args=()):
    pool = _require_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(q, *args)
        return dict(row) if row else None


async def db_get_user_by_email(email):
    row = await db_fetchrow("SELECT * FROM users WHERE email=$1", (email,))
    return dict(row) if row else None


async def db_get_user_by_id(uid):
    row = await db_fetchrow("SELECT * FROM users WHERE id=$1", (uid,))
    return dict(row) if row else None


async def db_get_camera(cid):
    row = await db_fetchrow("SELECT * FROM cameras WHERE id=$1", (cid,))
    return dict(row) if row else None


async def db_user_camera_exists(uid, cid):
    row = await db_fetchrow(
        "SELECT 1 FROM user_cameras WHERE user_id=$1 AND camera_id=$2",
        (uid, cid),
    )
    return row is not None


async def db_list_users_by_client(client_id):
    pool = _require_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, email, role, is_active, permissions FROM users WHERE client_id=$1",
            client_id,
        )
        return [dict(r) for r in rows]


async def db_update_user_permissions(user_id, permissions):
    await db_execute(
        "UPDATE users SET permissions=$1 WHERE id=$2",
        (json.dumps(permissions), user_id),
    )


async def db_insert_alert(
    client_id,
    camera_id,
    person,
    event,
    priority=None,
    clip_url=None,
    meta=None,
):
    meta_json = json.dumps(meta) if meta is not None else None
    await db_execute(
        """
        INSERT INTO alerts (client_id, camera_id, person, event, priority, clip_url, meta)
        VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
        """,
        (client_id, camera_id, person, event, priority, clip_url, meta_json),
    )


async def db_list_alerts(client_id=None, camera_id=None, limit=50):
    limit = max(1, min(int(limit), 200))
    args = []
    clauses = []
    if client_id is not None:
        args.append(int(client_id))
        clauses.append(f"client_id = ${len(args)}")
    if camera_id is not None:
        args.append(int(camera_id))
        clauses.append(f"camera_id = ${len(args)}")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    args.append(limit)
    q = f"""
        SELECT id, client_id, camera_id, person, event, priority, clip_url, meta, created_at
        FROM alerts
        {where}
        ORDER BY created_at DESC
        LIMIT ${len(args)}
    """
    rows = await db_fetch(q, tuple(args))
    for row in rows:
        if row.get("created_at"):
            row["created_at"] = row["created_at"].isoformat()
        if row.get("timestamp") is None and row.get("created_at"):
            row["timestamp"] = row["created_at"]
    return rows


async def db_insert_recording_segment(camera_id, path, start_ts, end_ts, size_bytes):
    await db_execute(
        """
        INSERT INTO recording_segments (camera_id, path, start_ts, end_ts, size_bytes)
        VALUES ($1, $2, to_timestamp($3), to_timestamp($4), $5)
        """,
        (int(camera_id), str(path), float(start_ts), float(end_ts), int(size_bytes or 0)),
    )


async def db_list_recording_segments(camera_id=None, limit=50):
    limit = max(1, min(int(limit), 200))
    if camera_id is not None:
        rows = await db_fetch(
            """
            SELECT id, camera_id, path, start_ts, end_ts, size_bytes
            FROM recording_segments
            WHERE camera_id = $1
            ORDER BY start_ts DESC
            LIMIT $2
            """,
            (int(camera_id), limit),
        )
    else:
        rows = await db_fetch(
            """
            SELECT id, camera_id, path, start_ts, end_ts, size_bytes
            FROM recording_segments
            ORDER BY start_ts DESC
            LIMIT $1
            """,
            (limit,),
        )
    for row in rows:
        for key in ("start_ts", "end_ts"):
            if row.get(key):
                row[key] = row[key].isoformat()
    return rows


async def db_list_cameras_for_client(client_id):
    return await db_fetch(
        "SELECT id, name, rtsp_url, is_active FROM cameras WHERE client_id = $1 ORDER BY id",
        (int(client_id),),
    )
