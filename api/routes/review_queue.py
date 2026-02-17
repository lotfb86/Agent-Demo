from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.services.database import connect_db

router = APIRouter(prefix="/api/review-queue", tags=["review-queue"])


class ReviewActionRequest(BaseModel):
    action: str


@router.post("/{item_id}/action")
async def review_action(item_id: int, body: ReviewActionRequest) -> dict[str, str]:
    action = body.action.lower().strip()
    if action not in {"approve", "reject", "escalate"}:
        raise HTTPException(status_code=400, detail="action must be one of approve/reject/escalate")

    conn = await connect_db()
    try:
        cursor = await conn.execute(
            "SELECT id, status FROM review_queue WHERE id = ?",
            (item_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Review item not found")

        await conn.execute(
            """
            UPDATE review_queue
            SET status = 'closed', action = ?, actioned_at = ?
            WHERE id = ?
            """,
            (action, datetime.utcnow().isoformat() + "Z", item_id),
        )
        await conn.commit()
        return {"status": "ok", "action": action}
    finally:
        await conn.close()
