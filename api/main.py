from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routes.agents import router as agents_router
from api.routes.communications import router as communications_router
from api.routes.demo import router as demo_router
from api.routes.review_queue import router as review_router
from api.services.config import get_settings
from api.services.llm import llm_enabled
from api.services.session_manager import session_manager

settings = get_settings()
app = FastAPI(title="RPMX Orchestration API", version="0.1.0")
base_dir = Path(__file__).resolve().parents[1]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agents_router)
app.include_router(review_router)
app.include_router(communications_router)
app.include_router(demo_router)
app.mount("/assets", StaticFiles(directory=base_dir), name="assets")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "real_llm_enabled": "true" if llm_enabled() else "false",
    }


@app.websocket("/ws/agent/{session_id}")
async def ws_agent_session(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    sent_index = 0

    try:
        while True:
            state = await session_manager.get(session_id)
            if state is None:
                await websocket.send_json(
                    {
                        "type": "error",
                        "payload": {"message": "Unknown session"},
                        "session_id": session_id,
                    }
                )
                break

            while sent_index < len(state.events):
                await websocket.send_json(state.events[sent_index])
                sent_index += 1

            if state.done and sent_index >= len(state.events):
                break

            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        return
    finally:
        try:
            await websocket.close()
        except RuntimeError:
            pass
