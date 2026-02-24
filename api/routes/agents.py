from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.services.agent_registry import BY_ID
from api.services.agent_runtime import run_agent_session, run_financial_query, EventEmitter
from api.services.database import connect_db
from api.services.llm import llm_chat, llm_enabled
from api.services.session_manager import session_manager
from api.services.skills import append_training_instruction, read_identity, read_skills, write_skills

router = APIRouter(prefix="/api/agents", tags=["agents"])


class RunResponse(BaseModel):
    session_id: str


class QueryRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None


class QueryResponse(BaseModel):
    session_id: str
    conversation_id: str


class ChatRequest(BaseModel):
    message: str
    apply: bool = False


class SkillsUpdateRequest(BaseModel):
    content: str


async def draft_training_instruction(agent_id: str, message: str) -> str:
    if not llm_enabled():
        raise RuntimeError(
            "Model-only runtime requires USE_REAL_LLM=true and OPENROUTER_API_KEY configured."
        )

    response = await llm_chat(
        [
            {
                "role": "system",
                "content": (
                    "Rewrite user training guidance into one concise operational instruction for an AI agent. "
                    "Return a single sentence and no markdown."
                ),
            },
            {
                "role": "user",
                "content": f"Agent: {agent_id}\\nGuidance: {message}",
            },
        ],
        temperature=0.2,
        max_tokens=120,
    )
    text = response.strip()
    if not text:
        raise RuntimeError("Training model returned empty instruction")
    return text


async def fetchall(conn, query: str, params: tuple[Any, ...] = ()) -> list[Any]:
    cursor = await conn.execute(query, params)
    return await cursor.fetchall()


async def fetchone(conn, query: str, params: tuple[Any, ...] = ()) -> Optional[Any]:
    cursor = await conn.execute(query, params)
    return await cursor.fetchone()


@router.get("")
async def list_agents() -> list[dict[str, Any]]:
    conn = await connect_db()
    try:
        rows = await fetchall(
            conn,
            """
            SELECT a.id, a.name, a.department, a.workspace_type,
                   s.status, s.current_activity, s.last_run_at, s.cost_today, s.tasks_completed_today,
                   COALESCE(r.review_count, 0) AS review_count
            FROM agents a
            JOIN agent_status s ON s.agent_id = a.id
            LEFT JOIN (
                SELECT agent_id, COUNT(*) AS review_count
                FROM review_queue
                WHERE status = 'open'
                GROUP BY agent_id
            ) r ON r.agent_id = a.id
            ORDER BY a.name
            """,
        )
        result = []
        for row in rows:
            agent = dict(row)
            meta = BY_ID.get(agent["id"])
            if meta:
                agent["tool_count"] = len(meta.tools)
                agent["description"] = meta.description
            result.append(agent)
        return result
    finally:
        await conn.close()


