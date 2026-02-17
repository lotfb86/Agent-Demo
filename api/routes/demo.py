from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException

from api.services.session_manager import session_manager

router = APIRouter(prefix="/api/demo", tags=["demo"])


@router.post("/reset")
async def reset_demo() -> dict[str, str]:
    script = Path(__file__).resolve().parents[2] / "scripts" / "reset_demo.py"
    if not script.exists():
        raise HTTPException(status_code=500, detail="Reset script not found")

    proc = await asyncio.create_subprocess_exec(
        "python3",
        str(script),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise HTTPException(status_code=500, detail=stderr.decode().strip() or "Reset failed")

    # Clear in-memory session state so stale latest_output doesn't persist
    await session_manager.clear_all()

    return {
        "status": "ok",
        "message": stdout.decode().strip().splitlines()[-1] if stdout else "Reset complete",
    }
