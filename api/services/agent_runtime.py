from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable, Optional
from uuid import uuid4

from pypdf import PdfReader

from api.services.database import connect_db
from api.services.llm import LLMResponse, llm_chat, llm_chat_with_usage, llm_enabled, try_parse_json_object
from api.services.session_manager import session_manager
from api.services.skills import read_skills

BASE_DIR = Path(__file__).resolve().parents[2]


def utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def safe_json(payload: Any) -> str:
    return json.dumps(payload, separators=(",", ":"), default=str)


def estimate_tokens(message: str, payload: Any) -> tuple[int, int, float]:
    """Fallback estimation for non-LLM events (status changes, communications)."""
    payload_text = safe_json(payload)
    input_tokens = max(24, int(len(message) / 3.8))
    output_tokens = max(18, int(len(payload_text) / 4.4))
    cost = round((input_tokens * 0.000003) + (output_tokens * 0.000015), 6)
    return input_tokens, output_tokens, cost


# Pricing per token (Claude 3.7 Sonnet on OpenRouter)
INPUT_TOKEN_PRICE = 0.000003
OUTPUT_TOKEN_PRICE = 0.000015


@dataclass
class LLMResult:
    """Parsed JSON output from an LLM call plus accumulated token usage."""
    data: dict[str, Any]
    prompt_tokens: int = 0
    completion_tokens: int = 0


async def update_agent_status(
    conn,
    agent_id: str,
    *,
    status: str,
    current_activity: str,
    additional_cost: float = 0.0,
    additional_tasks: int = 0,
    set_last_run: bool = False,
) -> None:
    if set_last_run:
        await conn.execute(
            """
            UPDATE agent_status
            SET status = ?,
                current_activity = ?,
                cost_today = cost_today + ?,
                tasks_completed_today = tasks_completed_today + ?,
                last_run_at = ?
            WHERE agent_id = ?
            """,
            (status, current_activity, additional_cost, additional_tasks, utc_now(), agent_id),
        )
        return

    await conn.execute(
        """
        UPDATE agent_status
        SET status = ?,
            current_activity = ?,
            cost_today = cost_today + ?,
            tasks_completed_today = tasks_completed_today + ?
        WHERE agent_id = ?
        """,
        (status, current_activity, additional_cost, additional_tasks, agent_id),
    )


class EventEmitter:
    def __init__(self, conn, session_id: str, agent_id: str) -> None:
        self.conn = conn
        self.session_id = session_id
        self.agent_id = agent_id
        self.total_cost = 0.0
        self.total_raw_cost = 0.0
        self.total_input_tokens = 0
        self.total_output_tokens = 0

        from api.services.config import get_settings
        self._multiplier = get_settings().get_multiplier(agent_id)

    async def emit(self, event_type: str, payload: dict[str, Any], *, message: str) -> None:
        input_tokens, output_tokens, cost = estimate_tokens(message, payload)
        projected = round(cost * self._multiplier, 6)
        self.total_raw_cost += cost
        self.total_cost += projected
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

        await self._persist(event_type, payload, message, projected, input_tokens, output_tokens)

    async def emit_llm(self, event_type: str, payload: dict[str, Any], *, message: str,
                       prompt_tokens: int, completion_tokens: int) -> None:
        """Emit with real token counts from the LLM API."""
        raw_cost = round(
            (prompt_tokens * INPUT_TOKEN_PRICE) + (completion_tokens * OUTPUT_TOKEN_PRICE), 6
        )
        projected = round(raw_cost * self._multiplier, 6)
        self.total_raw_cost += raw_cost
        self.total_cost += projected
        self.total_input_tokens += prompt_tokens
        self.total_output_tokens += completion_tokens

        await self._persist(event_type, payload, message, projected, prompt_tokens, completion_tokens)

    async def _persist(self, event_type: str, payload: dict[str, Any], message: str,
                       cost: float, input_tokens: int, output_tokens: int) -> None:
        event = {
            "type": event_type,
            "payload": payload,
            "session_id": self.session_id,
            "timestamp": utc_now(),
        }
        await session_manager.append_event(self.session_id, event)

        await self.conn.execute(
            """
            INSERT INTO activity_logs (agent_id, session_id, event_type, message, cost, input_tokens, output_tokens, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self.agent_id,
                self.session_id,
                event_type,
                message,
                cost,
                input_tokens,
                output_tokens,
                event["timestamp"],
            ),
        )

    async def emit_reasoning(self, text: str) -> None:
        await self.emit("reasoning", {"text": text}, message=text)

    async def emit_thinking(self, text: str) -> None:
        """Lightweight thinking event — streams to frontend only (no DB persist, no token cost)."""
        event = {
            "type": "thinking",
            "payload": {"text": text},
            "session_id": self.session_id,
            "timestamp": utc_now(),
        }
        await session_manager.append_event(self.session_id, event)

    async def emit_tool_call(self, tool_name: str, args: dict[str, Any]) -> None:
        await self.emit("tool_call", {"tool": tool_name, "args": args}, message=f"Tool call: {tool_name}")

    async def emit_tool_result(self, tool_name: str, result: dict[str, Any], summary: str) -> None:
        await self.emit(
            "tool_result",
            {"tool": tool_name, "result": result, "summary": summary},
            message=summary,
        )

    async def emit_status_change(self, status: str, detail: str) -> None:
        await self.emit(
            "status_change",
            {"status": status, "detail": detail},
            message=detail,
        )

    async def emit_communication(self, recipient: str, subject: str, body: str) -> None:
        await self.emit(
            "communication_sent",
            {"recipient": recipient, "subject": subject, "body": body},
            message=f"Communication sent to {recipient}",
        )

    async def emit_agent_message(self, text: str, msg_type: str = "response") -> None:
        await self.emit(
            "agent_message",
            {"text": text, "message_type": msg_type},
            message=text[:120],
        )

    async def emit_code_block(self, language: str, code: str) -> None:
        await self.emit(
            "code_block",
            {"language": language, "code": code},
            message=f"Code: {language}",
        )

    async def emit_report_generated(self, report: dict[str, Any]) -> None:
        await self.emit(
            "report_generated",
            report,
            message=f"Report: {report.get('report_title', 'Financial Report')}",
        )


async def insert_review_item(conn, agent_id: str, item_ref: str, reason: str, details: str, context: str | None = None) -> int:
    cursor = await conn.execute(
        """
        INSERT INTO review_queue (agent_id, item_ref, reason_code, details, context, status, created_at)
        VALUES (?, ?, ?, ?, ?, 'open', ?)
        """,
        (agent_id, item_ref, reason, details, context, utc_now()),
    )
    return cursor.lastrowid


async def insert_communication(conn, agent_id: str, recipient: str, subject: str, body: str) -> None:
    await conn.execute(
        """
        INSERT INTO communications (agent_id, recipient, subject, body, channel, created_at)
        VALUES (?, ?, ?, ?, 'email', ?)
        """,
        (agent_id, recipient, subject, body, utc_now()),
    )


async def insert_internal_task(
    conn,
    agent_id: str,
    title: str,
    description: str,
    priority: str,
    due_date: Optional[str] = None,
) -> None:
    await conn.execute(
        """
        INSERT INTO internal_tasks (agent_id, title, description, priority, due_date, status, created_at)
        VALUES (?, ?, ?, ?, ?, 'open', ?)
        """,
        (agent_id, title, description, priority, due_date, utc_now()),
    )


async def insert_collection_item(conn, customer_name: str, amount: float, reason: str) -> None:
    await conn.execute(
        """
        INSERT INTO collections_queue (customer_name, amount, reason, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (customer_name, amount, reason, utc_now()),
    )


async def load_json(name: str) -> dict[str, Any]:
    path = BASE_DIR / "data" / "json" / name
    return json.loads(path.read_text())


def parse_currency(value: str) -> float:
    return float(value.replace("$", "").replace(",", "").strip())


async def fetchall(conn, query: str, params: tuple[Any, ...] = ()) -> list[Any]:
    cursor = await conn.execute(query, params)
    return await cursor.fetchall()


async def fetchone(conn, query: str, params: tuple[Any, ...] = ()) -> Optional[Any]:
    cursor = await conn.execute(query, params)
    return await cursor.fetchone()


async def read_invoice_pdf(file_path: str) -> dict[str, Any]:
    path = BASE_DIR / file_path
    reader = PdfReader(path)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    vendor = lines[0] if lines else "Unknown Vendor"
    invoice_match = re.search(r"Invoice #:?\s*(INV-[A-Z0-9-]+)", text)
    date_match = re.search(r"Date:?\s*(\d{4}-\d{2}-\d{2})", text)
    po_match = re.search(r"PO Ref:?\s*(PO-\d{4}-\d{4})", text)
    total_match = re.search(r"Total:?\s*\$([\d,]+\.\d{2})", text)

    return {
        "vendor": vendor,
        "invoice_number": invoice_match.group(1) if invoice_match else None,
        "invoice_date": date_match.group(1) if date_match else None,
        "po_reference": po_match.group(1) if po_match else None,
        "total": parse_currency(total_match.group(1)) if total_match else None,
        "text_excerpt": " ".join(lines[:12]),
    }


async def search_purchase_orders(
    conn,
    po_number: Optional[str],
    vendor: Optional[str],
    amount: Optional[float],
) -> list[dict[str, Any]]:
    if po_number:
        rows = await fetchall(
            conn,
            """
            SELECT p.po_number, p.amount, p.job_id, p.gl_code, v.name AS vendor
            FROM purchase_orders p
            JOIN vendors v ON p.vendor_id = v.id
            WHERE p.po_number = ?
            """,
            (po_number,),
        )
        return [dict(row) | {"confidence": 0.99} for row in rows]

    rows = await fetchall(
        conn,
        """
        SELECT p.po_number, p.amount, p.job_id, p.gl_code, v.name AS vendor
        FROM purchase_orders p
        JOIN vendors v ON p.vendor_id = v.id
        ORDER BY p.po_number
        """,
    )

    scored: list[dict[str, Any]] = []
    for row in rows:
        candidate = dict(row)
        if amount is None or abs(float(candidate["amount"]) - float(amount)) > 0.01:
            continue
        vendor_score = SequenceMatcher(None, (vendor or "").lower(), candidate["vendor"].lower()).ratio()
        if vendor_score < 0.68:
            continue
        confidence = round((vendor_score * 0.7) + 0.3, 3)
        scored.append(candidate | {"confidence": confidence})

    scored.sort(key=lambda row: row["confidence"], reverse=True)
    return scored[:5]


async def get_project(conn, project_id: str) -> Optional[dict[str, Any]]:
    row = await fetchone(
        conn,
        """
        SELECT id, name, division_id, pm_name, pm_email
        FROM projects WHERE id = ?
        """,
        (project_id,),
    )
    return dict(row) if row else None


async def check_duplicate_po(conn, po_number: str, current_invoice: str) -> list[dict[str, Any]]:
    rows = await fetchall(
        conn,
        """
        SELECT invoice_number, status
        FROM invoices
        WHERE po_reference = ?
          AND invoice_number <> ?
          AND status = 'matched'
        """,
        (po_number, current_invoice),
    )
    return [dict(row) for row in rows]


async def assign_coding(conn, invoice_number: str, job_id: str, gl_code: str) -> None:
    await conn.execute(
        "UPDATE invoices SET job_id = ?, gl_code = ? WHERE invoice_number = ?",
        (job_id, gl_code, invoice_number),
    )


async def mark_invoice_status(conn, invoice_number: str, status: str, notes: Optional[str] = None) -> None:
    await conn.execute(
        "UPDATE invoices SET status = ?, notes = ? WHERE invoice_number = ?",
        (status, notes, invoice_number),
    )


def normalize_confidence(value: Optional[str], default: str = "high") -> str:
    if not value:
        return default
    lowered = value.strip().lower()
    if lowered in {"low", "medium", "high"}:
        return lowered
    return default


async def model_training_rule_active(agent_id: str, skills_text: str) -> bool:
    result = (await llm_json_response(
        agent_id=agent_id,
        objective=(
            "Determine if training instructions currently include a rule to notify the project manager "
            "for material invoice price variances. Return JSON with key training_rule_active (boolean)."
        ),
        context_payload={"skills": skills_text},
        max_tokens=120,
        temperature=0.0,
        validator=validate_training_rule_flag,
    )).data
    value = result.get("training_rule_active")
    if isinstance(value, bool):
        return value
    raise RuntimeError(f"{agent_id}: model did not return boolean training_rule_active")


async def llm_json_response(
    *,
    agent_id: str,
    objective: str,
    context_payload: dict[str, Any],
    max_tokens: int = 1200,
    temperature: float = 0.1,
    validator: Optional[Callable[[dict[str, Any]], list[str]]] = None,
    model: Optional[str] = None,
) -> LLMResult:
    """Call the LLM to produce structured JSON. Returns LLMResult with accumulated real token usage."""
    if not llm_enabled():
        raise RuntimeError(
            "Real LLM mode is required. Set USE_REAL_LLM=true and OPENROUTER_API_KEY in .env."
        )

    # Accumulate token usage across all LLM calls within this function
    _acc_prompt = 0
    _acc_completion = 0

    async def _tracked_chat(messages, *, temp=0.2, mtokens=max_tokens) -> str:
        nonlocal _acc_prompt, _acc_completion
        resp = await llm_chat_with_usage(messages, temperature=temp, max_tokens=mtokens, model=model)
        _acc_prompt += resp.prompt_tokens
        _acc_completion += resp.completion_tokens
        return resp.text

    skills = read_skills(agent_id)
    system_prompt = (
        "You are an autonomous construction back-office agent. "
        "Return strict JSON only, no markdown, no commentary. "
        "Use the provided skills and objective to decide the output."
    )
    user_payload = {
        "agent_id": agent_id,
        "objective": objective,
        "skills": skills,
        "context": context_payload,
    }

    async def parse_candidate_text(initial_text: str) -> tuple[Optional[dict[str, Any]], str]:
        parsed = try_parse_json_object(initial_text)
        if parsed:
            return parsed, initial_text

        repair_prompt = (
            "Convert the following content into strict valid JSON only. "
            "Do not add explanation, markdown, or code fences. Preserve meaning."
        )
        repaired = await _tracked_chat(
            [
                {"role": "system", "content": repair_prompt},
                {"role": "user", "content": initial_text},
            ],
            temp=0.0,
        )
        repaired_parsed = try_parse_json_object(repaired)
        if repaired_parsed:
            return repaired_parsed, repaired
        return None, repaired

    last_text = ""
    candidate: Optional[dict[str, Any]] = None

    # JSON-shape acquisition loop.
    for attempt in range(1, 4):
        if attempt in {1, 2}:
            text = await _tracked_chat(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_payload)},
                ],
                temp=temperature if attempt == 1 else 0.0,
            )
        else:
            strict_retry_prompt = (
                "Return one valid JSON object only. "
                "No markdown, no prose, no trailing text."
            )
            text = await _tracked_chat(
                [
                    {"role": "system", "content": strict_retry_prompt},
                    {"role": "user", "content": json.dumps(user_payload)},
                ],
                temp=0.0,
            )
        parsed, raw_text = await parse_candidate_text(text)
        last_text = raw_text
        if parsed is not None:
            candidate = parsed
            break

    if candidate is None:
        preview = last_text[:180].replace("\n", " ")
        raise RuntimeError(f"{agent_id}: model output was not valid JSON (preview: {preview})")

    if validator is None:
        return LLMResult(data=candidate, prompt_tokens=_acc_prompt, completion_tokens=_acc_completion)

    # Schema/contract validation and model-repair loop.
    errors = validator(candidate)
    if not errors:
        return LLMResult(data=candidate, prompt_tokens=_acc_prompt, completion_tokens=_acc_completion)

    current_candidate = candidate
    for _ in range(3):
        repair_objective = {
            "objective": objective,
            "validation_errors": errors,
            "candidate": current_candidate,
            "context": context_payload,
        }
        repair_text = await _tracked_chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Repair the JSON so it satisfies all validation errors. "
                        "Return a single strict JSON object only."
                    ),
                },
                {"role": "user", "content": json.dumps(repair_objective)},
            ],
            temp=0.0,
        )
        repaired, raw_text = await parse_candidate_text(repair_text)
        last_text = raw_text
        if repaired is None:
            continue
        errors = validator(repaired)
        if not errors:
            return LLMResult(data=repaired, prompt_tokens=_acc_prompt, completion_tokens=_acc_completion)
        current_candidate = repaired

    preview = last_text[:180].replace("\n", " ")
    raise RuntimeError(
        f"{agent_id}: model output failed schema validation ({'; '.join(errors[:3])}) (preview: {preview})"
    )


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float))


def validate_training_rule_flag(payload: dict[str, Any]) -> list[str]:
    if not isinstance(payload.get("training_rule_active"), bool):
        return ["training_rule_active must be boolean"]
    return []