@router.get("/{agent_id}")
async def get_agent(agent_id: str) -> dict[str, Any]:
    if agent_id not in BY_ID:
        raise HTTPException(status_code=404, detail="Unknown agent")

    conn = await connect_db()
    try:
        row = await fetchone(
            conn,
            """
            SELECT a.id, a.name, a.department, a.description, a.workspace_type,
                   s.status, s.current_activity, s.last_run_at, s.cost_today, s.tasks_completed_today,
                   COALESCE(r.review_count, 0) AS review_count
            FROM agents a
            JOIN agent_status s ON s.agent_id = a.id
            LEFT JOIN (
                SELECT agent_id, COUNT(*) AS review_count
                FROM review_queue
                WHERE status = 'open'
                GROUP BY agent_id
            ) r ON r.agent_id = a.id
            WHERE a.id = ?
            """,
            (agent_id,),
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Agent not found")

        latest = await session_manager.latest_for_agent(agent_id)
        agent_meta = BY_ID[agent_id]
        response = dict(row)
        response["identity"] = read_identity(agent_id)
        response["skills"] = read_skills(agent_id)
        response["tools"] = list(agent_meta.tools)
        response["agent_description"] = agent_meta.description
        response["tool_count"] = len(agent_meta.tools)
        response["latest_output"] = latest.latest_output if latest else None
        response["latest_session_id"] = latest.session_id if latest else None
        return response
    finally:
        await conn.close()


@router.post("/{agent_id}/run", response_model=RunResponse)
async def run_agent(agent_id: str) -> RunResponse:
    if agent_id not in BY_ID:
        raise HTTPException(status_code=404, detail="Unknown agent")

    # Clear previous run's communications and review items for this agent
    conn = await connect_db()
    try:
        await conn.execute("DELETE FROM communications WHERE agent_id = ?", (agent_id,))
        await conn.execute("DELETE FROM review_queue WHERE agent_id = ?", (agent_id,))
        await conn.commit()
    finally:
        await conn.close()

    session = await session_manager.create(agent_id)

    async def execute() -> None:
        try:
            await run_agent_session(agent_id, session.session_id)
        except Exception as exc:
            await session_manager.append_event(
                session.session_id,
                {
                    "type": "error",
                    "payload": {"message": str(exc)},
                    "session_id": session.session_id,
                    "timestamp": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
                },
            )
            await session_manager.mark_done(session.session_id, output={"error": str(exc)})
            return

    asyncio.create_task(execute())
    return RunResponse(session_id=session.session_id)


@router.post("/financial_reporting/query", response_model=QueryResponse)
async def financial_query(body: QueryRequest) -> QueryResponse:
    agent_id = "financial_reporting"
    if agent_id not in BY_ID:
        raise HTTPException(status_code=404, detail="Unknown agent")

    conversation = await session_manager.get_or_create_conversation(body.conversation_id, agent_id)
    session = await session_manager.create(agent_id)

    async def execute() -> None:
        conn = await connect_db()
        try:
            emitter = EventEmitter(conn, session.session_id, agent_id)
            await conn.execute(
                "UPDATE agent_status SET status = 'working', current_activity = ? WHERE agent_id = ?",
                (f"Analyzing: {body.message[:60]}", agent_id),
            )
            await conn.commit()

            result = await run_financial_query(conn, emitter, body.message, conversation)

            await conn.execute(
                "UPDATE agent_status SET status = 'idle', current_activity = 'Ready', "
                "last_run_at = ?, cost_today = cost_today + ? WHERE agent_id = ?",
                (
                    datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
                    emitter.total_cost,
                    agent_id,
                ),
            )
            await conn.commit()

            await session_manager.append_event(
                session.session_id,
                {
                    "type": "complete",
                    "payload": {
                        "output": result,
                        "metrics": {
                            "cost": round(emitter.total_cost, 6),
                            "raw_cost": round(emitter.total_raw_cost, 6),
                            "multiplier": emitter._multiplier,
                            "input_tokens": emitter.total_input_tokens,
                            "output_tokens": emitter.total_output_tokens,
                            "units_processed": 1,
                            "cost_per_unit": round(emitter.total_cost, 6),
                        },
                    },
                    "session_id": session.session_id,
                    "timestamp": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
                },
            )
        except Exception as exc:
            await session_manager.append_event(
                session.session_id,
                {
                    "type": "error",
                    "payload": {"message": str(exc)},
                    "session_id": session.session_id,
                    "timestamp": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
                },
            )
            await session_manager.mark_done(session.session_id, output={"error": str(exc)})
        finally:
            await conn.close()

    asyncio.create_task(execute())
    return QueryResponse(session_id=session.session_id, conversation_id=conversation.conversation_id)


@router.post("/{agent_id}/chat")
async def training_chat(agent_id: str, body: ChatRequest) -> dict[str, Any]:
    if agent_id not in BY_ID:
        raise HTTPException(status_code=404, detail="Unknown agent")
    if not llm_enabled():
        raise HTTPException(
            status_code=400,
            detail="Model-only runtime requires USE_REAL_LLM=true and OPENROUTER_API_KEY configured.",
        )

    message = body.message.strip()
    updated_generic = None
    if body.apply:
        # When applying, the message is the already-approved instruction — skip LLM.
        updated_generic = append_training_instruction(agent_id, message)
        return {
            "response": "Training update applied to skills.md.",
            "suggested_instruction": message,
            "applied": True,
            "skills": updated_generic,
        }

    suggestion = await draft_training_instruction(agent_id, message)
    return {
        "response": "I interpreted your instruction and can apply it to the skills file.",
        "suggested_instruction": suggestion,
        "applied": False,
        "skills": None,
    }


class AgentAskRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None


@router.post("/{agent_id}/ask")
async def ask_agent(agent_id: str, body: AgentAskRequest) -> dict[str, Any]:
    """Chat with any agent about its last run and work context."""
    if agent_id not in BY_ID:
        raise HTTPException(status_code=404, detail="Unknown agent")
    if not llm_enabled():
        raise HTTPException(status_code=400, detail="LLM not enabled")

    # Build context from last run
    latest = await session_manager.latest_for_agent(agent_id)
    latest_output = latest.latest_output if latest else None
    latest_session_id = latest.session_id if latest else None

    # Get recent activity logs for this agent's last session
    activity_context = ""
    if latest_session_id:
        conn = await connect_db()
        try:
            rows = await fetchall(
                conn,
                """SELECT event_type, message, timestamp
                   FROM activity_logs
                   WHERE agent_id = ? AND session_id = ?
                   ORDER BY id ASC LIMIT 50""",
                (agent_id, latest_session_id),
            )
            activity_context = "\n".join(
                f"[{row['event_type']}] {row['message']}" for row in rows
            )
        finally:
            await conn.close()

    # Build or retrieve conversation
    conversation = await session_manager.get_or_create_conversation(
        body.conversation_id, agent_id
    )

    identity = read_identity(agent_id)
    skills = read_skills(agent_id)

    output_summary = ""
    if latest_output:
        try:
            output_summary = json.dumps(latest_output, indent=2, default=str)[:3000]
        except Exception:
            output_summary = str(latest_output)[:3000]

    system_prompt = (
        f"{identity}\n\n"
        f"Your skills and procedures:\n{skills}\n\n"
        f"You just completed a run. Here is a summary of what you did:\n"
        f"{output_summary or 'No recent run data.'}\n\n"
        f"Activity log from your last run:\n{activity_context[:2000]}\n\n"
        f"Answer the user's question about your work. Be specific and reference actual data "
        f"from your run (invoice numbers, amounts, vendor names, customer names, decisions made). "
        f"If you flagged an exception, explain why. If you matched an invoice, explain the logic. "
        f"Be conversational and helpful."
    )

    messages = [{"role": "system", "content": system_prompt}]
    # Add conversation history
    for msg in conversation.messages[-6:]:
        messages.append(msg)
    messages.append({"role": "user", "content": body.message})

    response_text = await llm_chat(
        messages, temperature=0.3, max_tokens=600
    )

    conversation.append_message("user", body.message)
    conversation.append_message("assistant", response_text)

    return {
        "response": response_text,
        "conversation_id": conversation.conversation_id,
    }


@router.get("/{agent_id}/skills")
async def get_skills(agent_id: str) -> dict[str, Any]:
    if agent_id not in BY_ID:
        raise HTTPException(status_code=404, detail="Unknown agent")
    return {"agent_id": agent_id, "skills": read_skills(agent_id)}


@router.put("/{agent_id}/skills")
async def put_skills(agent_id: str, body: SkillsUpdateRequest) -> dict[str, Any]:
    if agent_id not in BY_ID:
        raise HTTPException(status_code=404, detail="Unknown agent")
    write_skills(agent_id, body.content)
    return {"agent_id": agent_id, "skills": body.content, "updated_at": datetime.utcnow().isoformat() + "Z"}


@router.get("/{agent_id}/review-queue")
async def get_review_queue(agent_id: str) -> list[dict[str, Any]]:
    if agent_id not in BY_ID:
        raise HTTPException(status_code=404, detail="Unknown agent")

    conn = await connect_db()
    try:
        rows = await fetchall(
            conn,
            """
            SELECT id, agent_id, item_ref, reason_code, details, context, status, created_at, action, actioned_at
            FROM review_queue
            WHERE agent_id = ?
            ORDER BY created_at DESC
            """,
            (agent_id,),
        )
        result = []
        for row in rows:
            item = dict(row)
            if item.get("context"):
                try:
                    item["context"] = json.loads(item["context"])
                except (json.JSONDecodeError, TypeError):
                    item["context"] = None
            result.append(item)
        return result
    finally:
        await conn.close()


@router.get("/{agent_id}/activity")
async def get_activity(agent_id: str, session_id: Optional[str] = None) -> list[dict[str, Any]]:
    if agent_id not in BY_ID:
        raise HTTPException(status_code=404, detail="Unknown agent")

    conn = await connect_db()
    try:
        if session_id:
            rows = await fetchall(
                conn,
                """
                SELECT event_type, message, cost, input_tokens, output_tokens, timestamp, session_id
                FROM activity_logs
                WHERE agent_id = ? AND session_id = ?
                ORDER BY id ASC
                """,
                (agent_id, session_id),
            )
        else:
            rows = await fetchall(
                conn,
                """
                SELECT event_type, message, cost, input_tokens, output_tokens, timestamp, session_id
                FROM activity_logs
                WHERE agent_id = ?
                ORDER BY id DESC
                LIMIT 200
                """,
                (agent_id,),
            )

        return [dict(row) for row in rows]
    finally:
        await conn.close()


@router.get("/{agent_id}/decisions")
async def get_decisions(agent_id: str, session_id: Optional[str] = None) -> list[dict[str, Any]]:
    """Retrieve decision history for an agent's last run or specific session."""
    if agent_id not in BY_ID:
        raise HTTPException(status_code=404, detail="Unknown agent")

    # Get the session to retrieve from
    target_session = None
    if session_id:
        target_session = await session_manager.get(session_id)
    else:
        target_session = await session_manager.latest_for_agent(agent_id)

    if not target_session:
        return []

    # Extract decisions from session events
    decisions = []
    for event in target_session.events:
        decision = None

        # Tool results contain decision information
        if event.get("type") == "tool_result":
            payload = event.get("payload", {})
            tool = payload.get("tool", "")
            result = payload.get("result", {})

            # PO Match: match or exception decision
            if tool == "complete_invoice":
                decision = {
                    "timestamp": event.get("timestamp"),
                    "agent_id": agent_id,
                    "decision_type": "po_match",
                    "status": result.get("status", "unknown"),
                    "confidence": result.get("confidence", 0),
                    "reasoning": result.get("reasoning", ""),
                    "invoice_number": result.get("invoice_number"),
                    "vendor": result.get("vendor"),
                    "amount": result.get("amount"),
                    "matched_po": result.get("matched_po"),
                    "variance": result.get("variance"),
                }
            # AR Follow-Up: account action decision
            elif tool == "complete_account":
                decision = {
                    "timestamp": event.get("timestamp"),
                    "agent_id": agent_id,
                    "decision_type": "ar_action",
                    "action": result.get("action", "unknown"),
                    "reasoning": result.get("reason", ""),
                    "customer_name": result.get("customer_name"),
                    "days_overdue": result.get("days_out"),
                    "amount": result.get("amount"),
                    "email_sent": result.get("email_sent", False),
                    "escalation_level": result.get("escalation_level"),
                }
            # PO Match: exception flag decision
            elif tool == "flag_exception":
                decision = {
                    "timestamp": event.get("timestamp"),
                    "agent_id": agent_id,
                    "decision_type": "exception_flag",
                    "reason_code": result.get("reason_code"),
                    "reason_detail": result.get("reason_detail", ""),
                    "confidence": 0.95,  # Exception flagging is high confidence
                    "item_ref": result.get("item_ref"),
                }
            # Financial Reporting: report decision
            elif tool == "generate_report":
                decision = {
                    "timestamp": event.get("timestamp"),
                    "agent_id": agent_id,
                    "decision_type": "report_generation",
                    "report_type": result.get("report_type"),
                    "dimensions": result.get("dimensions", []),
                    "reasoning": result.get("reasoning", ""),
                    "confidence": result.get("confidence", 0.9),
                }
            # Vendor Compliance: compliance decision
            elif tool == "check_vendor":
                decision = {
                    "timestamp": event.get("timestamp"),
                    "agent_id": agent_id,
                    "decision_type": "vendor_compliance",
                    "vendor_name": result.get("vendor_name"),
                    "compliance_status": result.get("status", "unknown"),
                    "issues": result.get("issues", []),
                    "actions_recommended": result.get("recommendations", []),
                    "reasoning": result.get("reasoning", ""),
                }

        if decision:
            decisions.append(decision)

    return decisions
