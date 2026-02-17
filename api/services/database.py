from __future__ import annotations

import aiosqlite

from api.services.config import get_settings


async def connect_db() -> aiosqlite.Connection:
    settings = get_settings()
    conn = await aiosqlite.connect(settings.resolved_database_path)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys = ON;")
    return conn
