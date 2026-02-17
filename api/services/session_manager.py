from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4


@dataclass
class SessionState:
    session_id: str
    agent_id: str
    created_at: str
    events: list[dict[str, Any]] = field(default_factory=list)
    done: bool = False
    latest_output: Any = None


@dataclass
class ConversationContext:
    conversation_id: str
    agent_id: str
    messages: list[dict[str, str]] = field(default_factory=list)
    reports: list[dict[str, Any]] = field(default_factory=list)

    MAX_MESSAGES = 10

    def append_message(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})
        if len(self.messages) > self.MAX_MESSAGES:
            self.messages = self.messages[-self.MAX_MESSAGES:]

    def append_report(self, report: dict[str, Any]) -> None:
        self.reports.append(report)


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}
        self._conversations: dict[str, ConversationContext] = {}
        self._lock = asyncio.Lock()

    async def create(self, agent_id: str) -> SessionState:
        async with self._lock:
            session_id = str(uuid4())
            state = SessionState(
                session_id=session_id,
                agent_id=agent_id,
                created_at=datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            )
            self._sessions[session_id] = state
            return state

    async def append_event(self, session_id: str, event: dict[str, Any]) -> None:
        async with self._lock:
            state = self._sessions.get(session_id)
            if not state:
                return
            state.events.append(event)
            if event.get("type") == "complete":
                state.done = True
                state.latest_output = event.get("payload", {}).get("output")

    async def mark_done(self, session_id: str, output: Any = None) -> None:
        async with self._lock:
            state = self._sessions.get(session_id)
            if not state:
                return
            state.done = True
            if output is not None:
                state.latest_output = output

    async def get(self, session_id: str) -> Optional[SessionState]:
        async with self._lock:
            return self._sessions.get(session_id)

    async def latest_for_agent(self, agent_id: str) -> Optional[SessionState]:
        async with self._lock:
            candidates = [s for s in self._sessions.values() if s.agent_id == agent_id]
            if not candidates:
                return None
            return sorted(candidates, key=lambda s: s.created_at)[-1]

    async def get_or_create_conversation(
        self, conversation_id: Optional[str], agent_id: str
    ) -> ConversationContext:
        async with self._lock:
            if conversation_id and conversation_id in self._conversations:
                return self._conversations[conversation_id]
            cid = conversation_id or str(uuid4())
            ctx = ConversationContext(conversation_id=cid, agent_id=agent_id)
            self._conversations[cid] = ctx
            return ctx

    async def get_conversation(self, conversation_id: str) -> Optional[ConversationContext]:
        async with self._lock:
            return self._conversations.get(conversation_id)


session_manager = SessionManager()
