from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from api.services.database import connect_db

router = APIRouter(prefix="/api/communications", tags=["communications"])


@router.get("")
async def list_communications(limit: int = 200) -> list[dict[str, Any]]:
    conn = await connect_db()
    try:
        cursor = await conn.execute(
            """
            SELECT id, agent_id, recipient, subject, body, channel, created_at
            FROM communications
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await conn.close()