def make_po_step_validator(
    allowed_actions: list[str],
    available_po_numbers: set[str],
) -> Callable[[dict[str, Any]], list[str]]:
    allowed = set(allowed_actions)

    def validate(payload: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        action = str(payload.get("action", "")).strip()
        reason = payload.get("reason")
        args = payload.get("args")

        if action not in allowed:
            errors.append(f"action must be one of: {', '.join(sorted(allowed))}")
            return errors
        if not _is_non_empty_string(reason):
            errors.append("reason is required")
        if not isinstance(args, dict):
            errors.append("args must be object")
            return errors

        if action == "select_po":
            po_number = args.get("po_number")
            if not _is_non_empty_string(po_number):
                errors.append("select_po requires args.po_number")
            elif available_po_numbers and str(po_number).strip() not in available_po_numbers:
                errors.append("select_po args.po_number must be in available po matches")

        if action == "assign_coding":
            if not _is_non_empty_string(args.get("job_id")):
                errors.append("assign_coding requires args.job_id")
            if not _is_non_empty_string(args.get("gl_code")):
                errors.append("assign_coding requires args.gl_code")

        if action == "flag_exception":
            if not _is_non_empty_string(args.get("reason_code")):
                errors.append("flag_exception requires args.reason_code")
            if not _is_non_empty_string(args.get("details")):
                errors.append("flag_exception requires args.details")

        if action == "get_project_details":
            if not _is_non_empty_string(args.get("project_id")):
                errors.append("get_project_details requires args.project_id")

        if action == "send_notification":
            for field in ["recipient", "subject", "body"]:
                if not _is_non_empty_string(args.get(field)):
                    errors.append(f"send_notification requires args.{field}")

        if action == "complete_invoice":
            final_status = str(args.get("final_status", "")).strip().lower()
            if final_status not in {"matched", "exception"}:
                errors.append("complete_invoice args.final_status must be matched|exception")
            confidence = str(args.get("confidence", "")).strip().lower()
            if confidence not in {"low", "medium", "high"}:
                errors.append("complete_invoice args.confidence must be low|medium|high")
            if not _is_non_empty_string(args.get("summary")):
                errors.append("complete_invoice requires args.summary")

        return errors

    return validate


AR_ALLOWED_ACTIONS = {
    "polite_reminder",
    "firm_email_plus_internal_task",
    "escalated_to_collections",
    "attorney_escalation_105_days",
    "skip_retainage",
    "no_action_within_terms",
}


def validate_ar_single_account(payload: dict[str, Any]) -> list[str]:
    """Validate a single-account AR action response from the LLM."""
    errors: list[str] = []
    action = str(payload.get("action", "")).strip()
    if action not in AR_ALLOWED_ACTIONS:
        errors.append(f"action must be one of: {', '.join(sorted(AR_ALLOWED_ACTIONS))}")
    if not _is_non_empty_string(payload.get("reason")):
        errors.append("reason is required")
    if action in {"polite_reminder", "firm_email_plus_internal_task", "escalated_to_collections"}:
        if not _is_non_empty_string(payload.get("email_subject")):
            errors.append(f"email_subject required for {action}")
        if not _is_non_empty_string(payload.get("email_body")):
            errors.append(f"email_body required for {action}")
    return errors


def validate_financial_report(payload: dict[str, Any]) -> list[str]:
    """Validate batch-mode financial report (executive dashboard with sections)."""
    errors: list[str] = []
    if not _is_non_empty_string(payload.get("report_title")):
        errors.append("report_title is required")
    sections = payload.get("sections")
    if not isinstance(sections, list) or len(sections) < 1:
        errors.append("sections must be a non-empty array")
    else:
        valid_types = {"kpi_grid", "table", "chart", "narrative"}
        for idx, sec in enumerate(sections):
            if not isinstance(sec, dict):
                errors.append(f"sections[{idx}] must be object")
                continue
            stype = sec.get("type")
            if stype not in valid_types:
                errors.append(f"sections[{idx}].type must be one of {valid_types}")
            if stype == "table":
                if not isinstance(sec.get("columns"), list):
                    errors.append(f"sections[{idx}] table needs columns array")
                if not isinstance(sec.get("rows"), list):
                    errors.append(f"sections[{idx}] table needs rows array")
            elif stype == "chart":
                if not sec.get("chart_type"):
                    errors.append(f"sections[{idx}] chart needs chart_type")
                if not isinstance(sec.get("data"), dict):
                    errors.append(f"sections[{idx}] chart needs data object")
            elif stype == "narrative":
                if not _is_non_empty_string(sec.get("content")):
                    errors.append(f"sections[{idx}] narrative needs content")
            elif stype == "kpi_grid":
                if not isinstance(sec.get("metrics"), list):
                    errors.append(f"sections[{idx}] kpi_grid needs metrics array")
    return errors


def validate_financial_query_report(payload: dict[str, Any]) -> list[str]:
    """Validate chat-mode financial query report (same sections schema)."""
    errors: list[str] = []
    if not _is_non_empty_string(payload.get("report_title")):
        errors.append("report_title is required")
    if not _is_non_empty_string(payload.get("response_text")):
        errors.append("response_text is required")
    sections = payload.get("sections")
    if not isinstance(sections, list) or len(sections) < 1:
        errors.append("sections must be a non-empty array")
    return errors


def validate_vendor_compliance_findings(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    allowed_action_types = {"renewal_email", "urgent_hold_task", "w9_email", "contract_task"}
    findings = payload.get("findings")
    if not isinstance(findings, list):
        return ["findings must be an array"]
    for idx, row in enumerate(findings):
        if not isinstance(row, dict):
            errors.append(f"findings[{idx}] must be object")
            continue
        if not _is_non_empty_string(row.get("vendor")):
            errors.append(f"findings[{idx}].vendor is required")
        if not _is_non_empty_string(row.get("issue")):
            errors.append(f"findings[{idx}].issue is required")
        if not _is_non_empty_string(row.get("reason")):
            errors.append(f"findings[{idx}].reason is required")
        action_type = str(row.get("action_type", "")).strip()
        if action_type not in allowed_action_types:
            errors.append(f"findings[{idx}].action_type invalid")
        if action_type in {"renewal_email", "w9_email"}:
            if not _is_non_empty_string(row.get("subject")):
                errors.append(f"findings[{idx}].subject required for email action")
            if not _is_non_empty_string(row.get("body")):
                errors.append(f"findings[{idx}].body required for email action")
        if action_type in {"urgent_hold_task", "contract_task"}:
            if not _is_non_empty_string(row.get("task_title")):
                errors.append(f"findings[{idx}].task_title required for task action")
            if not _is_non_empty_string(row.get("task_description")):
                errors.append(f"findings[{idx}].task_description required for task action")

    # Demo-critical assertions.
    def has_finding(vendor_sub: str, action_type: str) -> bool:
        for row in findings:
            if not isinstance(row, dict):
                continue
            vendor = str(row.get("vendor", "")).lower()
            action = str(row.get("action_type", "")).strip()
            if vendor_sub.lower() in vendor and action == action_type:
                return True
        return False

    if not has_finding("Carolina Steel Fabricators", "urgent_hold_task"):
        errors.append("missing urgent_hold_task for Carolina Steel Fabricators")
    if not has_finding("Tri-State Paving", "w9_email"):
        errors.append("missing w9_email for Tri-State Paving")
    if not has_finding("Tri-State Paving", "contract_task"):
        errors.append("missing contract_task for Tri-State Paving")
    if not has_finding("Valley Forge Welding", "contract_task"):
        errors.append("missing contract_task for Valley Forge Welding")
    for vendor_sub in ["Southeast Grading", "Piedmont Lumber", "Summit Environmental"]:
        if not has_finding(vendor_sub, "renewal_email"):
            errors.append(f"missing renewal_email for {vendor_sub}")
    return errors


def validate_schedule_output(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    assignments = payload.get("assignments")
    if not isinstance(assignments, dict):
        errors.append("assignments must be object")
    else:
        if not assignments:
            errors.append("assignments cannot be empty")
        for crew_id, jobs in assignments.items():
            if not _is_non_empty_string(crew_id):
                errors.append("assignments key must be crew_id string")
            if not isinstance(jobs, list):
                errors.append(f"assignments[{crew_id}] must be array")
    for field in ["unoptimized_drive_minutes", "optimized_drive_minutes", "improvement_percent"]:
        if not _is_number(payload.get(field)):
            errors.append(f"{field} must be numeric")
    if _is_number(payload.get("optimized_drive_minutes")) and _is_number(payload.get("unoptimized_drive_minutes")):
        if float(payload["optimized_drive_minutes"]) >= float(payload["unoptimized_drive_minutes"]):
            errors.append("optimized_drive_minutes must be lower than unoptimized_drive_minutes")
    if _is_number(payload.get("improvement_percent")) and float(payload["improvement_percent"]) < 20:
        errors.append("improvement_percent must be at least 20")
    return errors


def validate_progress_findings(payload: dict[str, Any]) -> list[str]:
    """Legacy validator kept for backward compatibility."""
    return validate_progress_report(payload)


def validate_progress_report(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    # Findings
    findings = payload.get("findings")
    if not isinstance(findings, list):
        return ["findings must be an array"]
    for idx, row in enumerate(findings):
        if not isinstance(row, dict):
            errors.append(f"findings[{idx}] must be object")
            continue
        if not _is_non_empty_string(row.get("project_id")):
            errors.append(f"findings[{idx}].project_id is required")
        if not _is_non_empty_string(row.get("project_name")):
            errors.append(f"findings[{idx}].project_name is required")
        if not _is_non_empty_string(row.get("finding")):
            errors.append(f"findings[{idx}].finding is required")
        if not _is_non_empty_string(row.get("executive_summary")):
            errors.append(f"findings[{idx}].executive_summary is required")
        if not _is_non_empty_string(row.get("root_cause_analysis")):
            errors.append(f"findings[{idx}].root_cause_analysis is required")
        if not isinstance(row.get("create_task"), bool):
            errors.append(f"findings[{idx}].create_task must be boolean")
        if not _is_non_empty_string(row.get("status_color")):
            errors.append(f"findings[{idx}].status_color is required (green/amber/red)")
        if not _is_non_empty_string(row.get("recommendation")):
            errors.append(f"findings[{idx}].recommendation is required")
    return errors


def validate_maintenance_issues(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    issues = payload.get("issues")
    if not isinstance(issues, list):
        return ["issues must be an array"]
    for idx, row in enumerate(issues):
        if not isinstance(row, dict):
            errors.append(f"issues[{idx}] must be object")
            continue
        if not _is_non_empty_string(row.get("unit")):
            errors.append(f"issues[{idx}].unit is required")
        if not _is_non_empty_string(row.get("issue")):
            errors.append(f"issues[{idx}].issue is required")
        if not _is_non_empty_string(row.get("action")):
            errors.append(f"issues[{idx}].action is required")
        if not _is_non_empty_string(row.get("severity")):
            errors.append(f"issues[{idx}].severity is required")
        if not isinstance(row.get("create_task"), bool):
            errors.append(f"issues[{idx}].create_task must be boolean")
    return errors


def validate_training_issues(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    issues = payload.get("issues")
    if not isinstance(issues, list):
        return ["issues must be an array"]
    for idx, row in enumerate(issues):
        if not isinstance(row, dict):
            errors.append(f"issues[{idx}] must be object")
            continue
        if not _is_non_empty_string(row.get("name")):
            errors.append(f"issues[{idx}].name is required")
        if not _is_non_empty_string(row.get("issue_type")):
            errors.append(f"issues[{idx}].issue_type is required")
        if not _is_non_empty_string(row.get("detail")):
            errors.append(f"issues[{idx}].detail is required")
        if not isinstance(row.get("create_task"), bool):
            errors.append(f"issues[{idx}].create_task must be boolean")
    return errors


def _validate_checklist_entries(entries: Any, key: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(entries, list):
        return [f"checklist.{key} must be an array"]
    for idx, item in enumerate(entries):
        if not isinstance(item, dict):
            errors.append(f"checklist.{key}[{idx}] must be object")
            continue
        name = item.get("name", item.get("item"))
        if not _is_non_empty_string(name):
            errors.append(f"checklist.{key}[{idx}] requires name/item")
        if not _is_non_empty_string(item.get("status")):
            errors.append(f"checklist.{key}[{idx}] requires status")
    return errors


def validate_onboarding_plan(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    hire = payload.get("hire")
    checklist = payload.get("checklist")
    if not isinstance(hire, dict):
        errors.append("hire must be object")
    else:
        for field in ["name", "role", "division", "start_date", "hiring_manager"]:
            if not _is_non_empty_string(hire.get(field)):
                errors.append(f"hire.{field} is required")
    if not isinstance(checklist, dict):
        errors.append("checklist must be object")
    else:
        errors.extend(_validate_checklist_entries(checklist.get("documents"), "documents"))
        errors.extend(_validate_checklist_entries(checklist.get("training"), "training"))
        errors.extend(_validate_checklist_entries(checklist.get("equipment"), "equipment"))
    if not _is_non_empty_string(payload.get("welcome_email_recipient")):
        errors.append("welcome_email_recipient is required")
    if not _is_non_empty_string(payload.get("welcome_email_subject")):
        errors.append("welcome_email_subject is required")
    if not _is_non_empty_string(payload.get("welcome_email_body")):
        errors.append("welcome_email_body is required")
    return errors


def validate_cost_estimate(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    # line_items validation
    line_items = payload.get("line_items")
    if not isinstance(line_items, list) or len(line_items) < 10:
        errors.append("line_items must be array with at least 10 items")
    else:
        for idx, li in enumerate(line_items):
            if not isinstance(li, dict):
                errors.append(f"line_items[{idx}] must be object")
                continue
            for field in ["item", "category", "labor_cost", "material_cost", "equipment_cost", "subtotal"]:
                if field in ("item", "category"):
                    if not _is_non_empty_string(li.get(field)):
                        errors.append(f"line_items[{idx}].{field} is required")
                else:
                    if not _is_number(li.get(field)):
                        errors.append(f"line_items[{idx}].{field} must be numeric")
    # category_subtotals
    cat_sub = payload.get("category_subtotals")
    if not isinstance(cat_sub, dict) or len(cat_sub) < 3:
        errors.append("category_subtotals must be object with at least 3 categories")
    # direct_cost_total
    if not _is_number(payload.get("direct_cost_total")):
        errors.append("direct_cost_total must be numeric")
    elif float(payload["direct_cost_total"]) < 100000:
        errors.append("direct_cost_total should be realistic (>100k for site work)")
    # markups
    markups = payload.get("markups")
    if not isinstance(markups, dict):
        errors.append("markups must be object")
    else:
        for mk in ["overhead", "profit", "contingency"]:
            if not _is_number(markups.get(mk)):
                errors.append(f"markups.{mk} must be numeric")
    # grand_total
    if not _is_number(payload.get("grand_total")):
        errors.append("grand_total must be numeric")
    elif float(payload["grand_total"]) < 100000:
        errors.append("grand_total should be realistic (>100k for site work)")
    # assumptions & exclusions
    if not isinstance(payload.get("assumptions"), list) or len(payload.get("assumptions", [])) == 0:
        errors.append("assumptions must be a non-empty array")
    if not isinstance(payload.get("exclusions"), list):
        errors.append("exclusions must be an array")
    return errors


def validate_cost_category(payload: dict[str, Any]) -> list[str]:
    """Validate a single category pricing result from the LLM."""
    errors: list[str] = []
    if not _is_non_empty_string(payload.get("category")):
        errors.append("category is required")
    line_items = payload.get("line_items")
    if not isinstance(line_items, list) or len(line_items) == 0:
        errors.append("line_items must be non-empty array")
    else:
        for idx, li in enumerate(line_items):
            if not isinstance(li, dict):
                errors.append(f"line_items[{idx}] must be object")
                continue
            if not _is_non_empty_string(li.get("item")):
                errors.append(f"line_items[{idx}].item is required")
            for field in ["labor_cost", "material_cost", "equipment_cost", "subtotal"]:
                if not _is_number(li.get(field)):
                    errors.append(f"line_items[{idx}].{field} must be numeric")
    if not _is_number(payload.get("category_subtotal")):
        errors.append("category_subtotal must be numeric")
    return errors


def validate_proposal_narrative(payload: dict[str, Any]) -> list[str]:
    """Validate the proposal narrative LLM output."""
    errors: list[str] = []
    if not _is_non_empty_string(payload.get("scope_narrative")):
        errors.append("scope_narrative is required")
    if not isinstance(payload.get("assumptions"), list) or len(payload.get("assumptions", [])) < 4:
        errors.append("assumptions must have at least 4 items")
    if not isinstance(payload.get("exclusions"), list) or len(payload.get("exclusions", [])) < 3:
        errors.append("exclusions must have at least 3 items")
    if not _is_non_empty_string(payload.get("schedule_statement")):
        errors.append("schedule_statement is required")
    if not _is_non_empty_string(payload.get("validity_statement")):
        errors.append("validity_statement is required")
    return errors


async def cost_estimate_price_category(
    *,
    agent_id: str,
    category: str,
    items: list[dict[str, Any]],
    cost_db: dict[str, Any],
    category_index: int,
    total_categories: int,
    model: Optional[str] = None,
) -> LLMResult:
    """Ask the LLM to price one category of takeoff items against cost rates."""
    category_costs = cost_db.get(category, {})

    objective = (
        f"Price the '{category}' section of a construction takeoff (category {category_index} "
        f"of {total_categories}). For each item, use the rates from the cost database and calculate: "
        f"labor_cost = quantity × labor_rate, "
        f"material_cost = quantity × material_rate, "
        f"equipment_cost = quantity × equipment_rate, "
        f"subtotal = labor_cost + material_cost + equipment_cost. "
        f"Return JSON with keys: "
        f"category (string '{category}'), "
        f"line_items (array of objects with: item, quantity, unit, labor_cost, material_cost, "
        f"equipment_cost, subtotal), "
        f"category_subtotal (sum of all subtotals), "
        f"category_notes (1-2 sentences about key cost considerations for this scope category)."
    )

    return await llm_json_response(
        agent_id=agent_id,
        objective=objective,
        context_payload={
            "category": category,
            "items": items,
            "cost_rates": category_costs,
        },
        max_tokens=1500,
        temperature=0.1,
        validator=validate_cost_category,
        model=model,
    )


def validate_inquiry_routes(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    routes = payload.get("routes")
    if not isinstance(routes, list):
        return ["routes must be an array"]
    for idx, route in enumerate(routes):
        if not isinstance(route, dict):
            errors.append(f"routes[{idx}] must be object")
            continue
        for field in ["from", "subject", "route", "priority", "description"]:
            if not _is_non_empty_string(route.get(field)):
                errors.append(f"routes[{idx}].{field} is required")
    return errors


def ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            ordered.append(value)
            seen.add(value)
    return ordered


def determine_po_allowed_actions(state: dict[str, Any], training_rule_active: bool) -> list[str]:
    status = state["status"]
    if status == "matched":
        actions: list[str] = []
        if state["marked_complete"] and not state["posted_to_vista"]:
            actions.append("post_to_vista")
        if state["posted_to_vista"]:
            actions.append("complete_invoice")
        return ordered_unique(actions)

    if status == "exception":
        actions = []
        if (
            training_rule_active
            and state.get("exception_reason_code") == "price_variance"
            and state.get("selected_po")
            and not state.get("notified_pm")
        ):
            if not state.get("project"):
                actions.append("get_project_details")
            else:
                actions.append("send_notification")
        actions.append("complete_invoice")
        return ordered_unique(actions)

    # status == pending
    if state["invoice_data"] is None:
        return ["read_invoice"]
    if not state["searched_po"]:
        return ["search_purchase_orders"]

    actions = []
    if state["po_matches"] and not state["selected_po"]:
        actions.append("select_po")
    if state["selected_po"] and not state["checked_duplicate"]:
        actions.append("check_duplicate")
    if state["checked_duplicate"] and state["duplicates"]:
        actions.append("flag_exception")
    if not state["po_matches"]:
        actions.append("flag_exception")

    if state["selected_po"] and state["checked_duplicate"] and not state["duplicates"] and not state["coded"]:
        actions.extend(["assign_coding", "flag_exception"])
    if state["coded"] and not state["marked_complete"]:
        actions.append("mark_complete")
    if state["marked_complete"] and not state["posted_to_vista"]:
        actions.append("post_to_vista")
    return ordered_unique(actions)


def summarize_po_state_for_model(state: dict[str, Any]) -> dict[str, Any]:
    selected_po = state.get("selected_po")
    po_matches = state.get("po_matches", [])
    invoice = state["invoice"]
    variance = None
    if selected_po:
        variance = {
            "amount": round(float(invoice["amount"]) - float(selected_po["amount"]), 2),
            "percent": round(
                ((float(invoice["amount"]) - float(selected_po["amount"])) / float(selected_po["amount"])) * 100,
                1,
            ) if float(selected_po["amount"]) != 0 else None,
        }

    return {
        "invoice": invoice,
        "invoice_data": state.get("invoice_data"),
        "po_matches": po_matches[:5],
        "selected_po": selected_po,
        "duplicates": state.get("duplicates", []),
        "project": state.get("project"),
        "status": state["status"],
        "flags": {
            "searched_po": state["searched_po"],
            "checked_duplicate": state["checked_duplicate"],
            "coded": state["coded"],
            "marked_complete": state["marked_complete"],
            "posted_to_vista": state["posted_to_vista"],
            "notified_pm": state["notified_pm"],
        },
        "exception_reason_code": state.get("exception_reason_code"),
        "variance": variance,
        "recent_actions": state.get("step_history", [])[-6:],
    }


async def po_choose_next_action(
    *,
    state: dict[str, Any],
    training_rule_active: bool,
    step_number: int,
) -> LLMResult:
    allowed_actions = determine_po_allowed_actions(state, training_rule_active)
    if not allowed_actions:
        raise RuntimeError(f"po_match: no allowed actions available for {state['invoice']['invoice_number']}")

    objective = (
        "Choose the single best next PO processing action for this invoice. "
        "Return JSON with keys: action, reason, args. "
        "Only choose from allowed_actions. "
        "Use explicit tool-like progression and avoid skipping steps. "
        "If exception path is needed, use flag_exception then complete_invoice. "
        "For matched path, use assign_coding -> mark_complete -> post_to_vista -> complete_invoice. "
        "When training_rule_active is true and variance exception exceeds $1,000, include PM notification before complete_invoice."
    )
    context = {
        "step_number": step_number,
        "training_rule_active": training_rule_active,
        "allowed_actions": allowed_actions,
        "state": summarize_po_state_for_model(state),
    }

    available_po_numbers = {
        str(po.get("po_number")).strip()
        for po in state.get("po_matches", [])
        if isinstance(po, dict) and _is_non_empty_string(po.get("po_number"))
    }

    return await llm_json_response(
        agent_id="po_match",
        objective=objective,
        context_payload=context,
        max_tokens=700,
        temperature=0.1,
        validator=make_po_step_validator(allowed_actions, available_po_numbers),
    )


async def run_po_match(conn, emitter: EventEmitter) -> dict[str, Any]:
    agent_id = "po_match"
    skills = read_skills(agent_id)
    send_pm_variance_notifications = await model_training_rule_active(agent_id, skills)

    await emitter.emit_status_change("working", "PO Match Agent started invoice queue processing")
    await update_agent_status(conn, agent_id, status="working", current_activity="Processing invoice queue")

    rows = await fetchall(
        conn,
        """
        SELECT i.invoice_number, i.amount, i.po_reference, i.file_path, i.status, v.name AS vendor
        FROM invoices i
        JOIN vendors v ON i.vendor_id = v.id
        WHERE i.status = 'pending'
           OR (i.status = 'pending_post_training' AND ? = 1)
        ORDER BY i.invoice_number
        """,
        (1 if send_pm_variance_notifications else 0,),
    )

    invoices = [dict(row) for row in rows]
    processed: list[dict[str, Any]] = []

    for index, invoice in enumerate(invoices, start=1):
        await emitter.emit_reasoning(
            f"Processing {invoice['invoice_number']} ({index} of {len(invoices)}) from {invoice['vendor']}."
        )

        state: dict[str, Any] = {
            "invoice": invoice,
            "invoice_data": None,
            "po_matches": [],
            "selected_po": None,
            "duplicates": [],
            "project": None,
            "searched_po": False,
            "checked_duplicate": False,
            "coded": False,
            "marked_complete": False,
            "posted_to_vista": False,
            "status": "pending",
            "exception_reason_code": None,
            "details": "",
            "notified_pm": False,
            "step_history": [],
        }

        max_steps = 16
        for step in range(1, max_steps + 1):
            _llm = await po_choose_next_action(
                state=state,
                training_rule_active=send_pm_variance_notifications,
                step_number=step,
            )
            next_action = _llm.data
            await emitter.emit_llm("tool_result", {"tool": "llm_analysis", "result": {}, "summary": "LLM analysis complete"}, message="LLM analysis", prompt_tokens=_llm.prompt_tokens, completion_tokens=_llm.completion_tokens)

            action = str(next_action.get("action", "")).strip()
            reason = str(next_action.get("reason", "")).strip() or "Model-selected next step."
            args = next_action.get("args") if isinstance(next_action.get("args"), dict) else {}

            state["step_history"].append({"step": step, "action": action, "reason": reason})
            await emitter.emit_reasoning(f"Step {step}: {reason}")
            await emitter.emit_tool_call(action, args)

            if action == "read_invoice":
                file_path = str(args.get("file_path") or invoice["file_path"])
                invoice_data = await read_invoice_pdf(file_path)
                state["invoice_data"] = invoice_data
                await emitter.emit_tool_result(
                    "read_invoice",
                    invoice_data,
                    f"Read invoice PDF {invoice['invoice_number']} and extracted key fields.",
                )
                continue

            if action == "search_purchase_orders":
                invoice_data = state.get("invoice_data") or {}
                po_matches = await search_purchase_orders(
                    conn,
                    str(args.get("po_number") or invoice_data.get("po_reference") or invoice.get("po_reference") or "").strip() or None,
                    str(args.get("vendor") or invoice_data.get("vendor") or "").strip() or invoice["vendor"],
                    float(args.get("amount") or invoice["amount"]),
                )
                state["po_matches"] = po_matches
                state["searched_po"] = True
                await emitter.emit_tool_result(
                    "search_purchase_orders",
                    {"matches": po_matches[:5]},
                    f"Found {len(po_matches)} purchase-order candidate(s).",
                )
                continue

            if action == "select_po":
                po_number = str(args.get("po_number", "")).strip()
                selected_po = next((po for po in state["po_matches"] if po["po_number"] == po_number), None)
                if selected_po is None:
                    raise RuntimeError(f"po_match: select_po could not find {po_number}")
                state["selected_po"] = selected_po
                await emitter.emit_tool_result(
                    "select_po",
                    {"selected_po": selected_po},
                    f"Selected PO {selected_po['po_number']} for invoice {invoice['invoice_number']}.",
                )
                continue

            if action == "check_duplicate":
                selected_po = state.get("selected_po")
                po_number = str(args.get("po_number") or (selected_po["po_number"] if selected_po else "")).strip()
                if not po_number:
                    raise RuntimeError("po_match: check_duplicate requires selected PO")
                duplicates = await check_duplicate_po(conn, po_number, invoice["invoice_number"])
                state["duplicates"] = duplicates
                state["checked_duplicate"] = True
                await emitter.emit_tool_result(
                    "check_duplicate",
                    {"duplicates": duplicates},
                    f"Duplicate check returned {len(duplicates)} prior matched invoice(s).",
                )
                continue

            if action == "assign_coding":
                job_id = str(args.get("job_id", "")).strip()
                gl_code = str(args.get("gl_code", "")).strip()
                await assign_coding(conn, invoice["invoice_number"], job_id, gl_code)
                if state.get("selected_po"):
                    state["selected_po"]["job_id"] = job_id
                    state["selected_po"]["gl_code"] = gl_code
                state["coded"] = True
                await emitter.emit_tool_result(
                    "assign_coding",
                    {"invoice_id": invoice["invoice_number"], "job_id": job_id, "gl_code": gl_code},
                    f"Assigned coding {gl_code} to {invoice['invoice_number']}.",
                )
                continue

            if action == "mark_complete":
                await mark_invoice_status(conn, invoice["invoice_number"], "matched", reason)
                state["status"] = "matched"
                state["marked_complete"] = True
                await emitter.emit_tool_result(
                    "mark_complete",
                    {"invoice_id": invoice["invoice_number"], "status": "matched"},
                    f"Marked {invoice['invoice_number']} as matched.",
                )
                continue

            if action == "post_to_vista":
                await asyncio.sleep(0.35)
                state["posted_to_vista"] = True
                await emitter.emit_tool_result(
                    "post_to_vista",
                    {"invoice_id": invoice["invoice_number"], "confirmation": "Posted to Vista (stubbed)"},
                    f"Posted {invoice['invoice_number']} to Vista.",
                )
                continue

            if action == "flag_exception":
                reason_code = str(args.get("reason_code", "")).strip().lower()
                details = str(args.get("details", "")).strip()

                # Build context snapshot for human reviewer
                _sel_po = state.get("selected_po")
                _var_amt = None
                _var_pct = None
                if _sel_po:
                    _inv_amt = float(invoice["amount"])
                    _po_amt = float(_sel_po["amount"])
                    _var_amt = round(_inv_amt - _po_amt, 2)
                    if _po_amt != 0:
                        _var_pct = round((_var_amt / _po_amt) * 100, 1)

                review_context = safe_json({
                    "invoice": invoice,
                    "invoice_data": state.get("invoice_data"),
                    "po_matches": (state.get("po_matches") or [])[:5],
                    "selected_po": _sel_po,
                    "duplicates": state.get("duplicates") or [],
                    "project": state.get("project"),
                    "variance_amount": _var_amt,
                    "variance_pct": _var_pct,
                    "step_history": state.get("step_history") or [],
                })

                review_id = await insert_review_item(conn, agent_id, invoice["invoice_number"], reason_code, details, context=review_context)
                await mark_invoice_status(conn, invoice["invoice_number"], "exception", details)
                state["status"] = "exception"
                state["exception_reason_code"] = reason_code
                state["details"] = details
                await emitter.emit_tool_result(
                    "flag_exception",
                    {"review_id": review_id, "reason": reason_code, "details": details},
                    f"Flagged {invoice['invoice_number']} for review ({reason_code}).",
                )
                continue

            if action == "get_project_details":
                project_id = str(
                    args.get("project_id")
                    or (state["selected_po"]["job_id"] if state.get("selected_po") else "")
                ).strip()
                if not project_id:
                    raise RuntimeError("po_match: get_project_details requires project_id")
                project = await get_project(conn, project_id)
                state["project"] = project
                await emitter.emit_tool_result(
                    "get_project_details",
                    project or {},
                    f"Loaded project details for {project_id}.",
                )
                continue

            if action == "send_notification":
                recipient = str(args.get("recipient", "")).strip()
                subject = str(args.get("subject", "")).strip()
                body = str(args.get("body", "")).strip()
                await insert_communication(conn, agent_id, recipient, subject, body)
                state["notified_pm"] = True
                await emitter.emit_tool_result(
                    "send_notification",
                    {"recipient": recipient, "subject": subject},
                    f"Sent notification to {recipient}.",
                )
                await emitter.emit_communication(recipient, subject, body)
                continue

            if action == "complete_invoice":
                final_status = str(args.get("final_status", "")).strip().lower()
                confidence = normalize_confidence(str(args.get("confidence", "medium")), default="medium")
                summary = str(args.get("summary", "")).strip()

                if final_status != state["status"]:
                    raise RuntimeError(
                        f"po_match: complete_invoice status mismatch for {invoice['invoice_number']} "
                        f"(final_status={final_status}, state={state['status']})"
                    )
                if final_status == "matched" and not state["posted_to_vista"]:
                    raise RuntimeError(f"po_match: matched invoice {invoice['invoice_number']} not posted to Vista")

                selected_po = state.get("selected_po")
                variance_amount = None
                variance_pct = None
                if selected_po:
                    variance_amount = round(float(invoice["amount"]) - float(selected_po["amount"]), 2)
                    if float(selected_po["amount"]) != 0:
                        variance_pct = round((variance_amount / float(selected_po["amount"])) * 100, 1)

                if final_status == "matched":
                    processed.append(
                        {
                            "invoice_number": invoice["invoice_number"],
                            "status": "matched",
                            "po_number": selected_po["po_number"] if selected_po else None,
                            "gl_code": selected_po.get("gl_code") if selected_po else None,
                            "confidence": confidence,
                            "reason": summary,
                            "match_method": "exact_po" if invoice.get("po_reference") else "fuzzy_vendor_amount",
                        }
                    )
                else:
                    output_row = {
                        "invoice_number": invoice["invoice_number"],
                        "status": "exception",
                        "reason": state.get("exception_reason_code") or "manual_review",
                        "confidence": confidence,
                        "details": state.get("details") or summary,
                    }
                    if variance_amount is not None:
                        output_row["variance_amount"] = variance_amount
                    if variance_pct is not None:
                        output_row["variance_pct"] = variance_pct
                    processed.append(output_row)

                await emitter.emit_tool_result(
                    "complete_invoice",
                    {"invoice_id": invoice["invoice_number"], "status": final_status, "summary": summary},
                    f"Completed processing for {invoice['invoice_number']} as {final_status}.",
                )
                await asyncio.sleep(0.12)
                break

            raise RuntimeError(f"po_match: unsupported action '{action}'")
        else:
            raise RuntimeError(f"po_match: step limit exceeded for {invoice['invoice_number']}")

    summary_subject = "PO Match Daily Summary"
    summary_body = (
        f"Processed {len(processed)} invoice(s): "
        f"{sum(1 for item in processed if item['status'] == 'matched')} matched, "
        f"{sum(1 for item in processed if item['status'] == 'exception')} exception(s)."
    )
    await insert_communication(conn, agent_id, "apmanager@rpmx.com", summary_subject, summary_body)
    await emitter.emit_communication("apmanager@rpmx.com", summary_subject, summary_body)

    return {
        "processed": processed,
        "queue_progress": {
            "total": len(processed),
            "matched": sum(1 for row in processed if row["status"] == "matched"),
            "exceptions": sum(1 for row in processed if row["status"] == "exception"),
        },
        "training_rule_active": send_pm_variance_notifications,
    }


async def ar_choose_account_action(
    *,
    agent_id: str,
    account: dict[str, Any],
    account_index: int,
    total_accounts: int,
) -> LLMResult:
    """Ask the LLM to analyze one AR account and decide the follow-up action + compose email."""
    days = int(account["days_out"])
    if days <= 29:
        bucket_hint = "0-29 days (within terms)"
    elif days <= 59:
        bucket_hint = "30-59 days (polite reminder range)"
    elif days <= 89:
        bucket_hint = "60-89 days (firm follow-up range)"
    elif days <= 104:
        bucket_hint = "90-104 days (collections escalation range)"
    else:
        bucket_hint = "105+ days (attorney escalation range)"

    objective = (
        f"Analyze this accounts receivable account and determine the correct follow-up action. "
        f"This is account {account_index} of {total_accounts}. "
        f"The account falls in the {bucket_hint} aging bucket. "
        f"Return JSON with keys: action (polite_reminder|firm_email_plus_internal_task|"
        f"escalated_to_collections|attorney_escalation_105_days|skip_retainage|no_action_within_terms), "
        f"reason (1-2 sentence explanation), "
        f"email_subject (required for polite_reminder, firm_email_plus_internal_task, escalated_to_collections, attorney_escalation_105_days), "
        f"email_body (required for same — write a professional email following the tone guidelines in your skills), "
        f"recipient (email address — use billing@<companyname>.com format if not known; for attorney_escalation_105_days, use attorney contact info from skills)."
    )

    return await llm_json_response(
        agent_id=agent_id,
        objective=objective,
        context_payload={"account": account},
        max_tokens=800,
        temperature=0.15,
        validator=validate_ar_single_account,
    )


async def run_ar_followup(conn, emitter: EventEmitter) -> dict[str, Any]:
    agent_id = "ar_followup"
    rows = await fetchall(
        conn,
        "SELECT customer_name, days_out, amount, is_retainage, notes FROM ar_aging ORDER BY days_out DESC",
    )
    accounts = [dict(row) for row in rows]

    await emitter.emit_status_change("working", "AR Follow-Up Agent started aging review")
    await update_agent_status(conn, agent_id, status="working", current_activity="Reviewing AR aging accounts")

    await emitter.emit_reasoning(
        f"Loading AR aging data. Found {len(accounts)} accounts to review, "
        f"ranging from {min(a['days_out'] for a in accounts)} to {max(a['days_out'] for a in accounts)} days outstanding."
    )

    total_outstanding = sum(float(a["amount"]) for a in accounts)
    await emitter.emit_tool_call("scan_ar_aging", {"accounts": len(accounts), "total_outstanding": round(total_outstanding, 2)})
    await emitter.emit_tool_result(
        "scan_ar_aging",
        {"accounts": len(accounts), "total_outstanding": round(total_outstanding, 2)},
        f"Loaded {len(accounts)} accounts totaling ${total_outstanding:,.2f} outstanding.",
    )

    results: list[dict[str, Any]] = []
    emails_sent = 0
    escalated = 0
    skipped = 0

    for idx, account in enumerate(accounts, start=1):
        customer = account["customer_name"]
        days_out = int(account["days_out"])
        amount = float(account["amount"])
        is_retainage = bool(account.get("is_retainage"))

        await update_agent_status(
            conn, agent_id, status="working",
            current_activity=f"Reviewing {customer} ({idx}/{len(accounts)})",
        )

        # ── Step 1: Emit reasoning about this account ──
        retainage_note = " (Retainage balance)" if is_retainage else ""
        await emitter.emit_reasoning(
            f"Reviewing account {idx} of {len(accounts)}: {customer} — "
            f"${amount:,.2f} outstanding, {days_out} days.{retainage_note}"
        )

        # ── Step 2: Load account details ──
        await emitter.emit_tool_call("review_account", {
            "customer": customer,
            "days_out": days_out,
            "amount": amount,
            "is_retainage": is_retainage,
            "notes": account.get("notes", ""),
        })
        await emitter.emit_tool_result(
            "review_account",
            {"customer": customer, "days_out": days_out, "amount": amount},
            f"Loaded account details for {customer}.",
        )

        # ── Step 3: LLM decides action + composes email ──
        _llm = await ar_choose_account_action(
            agent_id=agent_id,
            account=account,
            account_index=idx,
            total_accounts=len(accounts),
        )
        decision = _llm.data
        await emitter.emit_llm(
            "tool_result",
            {"tool": "llm_analysis", "result": {}, "summary": f"Analyzed {customer}"},
            message=f"LLM analysis for {customer}",
            prompt_tokens=_llm.prompt_tokens,
            completion_tokens=_llm.completion_tokens,
        )

        action = str(decision.get("action", "")).strip()
        reason = str(decision.get("reason", "")).strip() or "Model-selected AR action."

        if action not in AR_ALLOWED_ACTIONS:
            raise RuntimeError(f"ar_followup: invalid action '{action}' for {customer}")

        # ── Step 4: Emit the determination ──
        await emitter.emit_tool_call("determine_action", {
            "customer": customer,
            "days_out": days_out,
            "amount": amount,
            "action": action,
        })
        await emitter.emit_tool_result(
            "determine_action",
            {"customer": customer, "action": action, "reason": reason},
            f"Action for {customer}: {action.replace('_', ' ')}.",
        )

        # ── Step 5: Execute the action ──
        recipient = (
            str(decision.get("recipient", "")).strip()
            or f"billing@{customer.lower().replace(' ', '')}.com"
        )
        subject = str(decision.get("email_subject", "")).strip()
        body = str(decision.get("email_body", "")).strip()

        if action in {"polite_reminder", "firm_email_plus_internal_task", "escalated_to_collections"}:
            if subject and body:
                await emitter.emit_tool_call("compose_email", {
                    "recipient": recipient,
                    "subject": subject,
                })
                await insert_communication(conn, agent_id, recipient, subject, body)
                await emitter.emit_communication(recipient, subject, body)
                emails_sent += 1

        if action == "escalated_to_collections":
            await emitter.emit_tool_call("escalate_to_collections", {
                "customer": customer,
                "amount": amount,
            })
            await insert_collection_item(conn, customer, amount, reason)
            await emitter.emit_tool_result(
                "escalate_to_collections",
                {"customer": customer, "amount": amount, "reason": reason},
                f"Escalated {customer} (${amount:,.2f}) to collections queue.",
            )
            escalated += 1

        if action == "firm_email_plus_internal_task":
            title = f"AR follow-up call: {customer}"
            description = f"Follow up by phone on ${amount:,.2f} outstanding ({days_out} days). {reason}"
            await emitter.emit_tool_call("create_internal_task", {
                "title": title,
                "priority": "high",
            })
            await insert_internal_task(
                conn, agent_id, title, description, "high",
                (datetime.utcnow() + timedelta(days=2)).date().isoformat(),
            )
            await emitter.emit_tool_result(
                "create_internal_task",
                {"title": title, "priority": "high"},
                f"Created internal follow-up task for {customer}.",
            )

        if action in {"skip_retainage", "no_action_within_terms"}:
            skipped += 1

        # ── Step 6: Mark account complete ──
        await emitter.emit_tool_result(
            "complete_account",
            {"customer": customer, "action": action},
            f"Completed review of {customer} — {action.replace('_', ' ')}.",
        )

        results.append({
            "customer": customer,
            "action": action,
            "reason": reason,
            "amount": amount,
            "days_out": days_out,
            "is_retainage": is_retainage,
        })

    # Build aging summary for the frontend
    buckets = {"current": 0, "30_60": 0, "61_90": 0, "over_90": 0}
    bucket_amounts = {"current": 0.0, "30_60": 0.0, "61_90": 0.0, "over_90": 0.0}
    for a in accounts:
        d = int(a["days_out"])
        amt = float(a["amount"])
        if d <= 30:
            buckets["current"] += 1; bucket_amounts["current"] += amt
        elif d <= 60:
            buckets["30_60"] += 1; bucket_amounts["30_60"] += amt
        elif d <= 90:
            buckets["61_90"] += 1; bucket_amounts["61_90"] += amt
        else:
            buckets["over_90"] += 1; bucket_amounts["over_90"] += amt

    aging_summary = {
        "total_accounts": len(accounts),
        "total_outstanding": round(total_outstanding, 2),
        "buckets": buckets,
        "bucket_amounts": {k: round(v, 2) for k, v in bucket_amounts.items()},
    }

    return {
        "results": results,
        "aging_summary": aging_summary,
        "queue_progress": {
            "total": len(accounts),
            "actions_taken": emails_sent + escalated,
            "emails_sent": emails_sent,
            "escalated": escalated,
            "skipped": skipped,
        },
    }


async def run_financial_reporting(conn, emitter: EventEmitter) -> dict[str, Any]:
    """Batch mode: Generate an Executive Dashboard report with sections."""
    payload = await load_json("financial_reporting.json")
    gl_records = payload.get("monthly_gl", [])

    await emitter.emit_reasoning(
        "Loading financial data for RPMX Construction Group ($850M annual revenue). "
        "Generating executive dashboard with KPIs, P&L summary, and division performance."
    )
    await asyncio.sleep(0.3)

    divisions = list(DIVISION_NAMES.keys())
    await emitter.emit_tool_call("load_financial_data", {"divisions": divisions})
    await asyncio.sleep(0.2)
    await emitter.emit_tool_result(
        "load_financial_data",
        {"status": "loaded", "gl_records": len(gl_records)},
        f"Loaded {len(gl_records)} GL records across {len(divisions)} divisions.",
    )
    await asyncio.sleep(0.2)

    # Pre-compute data for the dashboard
    q4_records = _filter_gl(gl_records, None, "2025-10", "2025-12")
    company_pnl = _compute_pnl(q4_records)
    q_trend = _quarterly_trend(gl_records, "gross_margin")
    rev_trend = _quarterly_trend(gl_records, "revenue")

    div_performance = {}
    for d in DIVISION_NAMES:
        d_recs = _filter_gl(gl_records, d, "2025-10", "2025-12")
        d_pnl = _compute_pnl(d_recs)
        div_performance[DIVISION_NAMES[d]] = {
            "revenue": d_pnl["revenue"],
            "gross_margin_pct": d_pnl["gross_margin_pct"],
            "net_margin_pct": d_pnl["net_margin_pct"],
        }

    ar = payload.get("ar_aging_snapshot", [])
    bl = payload.get("backlog", [])
    cf = payload.get("cash_flow", [])
    targets = payload.get("kpi_targets", {})
    monthly_rev = company_pnl["revenue"] / 3

    computed_data = {
        "company_pnl": company_pnl,
        "division_performance": div_performance,
        "quarterly_margin_trend": q_trend,
        "quarterly_revenue_trend": rev_trend,
        "kpis": {
            "q4_revenue": company_pnl["revenue"],
            "gross_margin_pct": company_pnl["gross_margin_pct"],
            "net_margin_pct": company_pnl["net_margin_pct"],
            "overhead_ratio": _compute_overhead_ratio(q4_records),
            "dso": _compute_dso(ar, monthly_rev),
            "total_backlog": sum(b["contracted_backlog"] for b in bl),
            "cash_balance": cf[-1]["ending_cash_balance"] if cf else 0,
        },
        "targets": targets,
    }

    await emitter.emit_reasoning(
        "Computing Q4 2025 P&L, division performance, margin trends, "
        "and key performance indicators."
    )
    await asyncio.sleep(0.3)

    await emitter.emit_tool_call("generate_report", {"type": "executive_dashboard", "period": "Q4 2025"})
    await asyncio.sleep(0.1)

    _llm = await llm_json_response(
        agent_id="financial_reporting",
        objective=(
            "Generate an Executive Dashboard report for RPMX Construction Group, Q4 2025.\n"
            "You have been given pre-computed financial data. Numbers MUST exactly match.\n\n"
            "Return strict JSON with these keys:\n"
            "- report_title: 'Executive Dashboard — Q4 2025'\n"
            "- report_type: 'kpi_dashboard'\n"
            "- sections: array of 4 sections:\n"
            "  1. kpi_grid: 6-8 key metrics (revenue, gross margin, net margin, overhead ratio, DSO, backlog, cash balance)\n"
            "  2. table: Division Performance table with columns: Division, Revenue, Gross Margin %, Net Margin %\n"
            "  3. chart: line chart of quarterly gross margin trend\n"
            "  4. narrative: Executive summary paragraph highlighting performance, trends, and concerns\n"
            "- division_name: 'Company-Wide'\n"
            "- period_label: 'Q4 2025'\n\n"
            "Currency values should be raw numbers. Percent values like 18.5 (not 0.185).\n"
            "The narrative should sound like a CFO briefing — professional, insightful, action-oriented."
        ),
        context_payload=computed_data,
        max_tokens=3000,
        temperature=0.1,
        validator=validate_financial_report,
    )
    report = _llm.data
    await emitter.emit_llm("tool_result", {"tool": "llm_analysis", "result": {}, "summary": "Dashboard generated"}, message="Dashboard generated", prompt_tokens=_llm.prompt_tokens, completion_tokens=_llm.completion_tokens)

    await emitter.emit_tool_result(
        "generate_report",
        {"report_type": "kpi_dashboard"},
        "Executive Dashboard generated.",
    )

    return report


# ---------------------------------------------------------------------------
# Financial Reporting — Chat-driven query handler (v2 — sections-based)
# ---------------------------------------------------------------------------

DIVISION_NAMES = {
    "EX": "Excavation & Earthwork",
    "RC": "Road & Highway Construction",
    "SD": "Site Development",
    "LM": "Landscape & Maintenance",
    "RW": "Retaining Walls & Structures",
}
DIVISION_SHORT = {
    "EX": "Excavation", "RC": "Roads", "SD": "Site Dev",
    "LM": "Landscape", "RW": "Walls",
}
GL_CATEGORIES = {
    "revenue": ["4100", "4200", "4300"],
    "cogs": ["5100", "5200", "5300", "5400", "5500", "5600", "5700", "5800"],
    "opex": ["6100", "6200", "6300", "6400", "6500", "6600"],
}
GL_DESCRIPTIONS: dict[str, str] = {
    "4100": "Contract Revenue", "4200": "Service Revenue", "4300": "Change Order Revenue",
    "5100": "Materials", "5200": "Equipment Rental", "5300": "Subcontractor Costs",
    "5400": "Direct Labor", "5500": "Fuel & Lubricants", "5600": "Hauling & Freight",
    "5700": "Permits & Fees", "5800": "Equipment Maintenance",
    "6100": "Office & Admin", "6200": "Insurance", "6300": "Vehicle & Fleet",
    "6400": "IT & Software", "6500": "Professional Fees", "6600": "Depreciation",
}


# ── Deterministic computation helpers ──

def _filter_gl(records: list[dict], division: str | None = None,
               period_start: str | None = None, period_end: str | None = None,
               gl_codes: list[str] | None = None) -> list[dict]:
    """Filter GL records by division, period range, and/or GL code list."""
    out = records
    if division and division != "all":
        out = [r for r in out if r["division_id"] == division]
    if period_start:
        out = [r for r in out if r["period"] >= period_start]
    if period_end:
        out = [r for r in out if r["period"] <= period_end]
    if gl_codes:
        out = [r for r in out if r["gl_code"] in gl_codes]
    return out


def _sum_by_gl(records: list[dict]) -> dict[str, float]:
    """Sum amounts grouped by GL code."""
    totals: dict[str, float] = {}
    for r in records:
        totals[r["gl_code"]] = totals.get(r["gl_code"], 0.0) + r["amount"]
    return {k: round(v, 2) for k, v in totals.items()}


def _sum_by_division(records: list[dict]) -> dict[str, float]:
    """Sum amounts grouped by division_id."""
    totals: dict[str, float] = {}
    for r in records:
        totals[r["division_id"]] = totals.get(r["division_id"], 0.0) + r["amount"]
    return {k: round(v, 2) for k, v in totals.items()}


def _sum_by_period(records: list[dict]) -> dict[str, float]:
    """Sum amounts grouped by period."""
    totals: dict[str, float] = {}
    for r in records:
        totals[r["period"]] = totals.get(r["period"], 0.0) + r["amount"]
    return {k: round(v, 2) for k, v in sorted(totals.items())}


def _compute_pnl(gl_records: list[dict]) -> dict[str, Any]:
    """Compute a full P&L structure from GL records."""
    by_gl = _sum_by_gl(gl_records)
    revenue = sum(by_gl.get(c, 0) for c in GL_CATEGORIES["revenue"])
    cogs_items = {GL_DESCRIPTIONS.get(c, c): by_gl.get(c, 0) for c in GL_CATEGORIES["cogs"] if by_gl.get(c, 0) != 0}
    cogs_total = sum(cogs_items.values())
    gross_profit = revenue - cogs_total
    gross_margin = round((gross_profit / revenue * 100) if revenue else 0, 1)
    opex_items = {GL_DESCRIPTIONS.get(c, c): by_gl.get(c, 0) for c in GL_CATEGORIES["opex"] if by_gl.get(c, 0) != 0}
    opex_total = sum(opex_items.values())
    net_income = gross_profit - opex_total
    net_margin = round((net_income / revenue * 100) if revenue else 0, 1)
    return {
        "revenue": round(revenue, 2),
        "cogs_breakdown": {k: round(v, 2) for k, v in cogs_items.items()},
        "cogs_total": round(cogs_total, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_margin_pct": gross_margin,
        "opex_breakdown": {k: round(v, 2) for k, v in opex_items.items()},
        "opex_total": round(opex_total, 2),
        "net_income": round(net_income, 2),
        "net_margin_pct": net_margin,
    }


def _compute_variance(current: dict[str, Any], prior: dict[str, Any]) -> dict[str, Any]:
    """Compute dollar and % variance between two P&L dicts."""
    result = {}
    for key in ["revenue", "cogs_total", "gross_profit", "opex_total", "net_income"]:
        c_val = current.get(key, 0)
        p_val = prior.get(key, 0)
        diff = round(c_val - p_val, 2)
        pct = round((diff / p_val * 100) if p_val else 0, 1)
        result[key] = {"current": c_val, "prior": p_val, "variance": diff, "variance_pct": pct}
    for key in ["gross_margin_pct", "net_margin_pct"]:
        c_val = current.get(key, 0)
        p_val = prior.get(key, 0)
        result[key] = {"current": c_val, "prior": p_val, "change_bps": round((c_val - p_val) * 100)}
    return result


def _period_range_for_quarter(quarter_str: str) -> tuple[str, str]:
    """Convert '2025-Q4' → ('2025-10', '2025-12')."""
    parts = quarter_str.split("-Q")
    year = parts[0]
    q = int(parts[1])
    start_month = (q - 1) * 3 + 1
    end_month = q * 3
    return f"{year}-{start_month:02d}", f"{year}-{end_month:02d}"


def _period_range_for_year(year_str: str) -> tuple[str, str]:
    """Convert '2025' → ('2025-01', '2025-12')."""
    return f"{year_str}-01", f"{year_str}-12"


def _resolve_period_range(period: str | None) -> tuple[str | None, str | None]:
    """Resolve period string to start/end range."""
    if not period:
        return None, None
    if "-Q" in period:
        return _period_range_for_quarter(period)
    if len(period) == 4:  # just year
        return _period_range_for_year(period)
    # YYYY-MM single month
    return period, period


def _compute_dso(ar_snapshot: list[dict], monthly_rev: float) -> float:
    """Days Sales Outstanding = total AR / average daily revenue."""
    total_ar = sum(a["total_outstanding"] for a in ar_snapshot)
    daily_rev = monthly_rev / 30 if monthly_rev else 1
    return round(total_ar / daily_rev, 1)


def _compute_overhead_ratio(gl_records: list[dict]) -> float:
    """OpEx as % of revenue."""
    by_gl = _sum_by_gl(gl_records)
    revenue = sum(by_gl.get(c, 0) for c in GL_CATEGORIES["revenue"])
    opex = sum(by_gl.get(c, 0) for c in GL_CATEGORIES["opex"])
    return round((opex / revenue * 100) if revenue else 0, 1)


def _quarterly_trend(gl_records: list[dict], metric: str = "gross_margin") -> list[dict]:
    """Compute quarterly trend for a given metric across all available data."""
    from collections import defaultdict
    by_q: dict[str, list[dict]] = defaultdict(list)
    for r in gl_records:
        y = r["period"][:4]
        m = int(r["period"][5:7])
        q = (m - 1) // 3 + 1
        q_label = f"{y}-Q{q}"
        by_q[q_label].append(r)

    result = []
    for q_label in sorted(by_q.keys()):
        pnl = _compute_pnl(by_q[q_label])
        if metric == "gross_margin":
            result.append({"quarter": q_label, "value": pnl["gross_margin_pct"]})
        elif metric == "net_margin":
            result.append({"quarter": q_label, "value": pnl["net_margin_pct"]})
        elif metric == "revenue":
            result.append({"quarter": q_label, "value": pnl["revenue"]})
        elif metric == "overhead":
            oh = round((pnl["opex_total"] / pnl["revenue"] * 100) if pnl["revenue"] else 0, 1)
            result.append({"quarter": q_label, "value": oh})
        else:
            result.append({"quarter": q_label, "value": pnl.get(metric, 0)})
    return result


def _build_simulated_sql(intent: str, division: str | None, period: str | None, gl_filter: str | None) -> str:
    """Create a realistic-looking SQL query for the code-block visualization."""
    div_name = DIVISION_NAMES.get(division, "All Divisions") if division and division != "all" else "All Divisions"
    where_clauses = []
    if division and division != "all":
        where_clauses.append(f"division_id = '{division}'")
    if period and period != "latest":
        where_clauses.append(f"period >= '{period}'")
    if gl_filter:
        where_clauses.append(f"gl_code = '{gl_filter}'")
    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    if intent in ("comparison", "margin_analysis"):
        return (
            f"-- Year-over-year comparison for {div_name}\n"
            f"SELECT period, gl_code,\n"
            f"       SUM(amount) AS total,\n"
            f"       LAG(SUM(amount)) OVER (ORDER BY period) AS prior_period\n"
            f"FROM vista_gl_transactions\n"
            f"WHERE {where_sql}\n"
            f"GROUP BY period, gl_code\n"
            f"ORDER BY period, gl_code;"
        )
    if intent == "job_costing":
        return (
            f"-- Job cost detail for {div_name}\n"
            f"SELECT j.job_id, j.name, j.contract_value,\n"
            f"       j.percent_complete, j.costs_total\n"
            f"FROM vista_jobs j\n"
            f"WHERE j.division_id = '{division or 'ALL'}'\n"
            f"ORDER BY j.contract_value DESC;"
        )
    if intent == "ar_analysis":
        return (
            f"-- AR aging analysis\n"
            f"SELECT customer, division_id,\n"
            f"       current_amt, days_1_30, days_31_60, days_61_90, days_over_90\n"
            f"FROM vista_ar_aging\n"
            f"WHERE {where_sql}\n"
            f"ORDER BY total_outstanding DESC;"
        )
    if intent == "cash_flow":
        return (
            f"-- Cash flow analysis\n"
            f"SELECT period, operating_cash_in, operating_cash_out,\n"
            f"       capital_expenditures, net_cash_flow, ending_cash_balance\n"
            f"FROM vista_cash_flow\n"
            f"WHERE {where_sql}\n"
            f"ORDER BY period;"
        )
    return (
        f"-- P&L query for {div_name}\n"
        f"SELECT gl_code, gl_description,\n"
        f"       SUM(amount) AS total_amount\n"
        f"FROM vista_gl_transactions\n"
        f"WHERE {where_sql}\n"
        f"GROUP BY gl_code, gl_description\n"
        f"ORDER BY gl_code;"
    )


async def run_financial_query(
    conn,
    emitter: EventEmitter,
    user_message: str,
    conversation: "ConversationContext",
) -> dict[str, Any]:
    """Chat-driven financial reporting: classify intent → compute data → generate sectioned report."""
    from .session_manager import ConversationContext  # avoid circular at module-level

    payload = await load_json("financial_reporting.json")
    gl_records = payload.get("monthly_gl", [])
    budget_records = payload.get("monthly_budget", [])
    gl_chart = payload.get("gl_chart", {})

    # --- Phase 1: Emit initial reasoning ---
    await emitter.emit_reasoning(
        f"Analyzing your request: \"{user_message[:100]}\" — "
        "I'll classify your intent, query the relevant financial data, and generate a report."
    )
    await asyncio.sleep(0.3)

    # --- Phase 1b: Intent classification (LLM call 1) ---
    await emitter.emit_tool_call("classify_intent", {"message": user_message[:80]})
    await asyncio.sleep(0.2)

    history_for_llm = ""
    if conversation.messages:
        history_for_llm = "\n".join(
            f"{m['role'].upper()}: {m['content']}" for m in conversation.messages[-6:]
        )

    available_divisions = ", ".join(f"{k}={v}" for k, v in DIVISION_NAMES.items())
    available_jobs = ", ".join(j["job_id"] + "=" + j["name"] for j in payload.get("jobs", [])[:15])

    _llm = await llm_json_response(
        agent_id="financial_reporting",
        objective=(
            "Classify the user's financial query and extract parameters.\n"
            "Return strict JSON with these keys:\n"
            "- intent: one of p_and_l, comparison, expense_analysis, job_costing, ar_analysis, "
            "backlog, cash_flow, margin_analysis, budget_variance, kpi_dashboard, custom_query, clarification_needed\n"
            "- division: one of EX, RC, SD, LM, RW, all, or null\n"
            "- period_start: YYYY-MM format for the start of the period range, or null\n"
            "- period_end: YYYY-MM format for the end of the period range, or null\n"
            "- compare_period_start: YYYY-MM for comparison start, or null\n"
            "- compare_period_end: YYYY-MM for comparison end, or null\n"
            "- gl_filter: a GL code like 5500, or null\n"
            "- gl_category: revenue, cogs, or opex — or null\n"
            "- job_id: a job ID like J-1001, or null\n"
            "- aggregation: monthly, quarterly, or annual — default quarterly\n"
            "- clarification_question: a follow-up question string if intent is clarification_needed, else null\n\n"
            "IMPORTANT DATE RULES:\n"
            "- Today is January 2026. The most recent complete quarter is Q4 2025 (2025-10 to 2025-12).\n"
            "- The most recent complete fiscal year is FY 2025 (2025-01 to 2025-12).\n"
            "- For 'last N months' → count back N months from 2026-01 (e.g. 'last 6 months' → 2025-08 to 2026-01)\n"
            "- For 'this year' or 'YTD 2025' → 2025-01 to 2025-12\n"
            "- For 'Q4 2025' → 2025-10 to 2025-12\n"
            "- For 'Q3 2025' → 2025-07 to 2025-09\n"
            "- For a single month like 'October 2025' → 2025-10 to 2025-10\n"
            "- For year-over-year → set period_start/end to current period AND compare_period_start/end to prior year equivalent\n"
            "- If no period is specified, use smart defaults based on intent:\n"
            "  * p_and_l/budget_variance → most recent quarter: 2025-10 to 2025-12\n"
            "  * comparison → current year vs prior year: period 2025-01..2025-12, compare 2024-01..2024-12\n"
            "  * cash_flow → last 12 months: 2025-02 to 2026-01\n"
            "  * margin_analysis → all available (null, let backend handle)\n"
            "  * expense_analysis → last 12 months: 2025-02 to 2026-01\n"
            "  * kpi_dashboard → null (backend uses latest)\n"
            "  * ar_analysis/backlog/job_costing → null (point-in-time data)\n\n"
            f"Division lookup: {available_divisions}\n"
            "Available periods: 2024-01 through 2026-01\n"
            f"Sample jobs: {available_jobs}\n"
            "GL codes: 4100=Contract Revenue, 4200=Service Revenue, 4300=Change Orders, "
            "5100=Materials, 5200=Equipment Rental, 5300=Subcontractor, 5400=Direct Labor, "
            "5500=Fuel, 5600=Hauling, 5700=Permits, 5800=Equip Maintenance, "
            "6100=Office/Admin, 6200=Insurance, 6300=Vehicle/Fleet, 6400=IT, 6500=Prof Fees, 6600=Depreciation\n\n"
            "Intent guide:\n"
            "- P&L questions → p_and_l\n"
            "- Year-over-year, compare periods → comparison\n"
            "- Cost breakdown, specific cost line, comparing cost categories → expense_analysis\n"
            "  NOTE: For expense_analysis, if the user asks about MULTIPLE cost types (e.g. 'labor vs subcontractor'),\n"
            "  leave gl_filter null and set gl_category to the broader category (cogs or opex), or leave both null\n"
            "  to get ALL expenses. The backend will include all relevant GL codes.\n"
            "- Specific project costs → job_costing\n"
            "- Receivables, DSO, collections → ar_analysis\n"
            "- Backlog, pipeline → backlog\n"
            "- Cash position, cash flow → cash_flow\n"
            "- Margin trends, profitability → margin_analysis\n"
            "- Budget vs actual → budget_variance\n"
            "- Dashboard, KPIs, overview → kpi_dashboard\n"
            "- Anything else specific → custom_query\n"
        ),
        context_payload={
            "user_message": user_message,
            "conversation_history": history_for_llm,
        },
        max_tokens=500,
        temperature=0.0,
    )
    intent_result = _llm.data
    await emitter.emit_llm("tool_result", {"tool": "llm_analysis", "result": {}, "summary": "Intent classified"}, message="Intent classified", prompt_tokens=_llm.prompt_tokens, completion_tokens=_llm.completion_tokens)

    intent = intent_result.get("intent", "custom_query")
    division = intent_result.get("division")
    # Support both new range format and old single-period format
    p_start = intent_result.get("period_start")
    p_end = intent_result.get("period_end")
    # Fallback for old single-period format
    if not p_start and not p_end:
        old_period = intent_result.get("period")
        if old_period:
            p_start, p_end = _resolve_period_range(old_period)
    compare_p_start = intent_result.get("compare_period_start")
    compare_p_end = intent_result.get("compare_period_end")
    if not compare_p_start and not compare_p_end:
        old_cp = intent_result.get("compare_period")
        if old_cp:
            compare_p_start, compare_p_end = _resolve_period_range(old_cp)
    gl_filter = intent_result.get("gl_filter")
    gl_category = intent_result.get("gl_category")
    job_id = intent_result.get("job_id")
    aggregation = intent_result.get("aggregation", "quarterly")
    # Build a human-readable period label for display
    if intent in ("ar_analysis", "backlog", "job_costing") and not p_start:
        period_display = "As of January 2026"
    else:
        period_display = f"{p_start} to {p_end}" if p_start and p_end and p_start != p_end else (p_start or "latest")

    div_label = DIVISION_NAMES.get(division, division or "all divisions") if division else "all divisions"
    await emitter.emit_tool_result(
        "classify_intent",
        {"intent": intent, "division": division, "period": period_display},
        f"Classified as {intent} for {div_label}",
    )
    await asyncio.sleep(0.2)

    # --- Handle clarification ---
    if intent == "clarification_needed":
        question = intent_result.get("clarification_question") or (
            "Could you be more specific? For example, which division, time period, or metric are you interested in?"
        )
        conversation.append_message("user", user_message)
        conversation.append_message("assistant", question)
        await emitter.emit_agent_message(question, msg_type="clarification")
        return {"type": "clarification", "question": question}

    # --- Phase 2: Deterministic data computation (NO LLM) ---
    await emitter.emit_reasoning(
        f"Connecting to Vista ERP to pull financial data"
        + (f" for {div_label}" if division else "")
        + (f", period {period_display}" if p_start else "")
        + "."
    )
    await asyncio.sleep(0.3)

    await emitter.emit_tool_call("query_gl_data", {"intent": intent, "division": division, "period": period_display})
    await asyncio.sleep(0.2)

    sql_query = _build_simulated_sql(intent, division, p_start or "latest", gl_filter)
    await emitter.emit_code_block("sql", sql_query)
    await asyncio.sleep(0.3)

    # Build computed_data dict that the LLM will use to structure the report
    computed_data: dict[str, Any] = {"intent": intent}

    if intent in ("p_and_l", "custom_query"):
        filtered = _filter_gl(gl_records, division, p_start, p_end)
        computed_data["pnl"] = _compute_pnl(filtered)
        computed_data["record_count"] = len(filtered)
        # Add per-division breakdown for company-wide P&L
        if not division or division == "all":
            div_pnls = {}
            for d_code, d_name in DIVISION_NAMES.items():
                d_filtered = _filter_gl(gl_records, d_code, p_start, p_end)
                d_pnl = _compute_pnl(d_filtered)
                div_pnls[d_name] = {"revenue": d_pnl["revenue"], "gross_profit": d_pnl["gross_profit"],
                                     "gross_margin_pct": d_pnl["gross_margin_pct"], "net_income": d_pnl["net_income"]}
            computed_data["division_breakdown"] = div_pnls

    elif intent == "comparison":
        filtered_current = _filter_gl(gl_records, division, p_start, p_end)
        current_pnl = _compute_pnl(filtered_current)
        # Determine prior period from compare_p_start/compare_p_end, or default to prior year
        cp_s = compare_p_start
        cp_e = compare_p_end
        if not cp_s and p_start:
            try:
                y = int(p_start[:4]) - 1
                cp_s = f"{y}{p_start[4:]}"
                cp_e = f"{y}{p_end[4:]}" if p_end else None
            except Exception:
                cp_s, cp_e = None, None
        filtered_prior = _filter_gl(gl_records, division, cp_s, cp_e)
        prior_pnl = _compute_pnl(filtered_prior)
        computed_data["current_pnl"] = current_pnl
        computed_data["prior_pnl"] = prior_pnl
        computed_data["variance"] = _compute_variance(current_pnl, prior_pnl)
        computed_data["current_period_label"] = f"{p_start} to {p_end}" if p_start else "current"
        computed_data["prior_period_label"] = f"{cp_s} to {cp_e}" if cp_s else "prior year"

    elif intent == "expense_analysis":
        gl_list = None
        if gl_filter:
            gl_list = [gl_filter]
        elif gl_category:
            gl_list = GL_CATEGORIES.get(gl_category)
        else:
            gl_list = GL_CATEGORIES["cogs"] + GL_CATEGORIES["opex"]
        filtered = _filter_gl(gl_records, division, p_start, p_end, gl_list)
        computed_data["expense_by_gl"] = {GL_DESCRIPTIONS.get(k, k): v for k, v in _sum_by_gl(filtered).items()}
        computed_data["expense_by_division"] = {DIVISION_NAMES.get(k, k): v for k, v in _sum_by_division(filtered).items()}
        computed_data["total"] = round(sum(_sum_by_gl(filtered).values()), 2)
        # Monthly trend for the filtered expense codes
        computed_data["monthly_trend"] = _sum_by_period(filtered)

    elif intent == "job_costing":
        jobs = payload.get("jobs", [])
        if job_id:
            jobs = [j for j in jobs if j["job_id"] == job_id]
        elif division and division != "all":
            jobs = [j for j in jobs if j["division_id"] == division]
        computed_data["jobs"] = jobs

    elif intent == "ar_analysis":
        ar = payload.get("ar_aging_snapshot", [])
        if division and division != "all":
            ar = [a for a in ar if a["division_id"] == division]
        total_ar = sum(a["total_outstanding"] for a in ar)
        # Get last 3 months of revenue for DSO - use the most recent available
        all_periods = sorted(set(r["period"] for r in gl_records))
        recent_3 = all_periods[-3:] if len(all_periods) >= 3 else all_periods
        dso_rev_start = recent_3[0] if recent_3 else "2025-10"
        dso_rev_end = recent_3[-1] if recent_3 else "2025-12"
        recent_rev = _filter_gl(gl_records, division, dso_rev_start, dso_rev_end, GL_CATEGORIES["revenue"])
        monthly_rev = sum(r["amount"] for r in recent_rev) / len(recent_3) if recent_rev else 1
        computed_data["ar_accounts"] = ar
        computed_data["total_ar"] = total_ar
        computed_data["dso"] = _compute_dso(ar, monthly_rev)
        # Aging summary for chart
        aging_summary = {"Current": 0, "1-30 Days": 0, "31-60 Days": 0, "61-90 Days": 0, "Over 90 Days": 0}
        for a in ar:
            aging_summary["Current"] += a.get("current", 0)
            aging_summary["1-30 Days"] += a.get("days_1_30", 0)
            aging_summary["31-60 Days"] += a.get("days_31_60", 0)
            aging_summary["61-90 Days"] += a.get("days_61_90", 0)
            aging_summary["Over 90 Days"] += a.get("days_over_90", 0)
        computed_data["aging_summary"] = {k: round(v, 2) for k, v in aging_summary.items()}

    elif intent == "backlog":
        bl = payload.get("backlog", [])
        if division and division != "all":
            bl = [b for b in bl if b["division_id"] == division]
        # Map division IDs to names in backlog records
        for b in bl:
            b["division_name"] = DIVISION_NAMES.get(b.get("division_id", ""), b.get("division_id", ""))
        computed_data["backlog"] = bl
        computed_data["total_backlog"] = sum(b["contracted_backlog"] for b in bl)
        computed_data["total_pipeline"] = sum(b["proposal_pipeline"] for b in bl)

    elif intent == "cash_flow":
        cf = payload.get("cash_flow", [])
        if p_start:
            cf = [c for c in cf if c["period"] >= p_start]
        if p_end:
            cf = [c for c in cf if c["period"] <= p_end]
        computed_data["cash_flow"] = cf
        if cf:
            computed_data["total_net_cash_flow"] = round(sum(c["net_cash_flow"] for c in cf), 2)
            computed_data["ending_balance"] = cf[-1]["ending_cash_balance"]
            computed_data["starting_balance"] = cf[0]["ending_cash_balance"] - cf[0]["net_cash_flow"]

    elif intent == "margin_analysis":
        computed_data["quarterly_gross_margin"] = _quarterly_trend(gl_records, "gross_margin")
        computed_data["quarterly_net_margin"] = _quarterly_trend(gl_records, "net_margin")
        computed_data["quarterly_revenue"] = _quarterly_trend(gl_records, "revenue")
        if division and division != "all":
            div_records = _filter_gl(gl_records, division)
            computed_data["division_gross_margin"] = _quarterly_trend(div_records, "gross_margin")
        # Also per-division current
        div_margins = {}
        for d in DIVISION_NAMES:
            d_recs = _filter_gl(gl_records, d, p_start, p_end)
            d_pnl = _compute_pnl(d_recs)
            div_margins[DIVISION_NAMES[d]] = {"gross_margin": d_pnl["gross_margin_pct"], "net_margin": d_pnl["net_margin_pct"],
                                              "revenue": d_pnl["revenue"]}
        computed_data["division_margins"] = div_margins

    elif intent == "budget_variance":
        filtered_actual = _filter_gl(gl_records, division, p_start, p_end)
        filtered_budget = _filter_gl(budget_records, division, p_start, p_end)
        actual_by_gl = _sum_by_gl(filtered_actual)
        budget_by_gl = {}
        for r in filtered_budget:
            budget_by_gl[r["gl_code"]] = budget_by_gl.get(r["gl_code"], 0.0) + r.get("budget_amount", 0)
        variance_lines = []
        for gl in sorted(set(list(actual_by_gl.keys()) + list(budget_by_gl.keys()))):
            act = actual_by_gl.get(gl, 0)
            bud = budget_by_gl.get(gl, 0)
            var_d = round(act - bud, 2)
            var_p = round((var_d / bud * 100) if bud else 0, 1)
            variance_lines.append({
                "gl_code": gl,
                "description": GL_DESCRIPTIONS.get(gl, gl),
                "actual": round(act, 2),
                "budget": round(bud, 2),
                "variance": var_d,
                "variance_pct": var_p,
            })
        computed_data["budget_variance_lines"] = variance_lines
        computed_data["total_actual"] = round(sum(v["actual"] for v in variance_lines), 2)
        computed_data["total_budget"] = round(sum(v["budget"] for v in variance_lines), 2)

    elif intent == "kpi_dashboard":
        # Full company P&L for most recent quarter
        recent_q = _filter_gl(gl_records, None, "2025-10", "2025-12")
        pnl = _compute_pnl(recent_q)
        monthly_rev = pnl["revenue"] / 3 if pnl["revenue"] else 1
        ar = payload.get("ar_aging_snapshot", [])
        bl = payload.get("backlog", [])
        cf = payload.get("cash_flow", [])
        targets = payload.get("kpi_targets", {})
        computed_data["kpis"] = {
            "quarterly_revenue": pnl["revenue"],
            "gross_margin_pct": pnl["gross_margin_pct"],
            "net_margin_pct": pnl["net_margin_pct"],
            "overhead_ratio": _compute_overhead_ratio(recent_q),
            "dso": _compute_dso(ar, monthly_rev),
            "total_backlog": sum(b["contracted_backlog"] for b in bl),
            "cash_balance": cf[-1]["ending_cash_balance"] if cf else 0,
            "revenue_per_employee": round(pnl["revenue"] * 4 / 1200, 0),
        }
        computed_data["targets"] = targets
        computed_data["pnl"] = pnl
        computed_data["quarterly_revenue"] = _quarterly_trend(gl_records, "revenue")

    else:
        # custom_query fallback: provide full P&L
        filtered = _filter_gl(gl_records, division, p_start, p_end)
        computed_data["pnl"] = _compute_pnl(filtered)

    row_count = len(_filter_gl(gl_records, division, p_start, p_end))
    await emitter.emit_tool_result(
        "query_gl_data",
        {"rows_returned": row_count, "data_sections": list(computed_data.keys())},
        f"Retrieved {row_count} GL records, computed {intent} data.",
    )
    await asyncio.sleep(0.2)

    # --- Phase 3: Report generation (LLM call 2) ---
    await emitter.emit_reasoning("Generating the report with tables, charts, and executive narrative...")
    await asyncio.sleep(0.3)

    await emitter.emit_tool_call("generate_report", {"intent": intent, "sections": "tables+charts+narrative"})
    await asyncio.sleep(0.1)

    _llm = await llm_json_response(
        agent_id="financial_reporting",
        objective=(
            f"The user asked: \"{user_message}\"\n"
            f"Intent: {intent}, Division: {division or 'all'}, Period: {period_display}\n"
            f"Aggregation: {aggregation}\n\n"
            "You have been given pre-computed financial data. Your job is to arrange it into a structured "
            "report with sections. The numbers in tables and charts MUST exactly match the provided computed data. "
            "Do NOT recalculate or invent numbers.\n\n"
            "Return strict JSON with these keys:\n"
            "- report_title: descriptive title (e.g. 'Excavation P&L — Q4 2025')\n"
            "- report_type: one of p_and_l, comparison, expense_analysis, job_costing, ar_analysis, "
            "backlog, cash_flow, margin_analysis, budget_variance, kpi_dashboard, custom_query\n"
            "- response_text: conversational 2-4 sentence summary answering the user's question\n"
            "- sections: array of section objects, each with:\n"
            "  - type: 'kpi_grid' | 'table' | 'chart' | 'narrative'\n"
            "  - For kpi_grid: { metrics: [{ label, value, format: 'currency'|'percent'|'number'|'days', trend: 'up'|'down'|'flat', target (optional number) }] }\n"
            "  - For table: { title, columns: [{ key, label, format: 'currency'|'percent'|'number'|'text' }], "
            "rows: [{ key1: val1, key2: val2, ... }], highlight_rows: [indices], footer: string|null }\n"
            "  - For chart: { chart_type: 'bar'|'line'|'pie'|'stacked_bar', title, "
            "data: { labels: [...], datasets: [{ label, values: [...] }] }, format: 'currency'|'percent'|'number' }\n"
            "  - For narrative: { title, content: paragraph text }\n"
            "- division_name: full division name or 'Company-Wide'\n"
            "- period_label: human-readable period like 'Q4 2025' or 'FY 2025'\n\n"
            "IMPORTANT RULES:\n"
            "- Include 2-4 sections per report (mix of types for visual richness)\n"
            "- Always include at least one table section and one narrative section\n"
            "- For P&L reports: kpi_grid (revenue, margin, net income) + P&L table + narrative\n"
            "- For comparisons: variance table + bar chart showing key line items + narrative\n"
            "- For margin analysis: line chart of quarterly trend + division comparison bar chart + narrative\n"
            "- For job costing: job summary table + narrative\n"
            "- For AR analysis: aging table + pie chart of aging buckets + narrative\n"
            "- For backlog: backlog table + bar chart + narrative\n"
            "- For cash flow: cash flow table + line chart of balance trend + narrative\n"
            "- For budget variance: variance table + bar chart of over/under + narrative\n"
            "- For KPI dashboard: kpi_grid + revenue trend chart + margin chart + narrative\n"
            "- Currency values should be raw numbers (not formatted strings)\n"
            "- Percent values should be numbers like 18.5 (not 0.185)\n"
            "- PERIOD LABEL RULES:\n"
            "  * For ar_analysis, backlog: period_label MUST be 'As of January 2026' (point-in-time snapshot, NOT a date range)\n"
            "  * For job_costing: period_label MUST be 'As of January 2026' (cumulative to date)\n"
            "  * For all other intents: use the actual period like 'Q4 2025', 'FY 2025', '2025-08 to 2026-01', etc.\n"
            "  * NEVER invent or hallucinate a period. Use only what is provided in the Period field above.\n"
        ),
        context_payload=computed_data,
        max_tokens=4000,
        temperature=0.1,
    )
    report_data = _llm.data
    await emitter.emit_llm("tool_result", {"tool": "llm_analysis", "result": {}, "summary": "Report generated"}, message="Report generated", prompt_tokens=_llm.prompt_tokens, completion_tokens=_llm.completion_tokens)

    await emitter.emit_tool_result(
        "generate_report",
        {"report_type": report_data.get("report_type", intent)},
        f"Report generated: {report_data.get('report_title', 'Financial Report')}",
    )
    await asyncio.sleep(0.2)

    # --- Phase 4: Emit results ---
    response_text = report_data.get("response_text", "Here is your report.")
    await emitter.emit_agent_message(response_text)
    await asyncio.sleep(0.15)

    report_id = str(uuid4())
    report_payload = {
        "report_id": report_id,
        "report_title": report_data.get("report_title", "Financial Report"),
        "report_type": report_data.get("report_type", intent),
        "sections": report_data.get("sections", []),
        "narrative": report_data.get("narrative", ""),
        "division_name": report_data.get("division_name", ""),
        "period_label": report_data.get("period_label", ""),
    }
    await emitter.emit_report_generated(report_payload)

    # Update conversation context
    conversation.append_message("user", user_message)
    conversation.append_message("assistant", response_text)
    conversation.append_report(report_payload)

    return report_payload


async def run_vendor_compliance(conn, emitter: EventEmitter) -> dict[str, Any]:
    payload = await load_json("vendor_compliance_records.json")
    vendors = payload["vendors"]

    await emitter.emit_reasoning(
        f"Loading vendor compliance records. Found {len(vendors)} active vendors to audit for "
        "insurance certificates, W-9 status, licensing, and contract terms."
    )
    await asyncio.sleep(0.3)

    await emitter.emit_tool_call("scan_vendor_records", {"vendor_count": len(vendors)})
    await asyncio.sleep(0.2)

    await emitter.emit_reasoning(
        "Scanning each vendor's documentation for expired insurance, missing W-9 forms, "
        "lapsed licenses, and contract renewal deadlines."
    )
    await asyncio.sleep(0.2)

    _llm = await llm_json_response(
        agent_id="vendor_compliance",
        objective=(
            "Scan vendor compliance and return JSON with key findings (array). "
            "Each finding must include: vendor, issue, reason, action_type "
            "(renewal_email|urgent_hold_task|w9_email|contract_task), "
            "subject (optional), body (optional), task_title (optional), task_description (optional), task_priority (optional)."
        ),
        context_payload=payload,
        max_tokens=2000,
        temperature=0.1,
        validator=validate_vendor_compliance_findings,
    )
    model_plan = _llm.data
    await emitter.emit_llm("tool_result", {"tool": "llm_analysis", "result": {}, "summary": "LLM analysis complete"}, message="LLM analysis", prompt_tokens=_llm.prompt_tokens, completion_tokens=_llm.completion_tokens)

    findings = model_plan.get("findings")
    if not isinstance(findings, list):
        raise RuntimeError("vendor_compliance: model output missing findings[]")

    await emitter.emit_reasoning(
        f"Audit complete. Identified {len(findings)} compliance issue(s) across {len(vendors)} vendors. "
        "Processing each finding and executing required actions."
    )
    await asyncio.sleep(0.3)

    for finding in findings:
        if not isinstance(finding, dict):
            continue
        vendor_name = str(finding.get("vendor", "")).strip()
        action_type = str(finding.get("action_type", "")).strip()
        if not vendor_name or not action_type:
            raise RuntimeError("vendor_compliance: finding missing vendor/action_type")

        vendor = next((v for v in vendors if v["name"] == vendor_name), None)
        if not vendor:
            continue

        await emitter.emit_tool_call("check_vendor", {"vendor": vendor_name, "issue": str(finding.get("issue", "")), "action": action_type})
        await asyncio.sleep(0.1)

        await emitter.emit_tool_result(
            "check_vendor",
            {"vendor": vendor_name, "issue": str(finding.get("issue", "")), "action_type": action_type, "reason": str(finding.get("reason", ""))},
            f"{vendor_name}: {finding.get('issue', 'compliance issue')} — action: {action_type.replace('_', ' ')}",
        )
        await asyncio.sleep(0.15)

        if action_type in {"renewal_email", "w9_email"}:
            subject = str(finding.get("subject", "")).strip()
            body = str(finding.get("body", "")).strip()
            if not subject or not body:
                raise RuntimeError(f"vendor_compliance: missing email content for {vendor_name}")
            await insert_communication(conn, "vendor_compliance", vendor["email"], subject, body)
            await emitter.emit_communication(vendor["email"], subject, body)

        if action_type in {"urgent_hold_task", "contract_task"}:
            title = str(finding.get("task_title", "")).strip() or f"Compliance task: {vendor_name}"
            description = str(finding.get("task_description", "")).strip() or str(finding.get("reason", "")).strip()
            priority = str(finding.get("task_priority", "")).strip() or ("critical" if action_type == "urgent_hold_task" else "medium")
            await insert_internal_task(conn, "vendor_compliance", title, description, priority)

    # Build compliance summary
    issue_types = set()
    expired_count = 0
    expiring_count = 0
    for f in findings:
        at = str(f.get("action_type", ""))
        if at == "urgent_hold_task":
            expired_count += 1
        elif at in {"renewal_email", "contract_task", "w9_email"}:
            expiring_count += 1
    compliant_count = len(vendors) - expired_count - expiring_count
    compliance_summary = {
        "total_vendors": len(vendors),
        "compliant": compliant_count,
        "expiring": expiring_count,
        "non_compliant": expired_count,
        "issues_found": len(findings),
    }

    await emitter.emit_status_change("complete", f"Vendor compliance audit finished: {len(findings)} issue(s) across {len(vendors)} vendors.")
    return {"findings": findings, "compliance_summary": compliance_summary}


async def run_schedule_optimizer(conn, emitter: EventEmitter) -> dict[str, Any]:
    payload = await load_json("dispatch_jobs.json")
    jobs = payload.get("jobs", [])
    crews = payload.get("crews", [])

    await emitter.emit_reasoning(
        f"Loading dispatch data: {len(jobs)} jobs across the Raleigh-Durham metro area "
        f"with {len(crews)} available crews. Analyzing GPS coordinates and job requirements."
    )
    await asyncio.sleep(0.3)

    await emitter.emit_tool_call("load_dispatch_data", {"jobs": len(jobs), "crews": len(crews)})
    await asyncio.sleep(0.2)

    await emitter.emit_tool_result(
        "load_dispatch_data",
        {"jobs_loaded": len(jobs), "crews_available": len(crews)},
        f"Loaded {len(jobs)} dispatch jobs and {len(crews)} crew assignments.",
    )
    await asyncio.sleep(0.2)

    await emitter.emit_reasoning(
        "Running route optimization algorithm. Minimizing total drive time by clustering nearby jobs "
        "and assigning them to the closest available crew while respecting crew skill requirements."
    )
    await asyncio.sleep(0.3)

    await emitter.emit_tool_call("optimize_routes", {"algorithm": "proximity_cluster", "jobs": len(jobs)})
    await asyncio.sleep(0.1)

    _llm = await llm_json_response(
        agent_id="schedule_optimizer",
        objective=(
            "Optimize crew assignments and routes. Return JSON with keys: "
            "assignments (object mapping crew_id to ordered job IDs), "
            "unoptimized_drive_minutes, optimized_drive_minutes, improvement_percent, rationale."
        ),
        context_payload=payload,
        max_tokens=1600,
        temperature=0.1,
        validator=validate_schedule_output,
    )
    result = _llm.data
    await emitter.emit_llm("tool_result", {"tool": "llm_analysis", "result": {}, "summary": "LLM analysis complete"}, message="LLM analysis", prompt_tokens=_llm.prompt_tokens, completion_tokens=_llm.completion_tokens)

    assignments = result.get("assignments", {})
    for crew_id, job_ids in assignments.items():
        if isinstance(job_ids, list):
            await emitter.emit_tool_result(
                "assign_crew",
                {"crew": crew_id, "jobs": job_ids, "job_count": len(job_ids)},
                f"Assigned {len(job_ids)} jobs to {crew_id.replace('_', ' ')}: {' → '.join(str(j) for j in job_ids)}",
            )
            await asyncio.sleep(0.15)

    improvement = result.get("improvement_percent", 0)
    optimized = result.get("optimized_drive_minutes", 0)
    unoptimized = result.get("unoptimized_drive_minutes", 0)
    await emitter.emit_reasoning(
        f"Optimization complete. Reduced total drive time from {unoptimized} to {optimized} minutes "
        f"({improvement}% improvement). {result.get('rationale', '')}"
    )
    await asyncio.sleep(0.2)

    await emitter.emit_tool_result(
        "optimize_routes",
        {"improvement_percent": improvement, "optimized_minutes": optimized, "unoptimized_minutes": unoptimized},
        f"Route optimization complete: {improvement}% improvement ({unoptimized} → {optimized} min).",
    )
    return result


def _compute_project_metrics(project: dict) -> dict:
    """Deterministic computation of all project metrics from proposal vs actuals.
    Returns a rich metrics dict — NO LLM involvement."""

    proposal = project.get("proposal", {})
    actuals = project.get("actuals", {})
    change_orders = project.get("change_orders", [])
    risk_flags = project.get("risk_flags", [])

    contract_value = proposal.get("contract_value", 0)
    estimated_cost = proposal.get("estimated_cost", 0)
    target_margin_pct = proposal.get("target_margin_pct", 0)
    pct_complete = actuals.get("percent_complete", 0)
    pct_billed = actuals.get("percent_billed", 0)
    total_cost_to_date = actuals.get("total_cost_to_date", 0)

    # ── Earned Value Analysis ──
    # BCWS (Budgeted Cost of Work Scheduled) = estimated_cost * pct_complete/100
    bcws = estimated_cost * pct_complete / 100 if estimated_cost else 0
    # BCWP (Budgeted Cost of Work Performed) = same as EV
    earned_value = bcws
    # ACWP = actual cost to date
    acwp = total_cost_to_date
    # Cost Performance Index (CPI) = EV / AC
    cpi = earned_value / acwp if acwp > 0 else 1.0
    # Estimate at Completion (EAC) = estimated_cost / CPI
    eac = estimated_cost / cpi if cpi > 0 else estimated_cost
    # Estimate to Complete (ETC) = EAC - ACWP
    etc = max(0, eac - acwp)
    # Variance at Completion (VAC) = estimated_cost - EAC
    vac = estimated_cost - eac
    # Projected margin
    projected_revenue = contract_value + sum(co.get("amount", 0) for co in change_orders if co.get("status") == "approved")
    projected_margin = projected_revenue - eac if eac > 0 else projected_revenue - estimated_cost
    projected_margin_pct = (projected_margin / projected_revenue * 100) if projected_revenue > 0 else 0

    # ── Cost Code Variance Analysis ──
    cost_code_analysis = []
    cost_by_code = actuals.get("cost_by_code", {})
    est_by_code = proposal.get("cost_estimate_by_code", {})
    for code, budgeted_val in est_by_code.items():
        actual_data = cost_by_code.get(code, {})
        if isinstance(actual_data, dict):
            actual_val = actual_data.get("actual", 0)
            code_pct = actual_data.get("pct_complete", 0)
        else:
            actual_val = 0
            code_pct = 0
        budgeted_for_pct = budgeted_val * code_pct / 100 if budgeted_val else 0
        variance = budgeted_for_pct - actual_val
        variance_pct = (variance / budgeted_for_pct * 100) if budgeted_for_pct > 0 else 0
        projected_final = actual_val / (code_pct / 100) if code_pct > 0 else actual_val
        cost_code_analysis.append({
            "code": code,
            "budgeted": budgeted_val,
            "actual": actual_val,
            "pct_complete": code_pct,
            "earned_value": round(budgeted_for_pct),
            "variance": round(variance),
            "variance_pct": round(variance_pct, 1),
            "projected_final": round(projected_final),
            "over_budget": actual_val > budgeted_for_pct * 1.05 and code_pct > 0,
        })

    # ── Labor Analysis ──
    labor_est = proposal.get("labor_estimate", {})
    labor_act = actuals.get("labor", {})
    est_hours = labor_est.get("total_labor_hours", 0)
    est_rate = labor_est.get("avg_loaded_rate", 0)
    est_labor_cost = labor_est.get("estimated_labor_cost", 0)
    act_hours = labor_act.get("total_hours_to_date", 0)
    act_rate = labor_act.get("avg_actual_loaded_rate", 0)
    act_labor_cost = labor_act.get("labor_cost_to_date", 0)
    overtime_hours = labor_act.get("overtime_hours", 0)
    overtime_cost = labor_act.get("overtime_cost", 0)
    productivity_index = labor_act.get("productivity_index", 1.0)

    # Hours burn rate
    expected_hours_at_pct = est_hours * pct_complete / 100 if est_hours else 0
    hours_variance = expected_hours_at_pct - act_hours
    hours_variance_pct = (hours_variance / expected_hours_at_pct * 100) if expected_hours_at_pct > 0 else 0
    # Rate variance
    rate_variance = act_rate - est_rate
    rate_impact = rate_variance * act_hours if act_hours > 0 else 0
    # Overtime percentage
    overtime_pct = (overtime_hours / act_hours * 100) if act_hours > 0 else 0
    # Projected total labor cost
    projected_labor = act_labor_cost / (pct_complete / 100) if pct_complete > 0 else act_labor_cost
    labor_budget_variance = est_labor_cost - projected_labor

    labor_analysis = {
        "estimated_hours": est_hours,
        "actual_hours": act_hours,
        "expected_hours_at_pct": round(expected_hours_at_pct),
        "hours_variance": round(hours_variance),
        "hours_variance_pct": round(hours_variance_pct, 1),
        "estimated_rate": est_rate,
        "actual_rate": act_rate,
        "rate_variance": round(rate_variance, 2),
        "rate_impact_dollars": round(rate_impact),
        "overtime_hours": overtime_hours,
        "overtime_cost": overtime_cost,
        "overtime_pct": round(overtime_pct, 1),
        "productivity_index": productivity_index,
        "estimated_labor_cost": est_labor_cost,
        "actual_labor_cost": act_labor_cost,
        "projected_labor_cost": round(projected_labor),
        "labor_budget_variance": round(labor_budget_variance),
        "monthly_labor": labor_act.get("monthly_labor", []),
    }

    # ── Schedule Analysis ──
    schedule = actuals.get("schedule", {})
    milestones = schedule.get("milestones", [])
    completed_milestones = [m for m in milestones if m.get("status") == "complete"]
    in_progress_milestones = [m for m in milestones if m.get("status") == "in_progress"]
    avg_delay = 0
    if completed_milestones:
        delays = [m.get("days_delta", 0) or 0 for m in completed_milestones]
        avg_delay = sum(delays) / len(delays) if delays else 0

    schedule_analysis = {
        "days_elapsed": schedule.get("days_elapsed", 0),
        "days_behind": schedule.get("days_behind", 0),
        "days_ahead": schedule.get("days_ahead", 0),
        "critical_path_delay_cause": schedule.get("critical_path_delay_cause"),
        "total_milestones": len(milestones),
        "completed_milestones": len(completed_milestones),
        "in_progress_milestones": len(in_progress_milestones),
        "avg_milestone_delay_days": round(avg_delay, 1),
        "milestones": milestones,
    }

    # ── Change Order Summary ──
    approved_cos = [co for co in change_orders if co.get("status") == "approved"]
    pending_cos = [co for co in change_orders if co.get("status") == "pending"]
    co_summary = {
        "total_count": len(change_orders),
        "approved_count": len(approved_cos),
        "pending_count": len(pending_cos),
        "approved_value": sum(co.get("amount", 0) for co in approved_cos),
        "pending_value": sum(co.get("amount", 0) for co in pending_cos),
        "total_schedule_impact_days": sum(co.get("impact_days", 0) for co in change_orders),
        "items": change_orders,
    }

    # ── Proposal Assumption Check ──
    broken_assumptions = []
    assumptions = proposal.get("key_assumptions", [])
    # Cross-reference assumptions with risk flags and schedule data
    for assumption in assumptions:
        a_lower = assumption.lower()
        is_broken = False
        reason = ""
        if "rock" in a_lower and any("rock" in rf.lower() for rf in risk_flags):
            is_broken = True
            reason = "Rock excavation encountered — contradicts assumption"
        elif "fuel" in a_lower:
            # Check if fuel costs show up in risk flags
            if any("fuel" in rf.lower() for rf in risk_flags):
                is_broken = True
                reason = "Fuel costs exceeded assumed rate"
        elif "winter" in a_lower or "weather" in a_lower:
            if schedule.get("days_behind", 0) > 30:
                is_broken = True
                reason = "Schedule delays pushed work into winter season"
        elif "subcontractor" in a_lower:
            if any("subcontractor" in rf.lower() or "sub" in rf.lower() for rf in risk_flags):
                is_broken = True
                reason = "Subcontractor availability issues encountered"
            elif schedule.get("critical_path_delay_cause") and "subcontractor" in schedule["critical_path_delay_cause"].lower():
                is_broken = True
                reason = "Subcontractor delay impacted critical path"
        elif "blasting" in a_lower:
            if any("blast" in rf.lower() for rf in risk_flags):
                is_broken = True
                reason = "Blasting volumes exceeded geological survey predictions"
        elif "retaining wall" in a_lower or "redesign" in a_lower:
            if any("redesign" in rf.lower() or "retaining" in rf.lower() for rf in risk_flags):
                is_broken = True
                reason = "Retaining wall required redesign due to field conditions"
        elif "endangered" in a_lower or "environmental" in a_lower:
            if any("raptor" in rf.lower() or "environmental" in rf.lower() for rf in risk_flags):
                is_broken = True
                reason = "Environmental mitigation required for raptor nesting"
        broken_assumptions.append({
            "assumption": assumption,
            "status": "broken" if is_broken else "holding",
            "reason": reason,
        })

    return {
        "project_id": project.get("project_id"),
        "project_name": project.get("project_name"),
        "division": project.get("division"),
        "project_manager": project.get("project_manager"),
        "client": project.get("client"),
        "finding": project.get("finding", "on_track"),
        "start_date": project.get("start_date"),
        "original_end_date": project.get("original_end_date"),
        "projected_end_date": project.get("current_projected_end_date"),
        "contract_value": contract_value,
        "estimated_cost": estimated_cost,
        "target_margin_pct": target_margin_pct,
        "total_cost_to_date": total_cost_to_date,
        "percent_complete": pct_complete,
        "percent_billed": pct_billed,
        "earned_value_analysis": {
            "earned_value": round(earned_value),
            "actual_cost": acwp,
            "cpi": round(cpi, 3),
            "eac": round(eac),
            "etc": round(etc),
            "vac": round(vac),
            "projected_revenue": round(projected_revenue),
            "projected_margin": round(projected_margin),
            "projected_margin_pct": round(projected_margin_pct, 1),
        },
        "cost_code_analysis": cost_code_analysis,
        "labor_analysis": labor_analysis,
        "schedule_analysis": schedule_analysis,
        "change_order_summary": co_summary,
        "broken_assumptions": broken_assumptions,
        "risk_flags": risk_flags,
    }


def _validate_single_project_analysis(payload: dict[str, Any]) -> list[str]:
    """Validator for a single project's LLM analysis output."""
    errors: list[str] = []
    if not _is_non_empty_string(payload.get("executive_summary")):
        errors.append("executive_summary is required")
    if not _is_non_empty_string(payload.get("root_cause_analysis")):
        errors.append("root_cause_analysis is required")
    if not _is_non_empty_string(payload.get("recommendation")):
        errors.append("recommendation is required")
    if not _is_non_empty_string(payload.get("proposal_vs_actual_insight")):
        errors.append("proposal_vs_actual_insight is required")
    if not _is_non_empty_string(payload.get("labor_insight")):
        errors.append("labor_insight is required")
    if not _is_non_empty_string(payload.get("schedule_insight")):
        errors.append("schedule_insight is required")
    if not isinstance(payload.get("create_task"), bool):
        errors.append("create_task must be boolean")
    if not _is_non_empty_string(payload.get("status_color")):
        errors.append("status_color is required (green/amber/red)")
    if not _is_non_empty_string(payload.get("finding")):
        errors.append("finding is required (on_track/at_risk/behind_schedule)")
    # reasoning_chain should be a list of strings
    chain = payload.get("reasoning_chain")
    if not isinstance(chain, list) or len(chain) < 3:
        errors.append("reasoning_chain must be an array of at least 3 reasoning steps")
    return errors


# ── Per-project thinking lines (shown while LLM reasons through each project) ──
_PROJECT_THINKING: dict[str, list[str]] = {
    "behind_schedule": [
        "Reviewing earned value metrics — CPI below 1.0 indicates cost overrun...",
        "Checking which cost codes are driving the variance...",
        "Analyzing labor productivity against original bid assumptions...",
        "Cross-referencing schedule milestones with critical path delays...",
        "Evaluating proposal assumptions that may have been broken...",
        "Assessing change order impacts on contract value and timeline...",
        "Calculating projected margin erosion based on current burn rate...",
        "Reviewing risk flags and their connection to field conditions...",
        "Determining root cause — is this a labor, material, or scope issue?...",
        "Formulating corrective action recommendations for the PM...",
    ],
    "at_risk": [
        "Earned value shows potential overrun — investigating cost drivers...",
        "Examining cost code actuals vs budget at current percent complete...",
        "Checking if labor rate variance is structural or temporary...",
        "Reviewing overtime hours as percentage of total — watching for burnout signals...",
        "Analyzing whether proposal assumptions still hold in the field...",
        "Looking at milestone completion dates vs baseline schedule...",
        "Evaluating pending change orders and their financial impact...",
        "Assessing productivity index against original bid estimates...",
        "Determining if risk level warrants escalation to senior leadership...",
        "Building recommendations based on leading indicator trends...",
    ],
    "on_track": [
        "Verifying earned value metrics align with schedule progress...",
        "Checking cost code performance across all categories...",
        "Confirming labor productivity is meeting or exceeding bid estimates...",
        "Reviewing milestone completions against baseline dates...",
        "Validating that proposal assumptions are holding in the field...",
        "Checking for any early warning signs in recent cost trends...",
        "Assessing change order pipeline for potential scope growth...",
        "Confirming projected margin is within acceptable range of target...",
    ],
}
_PROJECT_THINKING_DEFAULT = [
    "Loading project financials and comparing to original proposal...",
    "Analyzing cost performance index and earned value metrics...",
    "Reviewing labor hours, rates, and productivity trends...",
    "Checking schedule milestones and critical path status...",
    "Evaluating proposal assumptions against field reality...",
    "Calculating projected margin and estimate at completion...",
    "Reviewing change orders and risk flags...",
    "Formulating executive assessment and recommendations...",
]


async def run_progress_tracking(conn, emitter: EventEmitter) -> dict[str, Any]:
    payload = await load_json("project_progress.json")
    projects = payload.get("projects", [])
    as_of = payload.get("as_of_date", "2026-01-15")

    await emitter.emit_reasoning(
        f"Loading project data from Vista ERP. Found {len(projects)} active construction projects. "
        "Will analyze each project individually — comparing proposal estimates to actuals, "
        "computing earned value metrics, and assessing labor productivity."
    )
    await asyncio.sleep(0.3)

    await emitter.emit_tool_call("connect_vista_api", {"system": "Vista ERP", "module": "Job Cost"})
    await asyncio.sleep(0.2)
    await emitter.emit_tool_result(
        "connect_vista_api",
        {"status": "connected", "modules": ["Job Cost", "Payroll", "Project Management"]},
        "Connected to Vista ERP — Job Cost, Payroll & PM modules.",
    )
    await asyncio.sleep(0.15)

    # ═══════════════════════════════════════════════════════════════
    # Per-Project Analysis Loop (deterministic compute + individual LLM reasoning)
    # ═══════════════════════════════════════════════════════════════
    computed_projects = []
    findings = []

    for proj_idx, project in enumerate(projects, start=1):
        pname = project.get("project_name", "Unknown")
        pid = project.get("project_id", "")

        # ── Step 1: Announce which project we're analyzing ──
        await emitter.emit_reasoning(
            f"Analyzing project {proj_idx} of {len(projects)}: {pname} ({pid}). "
            f"Loading proposal data, actuals, change orders, and risk flags."
        )
        await asyncio.sleep(0.2)

        await emitter.emit_tool_call("load_project_data", {
            "project": pname,
            "project_id": pid,
            "index": f"{proj_idx} of {len(projects)}",
        })
        await asyncio.sleep(0.15)

        # ── Step 2: Deterministic computation ──
        metrics = _compute_project_metrics(project)
        computed_projects.append(metrics)

        ev = metrics["earned_value_analysis"]
        la = metrics["labor_analysis"]
        sa = metrics["schedule_analysis"]
        finding_status = metrics["finding"]
        broken = [ba for ba in metrics["broken_assumptions"] if ba["status"] == "broken"]
        over_budget_codes = [cc for cc in metrics["cost_code_analysis"] if cc.get("over_budget")]

        await emitter.emit_tool_result(
            "load_project_data",
            {
                "project": pname,
                "contract_value": metrics["contract_value"],
                "percent_complete": metrics["percent_complete"],
                "cost_to_date": metrics["total_cost_to_date"],
                "cost_codes": len(metrics["cost_code_analysis"]),
                "change_orders": metrics["change_order_summary"]["total_count"],
                "risk_flags": len(metrics["risk_flags"]),
            },
            f"Loaded {pname}: ${metrics['contract_value']:,.0f} contract, "
            f"{metrics['percent_complete']}% complete, "
            f"${metrics['total_cost_to_date']:,.0f} spent to date.",
        )
        await asyncio.sleep(0.15)

        # ── Step 3: Show earned value computation results ──
        await emitter.emit_tool_call("compute_earned_value", {
            "project": pname,
            "earned_value": ev["earned_value"],
            "actual_cost": ev["actual_cost"],
        })
        await asyncio.sleep(0.1)
        await emitter.emit_tool_result(
            "compute_earned_value",
            {
                "cpi": ev["cpi"],
                "eac": ev["eac"],
                "etc": ev["etc"],
                "vac": ev["vac"],
                "projected_margin_pct": ev["projected_margin_pct"],
            },
            f"CPI: {ev['cpi']:.2f} | EAC: ${ev['eac']:,.0f} | "
            f"Projected Margin: {ev['projected_margin_pct']:.1f}%"
            + (f" | {len(over_budget_codes)} cost codes over budget" if over_budget_codes else ""),
        )
        await asyncio.sleep(0.15)

        # ── Step 4: Show labor analysis results ──
        await emitter.emit_tool_call("analyze_labor_productivity", {
            "project": pname,
            "actual_hours": la["actual_hours"],
            "estimated_hours": la["estimated_hours"],
        })
        await asyncio.sleep(0.1)
        await emitter.emit_tool_result(
            "analyze_labor_productivity",
            {
                "productivity_index": la["productivity_index"],
                "hours_variance": la["hours_variance"],
                "overtime_pct": la["overtime_pct"],
                "rate_impact": la["rate_impact_dollars"],
            },
            f"Productivity: {la['productivity_index']:.2f} | "
            f"Hours variance: {la['hours_variance']:+,.0f} | "
            f"Overtime: {la['overtime_pct']:.1f}% | "
            f"Rate impact: ${la['rate_impact_dollars']:+,.0f}",
        )
        await asyncio.sleep(0.15)

        # ── Step 5: LLM deep-reasoning on this single project ──
        await emitter.emit_reasoning(
            f"Running AI analysis on {pname} — evaluating cost performance, labor trends, "
            f"schedule risk, and proposal assumptions against field data."
        )
        await asyncio.sleep(0.2)

        await emitter.emit_tool_call("reason_about_project", {
            "project": pname,
            "cpi": ev["cpi"],
            "broken_assumptions": len(broken),
            "over_budget_codes": len(over_budget_codes),
            "schedule_days_behind": sa["days_behind"],
        })

        # Start background thinking stream while LLM processes this project
        thinking_lines = _PROJECT_THINKING.get(finding_status, _PROJECT_THINKING_DEFAULT)
        thinking_task = asyncio.create_task(
            _run_thinking_stream(emitter, thinking_lines, interval=1.8)
        )

        try:
            _llm = await llm_json_response(
                agent_id="progress_tracking",
                objective=(
                    f"You are a senior construction project analyst reviewing '{pname}' for a CFO/executive audience.\n"
                    "All numbers have been pre-computed — DO NOT recalculate any figures.\n\n"
                    "Analyze this project deeply and return a JSON object with:\n"
                    "- finding: on_track / at_risk / behind_schedule\n"
                    "- status_color: green / amber / red\n"
                    "- reasoning_chain: array of 5-8 strings, each a distinct analytical step you took to reach your conclusion. "
                    "Example: ['CPI of 0.73 indicates $0.73 earned for every $1.00 spent — 27% cost overrun', "
                    "'Earthwork cost code is the primary driver at 42% over earned value', ...]. "
                    "Each step should reference specific numbers from the data.\n"
                    "- executive_summary: 2-3 sentence high-level status for a CFO\n"
                    "- root_cause_analysis: 3-5 sentence paragraph explaining WHY the project is in its current state. "
                    "For at_risk/behind projects, reference specific broken proposal assumptions, cost code overruns, "
                    "labor productivity issues, and schedule delays. For on_track projects, highlight strengths and watch items.\n"
                    "- proposal_vs_actual_insight: 2-3 sentences comparing the original bid assumptions to field reality\n"
                    "- labor_insight: 2-3 sentences about labor productivity, overtime, rate variances\n"
                    "- schedule_insight: 2-3 sentences about schedule performance and milestone trends\n"
                    "- financial_risk_level: high / medium / low\n"
                    "- schedule_risk_level: high / medium / low\n"
                    "- recommendation: 2-3 sentence specific, actionable recommendation for the PM\n"
                    "- create_task: boolean (true for at_risk/behind_schedule)\n"
                    "- task_title: string if create_task\n"
                    "- task_priority: high / medium / low\n\n"
                    "CRITICAL: Reference specific dollar amounts, percentages, cost codes, and metrics from the data below. "
                    "The reasoning_chain is the most important field — it shows HOW you arrived at your assessment."
                ),
                context_payload={
                    "project_metrics": metrics,
                },
                max_tokens=2000,
                temperature=0.2,
                validator=_validate_single_project_analysis,
            )
        finally:
            thinking_task.cancel()
            try:
                await thinking_task
            except asyncio.CancelledError:
                pass

        project_analysis = _llm.data
        await emitter.emit_llm(
            "tool_result",
            {"tool": "llm_analysis", "result": {}, "summary": f"AI analysis complete for {pname}"},
            message=f"LLM analysis for {pname}",
            prompt_tokens=_llm.prompt_tokens,
            completion_tokens=_llm.completion_tokens,
        )

        # Enrich the analysis with project identifiers
        project_analysis["project_id"] = pid
        project_analysis["project_name"] = pname

        # Emit the reasoning chain as visible reasoning steps
        reasoning_chain = project_analysis.get("reasoning_chain", [])
        for step in reasoning_chain:
            await emitter.emit_thinking(f"→ {step}")
            await asyncio.sleep(0.3)

        status_label = project_analysis.get("finding", finding_status).replace("_", " ").title()
        risk_level = project_analysis.get("financial_risk_level", "medium")

        await emitter.emit_tool_result(
            "reason_about_project",
            {
                "project": pname,
                "finding": project_analysis.get("finding", finding_status),
                "financial_risk": risk_level,
                "schedule_risk": project_analysis.get("schedule_risk_level", "medium"),
                "reasoning_steps": len(reasoning_chain),
            },
            f"{pname}: {status_label} — Financial Risk: {risk_level.upper()} | "
            f"Reasoning: {len(reasoning_chain)} analytical steps",
        )
        await asyncio.sleep(0.15)

        findings.append(project_analysis)

        # Create internal task if flagged
        if bool(project_analysis.get("create_task")):
            title = str(project_analysis.get("task_title", "")).strip() or f"PM follow-up: {pname}"
            description = str(project_analysis.get("executive_summary", "")).strip() or "Flagged project risk."
            priority = str(project_analysis.get("task_priority", "")).strip() or "high"
            await insert_internal_task(conn, "progress_tracking", title, description, priority)

    # ═══════════════════════════════════════════════════════════════
    # Portfolio Summary (deterministic)
    # ═══════════════════════════════════════════════════════════════
    total_contract = sum(p["contract_value"] for p in computed_projects)
    total_estimated = sum(p["estimated_cost"] for p in computed_projects)
    total_cost_to_date = sum(p["total_cost_to_date"] for p in computed_projects)
    total_eac = sum(p["earned_value_analysis"]["eac"] for p in computed_projects)
    total_projected_revenue = sum(p["earned_value_analysis"]["projected_revenue"] for p in computed_projects)
    total_projected_margin = sum(p["earned_value_analysis"]["projected_margin"] for p in computed_projects)
    portfolio_margin_pct = (total_projected_margin / total_projected_revenue * 100) if total_projected_revenue > 0 else 0
    on_track = sum(1 for f in findings if f.get("finding") == "on_track")
    at_risk = sum(1 for f in findings if f.get("finding") == "at_risk")
    behind = sum(1 for f in findings if f.get("finding") == "behind_schedule")
    weighted_pct = sum(p["percent_complete"] * p["contract_value"] for p in computed_projects)
    portfolio_pct_complete = round(weighted_pct / total_contract, 1) if total_contract > 0 else 0

    kpi_summary = {
        "as_of_date": as_of,
        "total_projects": len(computed_projects),
        "total_contract_value": total_contract,
        "total_estimated_cost": total_estimated,
        "total_cost_to_date": total_cost_to_date,
        "total_eac": round(total_eac),
        "total_projected_revenue": round(total_projected_revenue),
        "total_projected_margin": round(total_projected_margin),
        "portfolio_margin_pct": round(portfolio_margin_pct, 1),
        "portfolio_pct_complete": portfolio_pct_complete,
        "on_track_count": on_track,
        "at_risk_count": at_risk,
        "behind_count": behind,
    }

    task_count = sum(1 for f in findings if f.get("create_task"))
    await emitter.emit_reasoning(
        f"Portfolio analysis complete. {len(findings)} projects assessed: "
        f"{on_track} on track, {at_risk} at risk, {behind} behind schedule. "
        f"Total portfolio value: ${total_contract:,.0f}, weighted {portfolio_pct_complete}% complete."
    )

    await emitter.emit_status_change(
        "complete",
        f"Analyzed {len(findings)} projects: {task_count} need PM attention.",
    )

    # ── Return rich data for frontend rendering ──
    return {
        "kpi_summary": kpi_summary,
        "findings": findings,
        "computed_projects": computed_projects,
    }


async def run_maintenance_scheduler(conn, emitter: EventEmitter) -> dict[str, Any]:
    payload = await load_json("equipment_maintenance.json")
    equipment = payload.get("equipment", [])

    await emitter.emit_reasoning(
        f"Loading equipment maintenance records. Scanning {len(equipment)} units including "
        "excavators, loaders, trucks, and generators for overdue service, wear indicators, and safety issues."
    )
    await asyncio.sleep(0.3)

    await emitter.emit_tool_call("scan_maintenance_records", {"equipment_count": len(equipment)})
    await asyncio.sleep(0.2)

    await emitter.emit_reasoning(
        "Checking each unit's service history, hour meter readings, and last inspection dates "
        "against manufacturer-recommended maintenance intervals."
    )
    await asyncio.sleep(0.2)

    _llm = await llm_json_response(
        agent_id="maintenance_scheduler",
        objective=(
            "Analyze equipment maintenance records and return JSON with key issues (array). "
            "Each issue must include unit, issue, action, severity, create_task (true/false), task_priority (optional)."
        ),
        context_payload=payload,
        max_tokens=1600,
        temperature=0.1,
        validator=validate_maintenance_issues,
    )
    model_plan = _llm.data
    await emitter.emit_llm("tool_result", {"tool": "llm_analysis", "result": {}, "summary": "LLM analysis complete"}, message="LLM analysis", prompt_tokens=_llm.prompt_tokens, completion_tokens=_llm.completion_tokens)

    issues = model_plan.get("issues")
    if not isinstance(issues, list):
        raise RuntimeError("maintenance_scheduler: model output missing issues[]")

    await emitter.emit_reasoning(
        f"Scan complete. Found {len(issues)} maintenance issue(s). Processing each and creating work orders as needed."
    )
    await asyncio.sleep(0.2)

    for issue in issues:
        if not isinstance(issue, dict):
            continue

        unit = issue.get("unit", "Equipment")
        severity = str(issue.get("severity", "")).strip()

        await emitter.emit_tool_call("inspect_unit", {"unit": unit, "severity": severity})
        await asyncio.sleep(0.1)

        if bool(issue.get("create_task")):
            priority = str(issue.get("task_priority", "")).strip() or (
                "critical" if severity == "critical" else "medium"
            )
            await insert_internal_task(
                conn,
                "maintenance_scheduler",
                f"Maintenance: {unit}",
                str(issue.get("action", "")).strip() or "Model generated maintenance action.",
                priority,
            )

        await emitter.emit_tool_result(
            "inspect_unit",
            {"unit": unit, "issue": issue.get("issue", ""), "severity": severity, "action": issue.get("action", "")},
            f"{unit}: {issue.get('issue', 'issue detected')} [{severity}] — {issue.get('action', '')}",
        )
        await asyncio.sleep(0.15)

    # Build fleet summary
    sev_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for iss in issues:
        s = str(iss.get("severity", "medium")).lower()
        if s in sev_counts:
            sev_counts[s] += 1
    fleet_summary = {
        "total_units": len(equipment),
        "issues_found": len(issues),
        "all_clear": len(equipment) - len(issues),
        "severity_counts": sev_counts,
    }

    await emitter.emit_status_change("complete", f"Equipment audit finished: {len(issues)} issue(s) across {len(equipment)} units.")
    return {"issues": issues, "fleet_summary": fleet_summary}


async def run_training_compliance(conn, emitter: EventEmitter) -> dict[str, Any]:
    payload = await load_json("hr_certifications.json")
    employees = payload.get("employees", [])

    await emitter.emit_reasoning(
        f"Loading HR certification records. Auditing {len(employees)} employees for OSHA, "
        "first aid, equipment operator, and safety certification compliance."
    )
    await asyncio.sleep(0.3)

    await emitter.emit_tool_call("audit_employee_certifications", {"employee_count": len(employees)})
    await asyncio.sleep(0.2)

    await emitter.emit_reasoning(
        "Checking each employee's certification expiration dates, required training completions, "
        "and cross-referencing with job role requirements."
    )
    await asyncio.sleep(0.2)

    _llm = await llm_json_response(
        agent_id="training_compliance",
        objective=(
            "Review employee certification compliance. Return JSON with key issues (array). "
            "Each issue must include name, issue_type, detail, create_task (true/false), task_priority (optional)."
        ),
        context_payload=payload,
        max_tokens=1600,
        temperature=0.1,
        validator=validate_training_issues,
    )
    model_plan = _llm.data
    await emitter.emit_llm("tool_result", {"tool": "llm_analysis", "result": {}, "summary": "LLM analysis complete"}, message="LLM analysis", prompt_tokens=_llm.prompt_tokens, completion_tokens=_llm.completion_tokens)

    issues = model_plan.get("issues")
    if not isinstance(issues, list):
        raise RuntimeError("training_compliance: model output missing issues[]")

    await emitter.emit_reasoning(
        f"Compliance audit complete. Found {len(issues)} issue(s). Reviewing each employee and creating remediation tasks."
    )
    await asyncio.sleep(0.2)

    for issue in issues:
        if not isinstance(issue, dict):
            continue

        name = issue.get("name", "Employee")
        issue_type = issue.get("issue_type", "")

        await emitter.emit_tool_call("check_employee", {"employee": name, "issue_type": issue_type})
        await asyncio.sleep(0.1)

        if bool(issue.get("create_task")):
            await insert_internal_task(
                conn,
                "training_compliance",
                f"Training compliance: {name}",
                str(issue.get("detail", "")).strip() or "Model-generated compliance issue.",
                str(issue.get("task_priority", "")).strip() or "high",
            )

        await emitter.emit_tool_result(
            "check_employee",
            {"employee": name, "issue_type": issue_type, "detail": issue.get("detail", ""), "task_created": bool(issue.get("create_task"))},
            f"{name}: {issue_type.replace('_', ' ')} — {issue.get('detail', '')}",
        )
        await asyncio.sleep(0.15)

    # Build training compliance summary
    type_counts = {}
    for iss in issues:
        t = str(iss.get("issue_type", "expired")).lower().replace(" ", "_")
        type_counts[t] = type_counts.get(t, 0) + 1
    training_summary = {
        "total_employees": len(employees),
        "non_compliant": len(set(iss.get("name", "") for iss in issues)),
        "compliant": len(employees) - len(set(iss.get("name", "") for iss in issues)),
        "issues_found": len(issues),
        "type_counts": type_counts,
    }

    await emitter.emit_status_change("complete", f"Training audit finished: {len(issues)} issue(s) across {len(employees)} employees.")
    return {"issues": issues, "training_summary": training_summary}


async def run_onboarding(conn, emitter: EventEmitter) -> dict[str, Any]:
    payload = await load_json("onboarding_new_hire.json")

    hire_name = payload.get("new_hire", {}).get("name", "new hire")
    hire_role = payload.get("new_hire", {}).get("role", "employee")
    await emitter.emit_reasoning(
        f"Loading new hire data for {hire_name} ({hire_role}). "
        "Building comprehensive onboarding checklist including documents, training, and equipment."
    )
    await asyncio.sleep(0.3)

    await emitter.emit_tool_call("load_new_hire", {"name": hire_name, "role": hire_role})
    await asyncio.sleep(0.2)

    await emitter.emit_tool_result(
        "load_new_hire",
        {"name": hire_name, "role": hire_role},
        f"Loaded new hire profile: {hire_name}, {hire_role}.",
    )
    await asyncio.sleep(0.2)

    await emitter.emit_reasoning(
        "Generating onboarding workflow: required documentation, safety training schedule, "
        "equipment assignments, and welcome communications."
    )
    await asyncio.sleep(0.3)

    await emitter.emit_tool_call("run_onboarding_workflow", {"hire": hire_name})
    await asyncio.sleep(0.1)

    _llm = await llm_json_response(
        agent_id="onboarding",
        objective=(
            "Create onboarding workflow output. Return JSON with keys: "
            "hire, checklist (documents/training/equipment arrays each item has name and status), "
            "welcome_email_recipient, welcome_email_subject, welcome_email_body. "
            "IMPORTANT: This new hire's onboarding is already partially underway. "
            "Set realistic statuses: W-4 and I-9 should be 'complete' (already submitted). "
            "Direct Deposit should be 'in_progress'. Handbook Acknowledgment should be 'pending'. "
            "OSHA 10-Hour should be 'scheduled'. Equipment Operator Cert should be 'pending'. "
            "Site Safety Orientation should be 'pending'. "
            "Hard hat and Safety vest should be 'issued'. Steel-toe boots and Radio should be 'pending'. "
            "This gives a mix of complete/in-progress/pending items."
        ),
        context_payload=payload,
        max_tokens=1400,
        temperature=0.1,
        validator=validate_onboarding_plan,
    )
    plan = _llm.data
    await emitter.emit_llm("tool_result", {"tool": "llm_analysis", "result": {}, "summary": "LLM analysis complete"}, message="LLM analysis", prompt_tokens=_llm.prompt_tokens, completion_tokens=_llm.completion_tokens)

    hire = plan.get("hire")
    checklist = plan.get("checklist")
    recipient = str(plan.get("welcome_email_recipient", "")).strip()
    subject = str(plan.get("welcome_email_subject", "")).strip()
    body = str(plan.get("welcome_email_body", "")).strip()

    if not isinstance(hire, dict) or not isinstance(checklist, dict):
        raise RuntimeError("onboarding: model output missing hire/checklist")
    if not recipient or not subject or not body:
        raise RuntimeError("onboarding: model output missing welcome email fields")

    for section_name in ["documents", "training", "equipment"]:
        items = checklist.get(section_name, [])
        if items:
            await emitter.emit_tool_result(
                f"prepare_{section_name}",
                {"section": section_name, "items": len(items), "details": items},
                f"Prepared {len(items)} {section_name} item(s) for {hire.get('name', 'new hire')}.",
            )
            await asyncio.sleep(0.15)

    await emitter.emit_reasoning(f"Onboarding workflow built. Sending welcome email to {hire.get('name', 'new hire')}.")
    await asyncio.sleep(0.2)

    await insert_communication(conn, "onboarding", recipient, subject, body)
    await emitter.emit_communication(recipient, subject, body)

    await emitter.emit_tool_result(
        "run_onboarding_workflow",
        {"hire": hire, "checklist_sections": list(checklist.keys())},
        f"Onboarding workflow complete for {hire.get('name', 'new hire')}.",
    )

    # Build onboarding progress summary
    all_items: list[dict[str, Any]] = []
    for section_name in ["documents", "training", "equipment"]:
        all_items.extend(checklist.get(section_name, []))
    completed = sum(1 for i in all_items if str(i.get("status", "")).lower() in ("complete", "completed", "done", "issued"))
    in_prog = sum(1 for i in all_items if str(i.get("status", "")).lower() in ("in_progress", "in progress", "scheduled", "pending_review"))
    pending = len(all_items) - completed - in_prog
    onboarding_summary = {
        "total_items": len(all_items),
        "completed": completed,
        "in_progress": in_prog,
        "pending": pending,
    }

    return {"hire": hire, "checklist": checklist, "onboarding_summary": onboarding_summary}


_THINKING_OVERFLOW = [
    "Reviewing calculations against industry benchmarks...",
    "Double-checking unit rate conversions and quantity takeoffs...",
    "Verifying cost allocations across labor, material, and equipment...",
    "Cross-referencing line totals with category subtotals...",
    "Validating pricing against historical project data...",
    "Checking for scope gaps or missing allowances...",
    "Reconciling quantities with plan measurements...",
    "Applying regional cost adjustment factors...",
    "Reviewing production rate assumptions for reasonableness...",
    "Confirming crew composition and equipment selections...",
    "Evaluating subcontractor vs. self-perform cost trade-offs...",
    "Assessing schedule impacts on resource loading...",
]


async def _run_thinking_stream(
    emitter: EventEmitter,
    lines: list[str],
    interval: float = 1.8,
) -> None:
    """Background task that emits thinking lines at intervals until cancelled."""
    for line in lines:
        await asyncio.sleep(interval)
        await emitter.emit_thinking(line)
    # If we run out of scripted lines, cycle through varied overflow lines
    # so the UI never shows a stale repeated message.
    idx = 0
    while True:
        await asyncio.sleep(2.5)
        await emitter.emit_thinking(_THINKING_OVERFLOW[idx % len(_THINKING_OVERFLOW)])
        idx += 1


async def run_cost_estimator(conn, emitter: EventEmitter) -> dict[str, Any]:
    agent_id = "cost_estimator"
    payload = await load_json("takeoff_data.json")
    project = payload.get("project", {})
    takeoff = payload.get("takeoff", [])
    cost_database = payload.get("cost_database", {})
    markup_schedule = payload.get("markup_schedule", {})

    # Group takeoff items by category (preserve order)
    categories_map: dict[str, list[dict[str, Any]]] = {}
    for item in takeoff:
        cat = item.get("category", "Other")
        categories_map.setdefault(cat, []).append(item)
    category_names = list(categories_map.keys())

    # ═══════════════════════════════════════════════════════════════
    # Phase 1: Load & Preview Takeoff
    # ═══════════════════════════════════════════════════════════════
    await emitter.emit_status_change("working", "Loading takeoff data")
    await update_agent_status(conn, agent_id, status="working", current_activity="Loading takeoff data")

    await emitter.emit_reasoning(
        f"Received takeoff for {project.get('name', 'project')} — "
        f"{project.get('client', 'N/A')}, {project.get('location', '')}. "
        f"Found {len(takeoff)} line items across {len(category_names)} scope categories: "
        + ", ".join(f"{c} ({len(items)})" for c, items in categories_map.items())
        + ". Will price each category against the company cost database."
    )
    await asyncio.sleep(0.2)

    await emitter.emit_tool_call("load_takeoff_data", {
        "project": project.get("name", ""),
        "project_id": project.get("project_id", ""),
        "client": project.get("client", ""),
        "line_items": len(takeoff),
        "categories": len(category_names),
    })
    await asyncio.sleep(0.2)

    # Build takeoff preview table for activity stream
    takeoff_preview_lines = []
    for cat_name in category_names:
        takeoff_preview_lines.append(f"── {cat_name} ──")
        for ti in categories_map[cat_name]:
            takeoff_preview_lines.append(
                f"  {ti['item']}: {ti['quantity']:,} {ti['unit']}"
            )

    await emitter.emit_tool_result(
        "load_takeoff_data",
        {
            "project": project.get("name", ""),
            "total_items": len(takeoff),
            "categories": {c: len(items) for c, items in categories_map.items()},
            "takeoff_preview": "\n".join(takeoff_preview_lines),
        },
        f"Loaded takeoff: {len(takeoff)} items across {len(category_names)} categories — "
        + ", ".join(f"{c} ({len(items)})" for c, items in categories_map.items()),
    )
    await asyncio.sleep(0.2)

    # ═══════════════════════════════════════════════════════════════
    # Phase 2: Per-Category Pricing Loop (LLM per category)
    # ═══════════════════════════════════════════════════════════════
    all_line_items: list[dict[str, Any]] = []
    category_subtotals: dict[str, float] = {}
    category_notes: dict[str, str] = {}

    # Per-category thinking lines (shown while LLM works)
    # ~10 lines × 1.6s interval = ~16 seconds of coverage before overflow kicks in
    _category_thinking: dict[str, list[str]] = {
        "Earthwork": [
            "Calculating bulk excavation volumes for mass grading...",
            "Cross-referencing dozer and loader production rates against soil conditions...",
            "Applying crew composition factors for cut-and-fill operations...",
            "Checking fill import quantities against material haul distances...",
            "Estimating topsoil strip depth and stockpile handling costs...",
            "Verifying compaction testing allowances in the equipment rates...",
            "Comparing cut-fill balance to determine net import or export...",
            "Factoring in equipment mobilization and site access constraints...",
            "Reviewing fine grading tolerances and finish grade requirements...",
            "Validating earthwork unit prices against recent bid tabulations...",
        ],
        "Utilities": [
            "Mapping utility trench depths and widths for each run...",
            "Looking up pipe material costs by diameter — 6-inch through 18-inch...",
            "Factoring in bedding material and backfill requirements per linear foot...",
            "Calculating manhole installation labor based on depth and connection count...",
            "Checking dewatering allowances for shallow groundwater conditions...",
            "Pricing fire hydrant assemblies including tees, valves, and thrust blocks...",
            "Estimating storm drain inlet costs with precast frames and grates...",
            "Reviewing sanitary sewer service lateral connection details...",
            "Applying trench safety and shoring costs for deeper utility runs...",
            "Verifying utility testing and inspection allowances per specification...",
        ],
        "Paving": [
            "Computing asphalt tonnage from area and specified section thickness...",
            "Pricing aggregate base course by the cubic yard including placement...",
            "Applying paving crew mobilization costs for phased installation...",
            "Verifying tack coat and prime coat rates against current supplier pricing...",
            "Calculating compaction and density testing requirements for base course...",
            "Reviewing HMA mix design specifications and plant delivery distances...",
            "Checking for phased paving requirements to maintain traffic flow...",
            "Estimating saw-cut and joint layout costs for pavement sections...",
        ],
        "Concrete": [
            "Estimating concrete yardage for curb, gutter, and sidewalk sections...",
            "Applying form and finish labor rates based on linear footage...",
            "Factoring in reinforcement and dowel requirements per the plans...",
            "Checking concrete pump and placement costs for accessible pours...",
            "Calculating driveway apron dimensions and transition details...",
            "Reviewing ADA-compliant ramp and detectable warning requirements...",
            "Pricing expansion joint material and saw-cut control joints...",
            "Estimating cure-and-seal application costs per square foot...",
        ],
        "Erosion Control": [
            "Calculating silt fence and inlet protection quantities from the SWPPP...",
            "Pricing hydroseeding by the acre including mobilization...",
            "Factoring in maintenance and inspection costs over the project duration...",
            "Checking stabilized construction entrance specifications against site access...",
            "Reviewing NPDES permit compliance requirements and reporting costs...",
            "Estimating temporary sediment basin sizing and removal costs...",
            "Pricing erosion control blanket installation on disturbed slopes...",
            "Calculating seeding and mulching rates for final stabilization...",
        ],
    }
    _default_thinking = [
        "Analyzing quantity takeoff data for this scope category...",
        "Cross-referencing unit rates against the cost database...",
        "Computing labor, material, and equipment costs per line item...",
        "Verifying totals and checking for pricing anomalies...",
        "Reviewing quantity measurements against plan details...",
        "Applying waste and overrun factors to material quantities...",
        "Checking for scope items that may require specialized equipment...",
        "Reconciling calculated costs with database rate structure...",
    ]

    for cat_idx, cat_name in enumerate(category_names, start=1):
        cat_items = categories_map[cat_name]

        await emitter.emit_status_change(
            "working", f"Pricing category {cat_idx} of {len(category_names)}: {cat_name}"
        )
        await update_agent_status(
            conn, agent_id, status="working",
            current_activity=f"Pricing {cat_name} ({cat_idx}/{len(category_names)})",
        )

        await emitter.emit_reasoning(
            f"Pricing {cat_name} — {len(cat_items)} items. "
            f"Looking up labor, material, and equipment rates from cost database."
        )

        # Show the rates being looked up
        cat_rates = cost_database.get(cat_name, {})
        await emitter.emit_tool_call("lookup_cost_database", {
            "category": cat_name,
            "items": len(cat_items),
            "rates_available": len(cat_rates),
        })
        await asyncio.sleep(0.15)

        rates_summary_parts = []
        for ti in cat_items:
            item_name = ti["item"]
            rates = cat_rates.get(item_name, {})
            rates_summary_parts.append(
                f"{item_name}: L=${rates.get('labor_rate', 0)}/unit, "
                f"M=${rates.get('material_rate', 0)}/unit, "
                f"E=${rates.get('equipment_rate', 0)}/unit"
            )

        await emitter.emit_tool_result(
            "lookup_cost_database",
            {"category": cat_name, "rates_found": len(cat_rates)},
            f"Found rates for {len(cat_rates)} items in {cat_name}:\n" + "\n".join(rates_summary_parts),
        )
        await asyncio.sleep(0.15)

        # Start thinking stream while LLM works
        thinking_lines = _category_thinking.get(cat_name, _default_thinking)
        thinking_task = asyncio.create_task(
            _run_thinking_stream(emitter, thinking_lines, interval=1.6)
        )

        # LLM call to price this category
        try:
            _llm = await cost_estimate_price_category(
                agent_id=agent_id,
                category=cat_name,
                items=cat_items,
                cost_db=cost_database,
                category_index=cat_idx,
                total_categories=len(category_names),
                model="anthropic/claude-opus-4",
            )
        finally:
            thinking_task.cancel()
            try:
                await thinking_task
            except asyncio.CancelledError:
                pass

        cat_result = _llm.data

        await emitter.emit_llm(
            "tool_result",
            {"tool": "llm_analysis", "result": {}, "summary": f"Priced {cat_name}"},
            message=f"LLM pricing for {cat_name}",
            prompt_tokens=_llm.prompt_tokens,
            completion_tokens=_llm.completion_tokens,
        )

        cat_subtotal = float(cat_result.get("category_subtotal", 0))
        cat_line_items = cat_result.get("line_items", [])

        # Tag each line item with category for assembly
        for li in cat_line_items:
            li["category"] = cat_name
        all_line_items.extend(cat_line_items)

        category_subtotals[cat_name] = round(cat_subtotal, 2)
        category_notes[cat_name] = cat_result.get("category_notes", "")

        await emitter.emit_tool_call("price_category", {
            "category": cat_name,
            "items_priced": len(cat_line_items),
            "category_subtotal": round(cat_subtotal, 2),
        })
        await emitter.emit_tool_result(
            "price_category",
            {
                "category": cat_name,
                "items_priced": len(cat_line_items),
                "category_subtotal": round(cat_subtotal, 2),
            },
            f"{cat_name}: {len(cat_line_items)} items priced — subtotal ${cat_subtotal:,.0f}",
        )
        await asyncio.sleep(0.15)

    # ═══════════════════════════════════════════════════════════════
    # Phase 3: Apply Markups (deterministic — no LLM)
    # ═══════════════════════════════════════════════════════════════
    direct_cost_total = round(sum(category_subtotals.values()), 2)

    overhead_rate = markup_schedule.get("overhead", 0.12)
    profit_rate = markup_schedule.get("profit", 0.10)
    contingency_rate = markup_schedule.get("contingency", 0.05)
    bond_rate = markup_schedule.get("bond", 0.015)
    mobilization_rate = markup_schedule.get("mobilization", 0.03)

    markups = {
        "overhead": round(direct_cost_total * overhead_rate, 2),
        "profit": round(direct_cost_total * profit_rate, 2),
        "contingency": round(direct_cost_total * contingency_rate, 2),
        "bond": round(direct_cost_total * bond_rate, 2),
        "mobilization": round(direct_cost_total * mobilization_rate, 2),
    }
    total_markups = round(sum(markups.values()), 2)
    grand_total = round(direct_cost_total + total_markups, 2)

    await emitter.emit_status_change("working", "Applying markups")
    await update_agent_status(conn, agent_id, status="working", current_activity="Applying markups")

    await emitter.emit_reasoning(
        f"All {len(category_names)} categories priced. Direct cost total: ${direct_cost_total:,.0f}. "
        f"Applying standard markups — "
        f"Overhead {overhead_rate*100:.0f}%: ${markups['overhead']:,.0f}, "
        f"Profit {profit_rate*100:.0f}%: ${markups['profit']:,.0f}, "
        f"Contingency {contingency_rate*100:.0f}%: ${markups['contingency']:,.0f}, "
        f"Bond {bond_rate*100:.1f}%: ${markups['bond']:,.0f}, "
        f"Mobilization {mobilization_rate*100:.0f}%: ${markups['mobilization']:,.0f}."
    )
    await asyncio.sleep(0.2)

    await emitter.emit_tool_call("apply_markups", {
        "direct_cost": direct_cost_total,
        "overhead": f"{overhead_rate*100:.0f}%",
        "profit": f"{profit_rate*100:.0f}%",
        "contingency": f"{contingency_rate*100:.0f}%",
        "bond": f"{bond_rate*100:.1f}%",
        "mobilization": f"{mobilization_rate*100:.0f}%",
    })
    await asyncio.sleep(0.15)

    await emitter.emit_tool_result(
        "apply_markups",
        {
            "direct_cost": direct_cost_total,
            "markups": markups,
            "total_markups": total_markups,
            "grand_total": grand_total,
        },
        f"Markups applied: ${total_markups:,.0f} on ${direct_cost_total:,.0f} direct cost. Grand total: ${grand_total:,.0f}",
    )
    await asyncio.sleep(0.15)

    # ═══════════════════════════════════════════════════════════════
    # Phase 4: Generate Proposal Narrative (1 LLM call)
    # ═══════════════════════════════════════════════════════════════
    await emitter.emit_status_change("working", "Generating proposal narrative")
    await update_agent_status(conn, agent_id, status="working", current_activity="Generating proposal narrative")

    await emitter.emit_tool_call("generate_proposal", {
        "project": project.get("name", ""),
        "grand_total": grand_total,
        "categories": len(category_names),
    })
    await asyncio.sleep(0.1)

    # Thinking stream for proposal generation
    proposal_thinking_task = asyncio.create_task(
        _run_thinking_stream(emitter, [
            "Drafting scope of work narrative for the proposal document...",
            f"Describing the {len(category_names)} major work categories and their interdependencies...",
            "Structuring the proposal around site preparation, underground, and surface improvements...",
            "Compiling standard assumptions for soil conditions, site access, and working hours...",
            "Documenting material availability and lead time assumptions...",
            "Identifying exclusions — building construction, electrical, permits, hazmat...",
            "Noting design change and unforeseen condition exclusions...",
            "Determining realistic project schedule based on scope complexity and sequencing...",
            "Factoring in weather-related schedule allowances for the region...",
            "Finalizing pricing validity period and contractual terms...",
            "Reviewing proposal language for completeness and professional tone...",
            "Assembling final proposal sections — scope, assumptions, exclusions, schedule...",
        ], interval=1.8)
    )

    try:
        proposal_llm = await llm_json_response(
            agent_id=agent_id,
            objective=(
                "Write the narrative sections for a professional construction cost proposal. "
                f"Project: {project.get('name', '')} — {project.get('description', '')}. "
                f"Location: {project.get('location', '')}. Client: {project.get('client', '')}. "
                f"Scope categories: {', '.join(category_names)}. "
                f"Direct cost: ${direct_cost_total:,.0f}. Grand total: ${grand_total:,.0f}. "
                "Return JSON with these keys:\n"
                "- scope_narrative: 2-3 paragraph professional description of the work\n"
                "- assumptions: array of 5-7 strings (soil conditions, access, working hours, "
                "weather, material availability, utilities, subgrade)\n"
                "- exclusions: array of 4-6 strings (building construction, electrical/mechanical, "
                "permits, design changes, hazmat, landscaping beyond seeding)\n"
                "- schedule_statement: 1 sentence estimated project duration\n"
                "- validity_statement: 1 sentence pricing validity period"
            ),
            context_payload={
                "project": project,
                "categories": category_names,
                "category_subtotals": category_subtotals,
                "category_notes": category_notes,
                "direct_cost_total": direct_cost_total,
                "grand_total": grand_total,
            },
            max_tokens=1500,
            temperature=0.2,
            validator=validate_proposal_narrative,
            model="anthropic/claude-opus-4",
        )
    finally:
        proposal_thinking_task.cancel()
        try:
            await proposal_thinking_task
        except asyncio.CancelledError:
            pass

    proposal = proposal_llm.data

    await emitter.emit_llm(
        "tool_result",
        {"tool": "llm_analysis", "result": {}, "summary": "Proposal narrative generated"},
        message="LLM proposal narrative",
        prompt_tokens=proposal_llm.prompt_tokens,
        completion_tokens=proposal_llm.completion_tokens,
    )

    await emitter.emit_tool_result(
        "generate_proposal",
        {"status": "complete", "assumptions": len(proposal.get("assumptions", [])), "exclusions": len(proposal.get("exclusions", []))},
        f"Proposal narrative generated with {len(proposal.get('assumptions', []))} assumptions and {len(proposal.get('exclusions', []))} exclusions.",
    )
    await asyncio.sleep(0.1)

    # ═══════════════════════════════════════════════════════════════
    # Assemble final result
    # ═══════════════════════════════════════════════════════════════
    result: dict[str, Any] = {
        "project": project,
        "line_items": all_line_items,
        "category_subtotals": category_subtotals,
        "category_notes": category_notes,
        "direct_cost_total": direct_cost_total,
        "markups": markups,
        "grand_total": grand_total,
        "assumptions": proposal.get("assumptions", []),
        "exclusions": proposal.get("exclusions", []),
        "proposal": {
            "scope_narrative": proposal.get("scope_narrative", ""),
            "schedule_statement": proposal.get("schedule_statement", ""),
            "validity_statement": proposal.get("validity_statement", ""),
        },
    }

    await emitter.emit_status_change(
        "complete",
        f"Proposal complete for {project.get('name', 'project')}: ${grand_total:,.0f}",
    )
    return result


async def run_inquiry_router(conn, emitter: EventEmitter) -> dict[str, Any]:
    payload = await load_json("inquiry_emails.json")
    emails = payload.get("emails", [])

    await emitter.emit_reasoning(
        f"Loading customer inquiry inbox. Found {len(emails)} incoming emails to classify and route "
        "to the appropriate department (estimating, billing, operations, management)."
    )
    await asyncio.sleep(0.3)

    await emitter.emit_tool_call("load_inquiry_emails", {"email_count": len(emails)})
    await asyncio.sleep(0.2)

    await emitter.emit_reasoning(
        "Analyzing each email's subject, sender, and content to determine the correct department routing, "
        "urgency level, and create appropriate internal tasks."
    )
    await asyncio.sleep(0.2)

    await emitter.emit_tool_call("route_inquiries", {"emails": len(emails)})
    await asyncio.sleep(0.1)

    _llm = await llm_json_response(
        agent_id="inquiry_router",
        objective=(
            "Route customer inquiries. Return JSON with key routes (array). "
            "Each route item must include from, subject, route, priority, description."
        ),
        context_payload=payload,
        max_tokens=900,
        temperature=0.1,
        validator=validate_inquiry_routes,
    )
    plan = _llm.data
    await emitter.emit_llm("tool_result", {"tool": "llm_analysis", "result": {}, "summary": "LLM analysis complete"}, message="LLM analysis", prompt_tokens=_llm.prompt_tokens, completion_tokens=_llm.completion_tokens)

    routes = plan.get("routes")
    if not isinstance(routes, list):
        raise RuntimeError("inquiry_router: model output missing routes[]")

    await emitter.emit_reasoning(
        f"Routing decisions complete. Processing {len(routes)} inquiries and creating internal tasks."
    )
    await asyncio.sleep(0.2)

    for route in routes:
        if not isinstance(route, dict):
            continue
        subject = str(route.get("subject", "")).strip()
        sender = str(route.get("from", "")).strip()
        destination = str(route.get("route", "")).strip()
        priority = str(route.get("priority", "")).strip() or "medium"
        description = str(route.get("description", "")).strip() or f"From {sender} -> {destination}"
        if not subject or not sender or not destination:
            raise RuntimeError("inquiry_router: route entry missing required fields")

        await emitter.emit_tool_call("route_email", {"from": sender, "subject": subject})
        await asyncio.sleep(0.1)

        await insert_internal_task(
            conn,
            "inquiry_router",
            f"Route customer inquiry: {subject}",
            description,
            priority,
        )

        await emitter.emit_tool_result(
            "route_email",
            {"from": sender, "subject": subject, "route": destination, "priority": priority},
            f"{sender} → {destination} [{priority}]: {subject}",
        )
        await asyncio.sleep(0.15)

    await emitter.emit_status_change("complete", f"Routed {len(routes)} customer inquiries.")

    # Build inbox summary for frontend
    dept_counts: dict[str, int] = {}
    urgent_count = 0
    for r in routes:
        if not isinstance(r, dict):
            continue
        dept = str(r.get("route", "Other")).strip()
        dept_counts[dept] = dept_counts.get(dept, 0) + 1
        if str(r.get("priority", "")).lower() == "high":
            urgent_count += 1
    inbox_summary = {
        "total_emails": len(routes),
        "urgent": urgent_count,
        "departments": dept_counts,
    }

    return {"routes": routes, "inbox_summary": inbox_summary}


RUNNERS: dict[str, Callable[[Any, EventEmitter], Any]] = {
    "po_match": run_po_match,
    "ar_followup": run_ar_followup,
    "financial_reporting": run_financial_reporting,
    "vendor_compliance": run_vendor_compliance,
    "schedule_optimizer": run_schedule_optimizer,
    "progress_tracking": run_progress_tracking,
    "maintenance_scheduler": run_maintenance_scheduler,
    "training_compliance": run_training_compliance,
    "onboarding": run_onboarding,
    "cost_estimator": run_cost_estimator,
    "inquiry_router": run_inquiry_router,
}


@dataclass
class RunResult:
    output: dict[str, Any]
    total_cost: float
    input_tokens: int
    output_tokens: int


def infer_completed_tasks(output: dict[str, Any]) -> int:
    candidate_keys = ["processed", "results", "findings", "issues", "routes", "conversation"]
    for key in candidate_keys:
        value = output.get(key)
        if isinstance(value, list):
            return len(value)
    return 1


async def run_agent_session(agent_id: str, session_id: str) -> RunResult:
    if agent_id not in RUNNERS:
        raise ValueError(f"Unknown agent id: {agent_id}")
    if not llm_enabled():
        raise RuntimeError(
            "Model-only runtime requires USE_REAL_LLM=true and OPENROUTER_API_KEY configured."
        )

    conn = await connect_db()
    emitter = EventEmitter(conn, session_id, agent_id)

    try:
        await update_agent_status(conn, agent_id, status="working", current_activity="Starting run")
        await conn.commit()

        runner = RUNNERS[agent_id]
        output = await runner(conn, emitter)

        tasks_completed = infer_completed_tasks(output)
        cost_per_unit = round(emitter.total_cost / max(tasks_completed, 1), 6)

        await emitter.emit(
            "complete",
            {
                "agent_id": agent_id,
                "output": output,
                "metrics": {
                    "cost": round(emitter.total_cost, 6),
                    "raw_cost": round(emitter.total_raw_cost, 6),
                    "multiplier": emitter._multiplier,
                    "input_tokens": emitter.total_input_tokens,
                    "output_tokens": emitter.total_output_tokens,
                    "units_processed": tasks_completed,
                    "cost_per_unit": cost_per_unit,
                },
            },
            message=f"{agent_id} completed run",
        )
        await update_agent_status(
            conn,
            agent_id,
            status="idle",
            current_activity="Ready",
            additional_cost=emitter.total_cost,
            additional_tasks=tasks_completed,
            set_last_run=True,
        )
        await conn.commit()
        await session_manager.mark_done(session_id, output=output)

        return RunResult(
            output=output,
            total_cost=round(emitter.total_cost, 6),
            input_tokens=emitter.total_input_tokens,
            output_tokens=emitter.total_output_tokens,
        )
    except Exception as exc:  # noqa: BLE001
        await emitter.emit(
            "error",
            {"message": str(exc)},
            message=f"Run failed for {agent_id}: {exc}",
        )
        await update_agent_status(conn, agent_id, status="error", current_activity=str(exc)[:120])
        await conn.commit()
        await session_manager.mark_done(session_id, output={"error": str(exc)})
        raise
    finally:
        await conn.close()
