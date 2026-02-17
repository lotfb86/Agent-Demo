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


async def insert_review_item(conn, agent_id: str, item_ref: str, reason: str, details: str) -> int:
    cursor = await conn.execute(
        """
        INSERT INTO review_queue (agent_id, item_ref, reason_code, details, status, created_at)
        VALUES (?, ?, ?, ?, 'open', ?)
        """,
        (agent_id, item_ref, reason, details, utc_now()),
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
        resp = await llm_chat_with_usage(messages, temperature=temp, max_tokens=mtokens)
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


def make_ar_followup_validator(
    expected_customers: list[str],
    expected_actions: Optional[dict[str, str]] = None,
) -> Callable[[dict[str, Any]], list[str]]:
    allowed_actions = {
        "polite_reminder",
        "firm_email_plus_internal_task",
        "escalated_to_collections",
        "skip_retainage",
        "no_action_within_terms",
    }

    def validate(payload: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        actions = payload.get("actions")
        if not isinstance(actions, list):
            return ["actions must be an array"]

        seen: dict[str, dict[str, Any]] = {}
        for idx, row in enumerate(actions):
            if not isinstance(row, dict):
                errors.append(f"actions[{idx}] must be object")
                continue
            customer = row.get("customer")
            if not _is_non_empty_string(customer):
                errors.append(f"actions[{idx}].customer is required")
                continue
            seen[str(customer).strip()] = row

        for customer in expected_customers:
            if customer not in seen:
                errors.append(f"missing action for {customer}")

        for customer, row in seen.items():
            action = str(row.get("action", "")).strip()
            if action not in allowed_actions:
                errors.append(f"{customer}: invalid action")
            if expected_actions and expected_actions.get(customer) and action != expected_actions[customer]:
                errors.append(
                    f"{customer}: action must be {expected_actions[customer]}"
                )
            if not _is_non_empty_string(row.get("reason")):
                errors.append(f"{customer}: reason is required")
            if action in {"polite_reminder", "firm_email_plus_internal_task"}:
                if not _is_non_empty_string(row.get("email_subject")):
                    errors.append(f"{customer}: email_subject required for {action}")
                if not _is_non_empty_string(row.get("email_body")):
                    errors.append(f"{customer}: email_body required for {action}")
        return errors

    return validate


def validate_financial_report(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected_prompts = [
        "Pull me a P&L for the Excavation division for January 2026.",
        "How does that compare to January last year?",
        "Combine all divisions and give me a company-wide summary for Q4 2025.",
    ]
    conversation = payload.get("conversation")
    if not isinstance(conversation, list) or len(conversation) != 3:
        errors.append("conversation must be an array with exactly 3 entries")
    else:
        for idx, row in enumerate(conversation):
            if not isinstance(row, dict):
                errors.append(f"conversation[{idx}] must be object")
                continue
            if not _is_non_empty_string(row.get("prompt")):
                errors.append(f"conversation[{idx}].prompt is required")
            elif str(row.get("prompt")).strip() != expected_prompts[idx]:
                errors.append(f"conversation[{idx}].prompt must match demo prompt")
            if row.get("result") is None:
                errors.append(f"conversation[{idx}].result is required")
    if not _is_non_empty_string(payload.get("narrative")):
        errors.append("narrative is required")
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
    errors: list[str] = []
    # KPI summary
    kpi = payload.get("kpi_summary")
    if not isinstance(kpi, dict):
        errors.append("kpi_summary must be object")
    else:
        for field in ["total_budget", "total_spent", "on_track_count", "at_risk_count"]:
            if not _is_number(kpi.get(field)):
                errors.append(f"kpi_summary.{field} must be numeric")
    # Findings
    findings = payload.get("findings")
    if not isinstance(findings, list):
        return errors + ["findings must be an array"]
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
        if not _is_non_empty_string(row.get("message")):
            errors.append(f"findings[{idx}].message is required")
        if not isinstance(row.get("create_task"), bool):
            errors.append(f"findings[{idx}].create_task must be boolean")
        # New dashboard fields
        for num_field in ["budget_total", "actual_spent"]:
            if not _is_number(row.get(num_field)):
                errors.append(f"findings[{idx}].{num_field} must be numeric")
        if not _is_non_empty_string(row.get("status_color")):
            errors.append(f"findings[{idx}].status_color is required (green/amber/red)")
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
                review_id = await insert_review_item(conn, agent_id, invoice["invoice_number"], reason_code, details)
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


async def run_ar_followup(conn, emitter: EventEmitter) -> dict[str, Any]:
    agent_id = "ar_followup"
    rows = await fetchall(
        conn,
        "SELECT customer_name, days_out, amount, is_retainage, notes FROM ar_aging ORDER BY days_out DESC",
    )
    accounts = [dict(row) for row in rows]

    await emitter.emit_reasoning(
        f"Loading AR aging data. Found {len(accounts)} accounts to review, "
        f"ranging from {min(a['days_out'] for a in accounts)} to {max(a['days_out'] for a in accounts)} days outstanding."
    )
    await asyncio.sleep(0.3)

    total_outstanding = sum(float(a["amount"]) for a in accounts)
    await emitter.emit_tool_call("scan_ar_aging", {"accounts": len(accounts), "total_outstanding": round(total_outstanding, 2)})
    await asyncio.sleep(0.2)

    await emitter.emit_reasoning(
        "Analyzing each account's payment history, aging bucket, and retainage status to determine the appropriate follow-up action."
    )
    await asyncio.sleep(0.2)

    model_plan = await llm_json_response(
        agent_id=agent_id,
        objective=(
            "Choose AR follow-up actions for each account. "
            "Return JSON with key actions (array). Each action must include: "
            "customer, action (polite_reminder|firm_email_plus_internal_task|escalated_to_collections|skip_retainage|no_action_within_terms), "
            "reason, email_subject (optional), email_body (optional), recipient (optional), "
            "create_task (true/false), task_title (optional), task_description (optional), task_priority (optional). "
            "Include every customer exactly once."
        ),
        context_payload={"accounts": accounts},
        max_tokens=1400,
        temperature=0.1,
        validator=make_ar_followup_validator(
            expected_customers=[row["customer_name"] for row in accounts],
            expected_actions={
                "Greenfield Development": "polite_reminder",
                "Summit Property Group": "firm_email_plus_internal_task",
                "Parkview Associates": "escalated_to_collections",
                "Riverside Municipal": "skip_retainage",
                "Oak Valley Homes": "no_action_within_terms",
            },
        ),
    )

    actions = model_plan.get("actions")
    if not isinstance(actions, list):
        raise RuntimeError("ar_followup: model output missing actions[]")

    action_map: dict[str, dict[str, Any]] = {}
    for row in actions:
        if isinstance(row, dict) and row.get("customer"):
            action_map[str(row["customer"]).strip()] = row

    missing = [account["customer_name"] for account in accounts if account["customer_name"] not in action_map]
    if missing:
        raise RuntimeError(f"ar_followup: model omitted customers: {', '.join(missing)}")

    await emitter.emit_reasoning(
        f"Analysis complete. Generated action plan for all {len(accounts)} accounts. Now executing actions for each account."
    )
    await asyncio.sleep(0.3)

    results: list[dict[str, Any]] = []
    for idx, account in enumerate(accounts):
        customer = account["customer_name"]
        row = action_map[customer]
        action = str(row.get("action", "")).strip()
        reason = str(row.get("reason", "")).strip() or "Model-selected AR action."

        if action not in {
            "polite_reminder",
            "firm_email_plus_internal_task",
            "escalated_to_collections",
            "skip_retainage",
            "no_action_within_terms",
        }:
            raise RuntimeError(f"ar_followup: invalid action '{action}' for {customer}")

        await emitter.emit_reasoning(
            f"Reviewing account {idx + 1} of {len(accounts)}: {customer} — "
            f"${account['amount']:,.2f} outstanding, {account['days_out']} days. {reason}"
        )
        await asyncio.sleep(0.15)

        await emitter.emit_tool_call("determine_action", {"customer": customer, "days_out": account["days_out"], "amount": account["amount"]})
        await asyncio.sleep(0.1)

        await emitter.emit_tool_result(
            "determine_action",
            {"customer": customer, "action": action, "reason": reason},
            f"Selected '{action.replace('_', ' ')}' for {customer}.",
        )

        recipient = str(row.get("recipient", "")).strip() or f"billing@{customer.lower().replace(' ', '')}.com"
        subject = str(row.get("email_subject", "")).strip()
        body = str(row.get("email_body", "")).strip()

        if action in {"polite_reminder", "firm_email_plus_internal_task"}:
            if not subject or not body:
                raise RuntimeError(f"ar_followup: missing email content for {customer}")
            await insert_communication(conn, agent_id, recipient, subject, body)
            await emitter.emit_communication(recipient, subject, body)

        if action == "escalated_to_collections":
            await insert_collection_item(conn, customer, float(account["amount"]), reason)
            await emitter.emit_tool_result(
                "escalate_account",
                {"customer": customer, "amount": account["amount"], "reason": reason},
                f"Escalated {customer} to collections.",
            )

        create_task = bool(row.get("create_task"))
        if action == "firm_email_plus_internal_task":
            create_task = True
        if create_task:
            title = str(row.get("task_title", "")).strip() or f"AR follow-up for {customer}"
            description = str(row.get("task_description", "")).strip() or reason
            priority = str(row.get("task_priority", "")).strip() or "high"
            await insert_internal_task(
                conn,
                agent_id,
                title,
                description,
                priority,
                (datetime.utcnow() + timedelta(days=2)).date().isoformat(),
            )

        results.append({
            "customer": customer,
            "action": action,
            "reason": reason,
            "amount": float(account["amount"]),
            "days_out": int(account["days_out"]),
            "is_retainage": bool(account.get("is_retainage")),
        })

    # Build aging summary for the frontend
    total_outstanding = sum(float(a["amount"]) for a in accounts)
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

    return {"results": results, "aging_summary": aging_summary}


async def run_financial_reporting(conn, emitter: EventEmitter) -> dict[str, Any]:
    payload = await load_json("financial_reporting.json")

    await emitter.emit_reasoning(
        "Loading financial data including P&L statements across all divisions. "
        "I need to generate three conversational report responses and an executive narrative."
    )
    await asyncio.sleep(0.3)

    await emitter.emit_tool_call("load_financial_data", {"divisions": list(payload.get("divisions", {}).keys()) if isinstance(payload.get("divisions"), dict) else []})
    await asyncio.sleep(0.2)

    await emitter.emit_tool_result(
        "load_financial_data",
        {"status": "loaded"},
        "Loaded P&L data for all divisions across multiple periods.",
    )
    await asyncio.sleep(0.2)

    await emitter.emit_reasoning(
        "Step 1: Generating Excavation division P&L for January 2026. "
        "Step 2: Comparing against January 2025 year-over-year. "
        "Step 3: Consolidating all divisions for Q4 2025 company-wide summary."
    )
    await asyncio.sleep(0.3)

    await emitter.emit_tool_call("generate_report", {"prompts": 3, "scope": "Excavation + company-wide"})
    await asyncio.sleep(0.1)

    report = await llm_json_response(
        agent_id="financial_reporting",
        objective=(
            "Generate conversational financial-report outputs in strict JSON. "
            "Return keys: conversation (array length 3) and narrative (string). "
            "Conversation prompts MUST be exactly:\n"
            "1) Pull me a P&L for the Excavation division for January 2026.\n"
            "2) How does that compare to January last year?\n"
            "3) Combine all divisions and give me a company-wide summary for Q4 2025.\n"
            "Each conversation item must include prompt and result. Keep results concise but complete."
        ),
        context_payload=payload,
        max_tokens=2400,
        temperature=0.1,
        validator=validate_financial_report,
    )

    conversation = report.get("conversation", [])
    for idx, item in enumerate(conversation):
        prompt_text = item.get("prompt", f"Report query {idx + 1}")
        await emitter.emit_reasoning(f"Report {idx + 1} of 3: \"{prompt_text}\"")
        await asyncio.sleep(0.2)
        await emitter.emit_tool_result(
            "generate_report",
            {"prompt": prompt_text, "result": item.get("result", "")},
            f"Generated response for: {prompt_text[:60]}",
        )
        await asyncio.sleep(0.15)

    if report.get("narrative"):
        await emitter.emit_reasoning("Compiling executive narrative summary across all report queries.")
        await asyncio.sleep(0.15)
        await emitter.emit_tool_result(
            "compile_narrative",
            {"narrative": report["narrative"]},
            "Compiled executive narrative summary.",
        )

    return report


# ---------------------------------------------------------------------------
# Financial Reporting — Chat-driven query handler
# ---------------------------------------------------------------------------

DIVISION_NAMES = {
    "EX": "Excavation", "RC": "Road Construction", "SD": "Site Development",
    "LM": "Landscaping Maintenance", "RW": "Retaining Walls",
}
GL_DESCRIPTIONS = {
    "4100": "Contract Revenue", "4200": "Service Revenue",
    "5100": "Materials", "5200": "Equipment Rental", "5300": "Subcontractor",
    "5400": "Direct Labor", "5500": "Fuel", "5600": "Hauling",
    "6100": "Office Expenses", "6200": "Insurance", "6300": "Vehicle/Fleet",
    "6400": "IT & Software", "6500": "Professional Fees", "6600": "Misc Expenses",
}


def _filter_monthly_records(records: list[dict], division: str | None, period: str | None) -> list[dict]:
    """Filter monthly_records by division and/or period prefix."""
    out = records
    if division and division != "all":
        out = [r for r in out if r["division_id"] == division]
    if period:
        out = [r for r in out if r["period"].startswith(period)]
    return out


def _build_simulated_sql(intent: str, division: str | None, period: str | None, gl_filter: str | None) -> str:
    """Create a realistic-looking SQL query for the code-block visualization."""
    div_name = DIVISION_NAMES.get(division, "All Divisions") if division and division != "all" else "All Divisions"
    where_clauses = []
    if division and division != "all":
        where_clauses.append(f"division_id = '{division}'")
    if period:
        where_clauses.append(f"period LIKE '{period}%'")
    if gl_filter:
        where_clauses.append(f"gl_code = '{gl_filter}'")
    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    if intent == "comparison":
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
    """Chat-driven financial reporting: classify intent, query data, generate report."""
    from .session_manager import ConversationContext  # avoid circular at module-level

    payload = await load_json("financial_reporting.json")
    records = payload.get("monthly_records", [])

    # --- Step 1: Emit initial reasoning ---
    await emitter.emit_reasoning(
        f"Analyzing your request: \"{user_message[:100]}\" — "
        "I'll classify your intent, query the relevant financial data, and generate a report."
    )
    await asyncio.sleep(0.3)

    # --- Step 2: Intent classification (LLM) ---
    await emitter.emit_tool_call("classify_intent", {"message": user_message[:80]})
    await asyncio.sleep(0.2)

    history_for_llm = ""
    if conversation.messages:
        history_for_llm = "\n".join(
            f"{m['role'].upper()}: {m['content']}" for m in conversation.messages[-6:]
        )

    intent_result = await llm_json_response(
        agent_id="financial_reporting",
        objective=(
            "Classify the user's financial query and extract parameters.\n"
            "Return strict JSON with these keys:\n"
            "- intent: one of p_and_l, comparison, expense_analysis, job_costing, custom_query, clarification_needed\n"
            "- division: one of EX, RC, SD, LM, RW, all, or null\n"
            "- period: YYYY-MM or YYYY-Q# format, or null\n"
            "- compare_period: YYYY-MM or YYYY-Q# format, or null (only for comparisons)\n"
            "- gl_filter: a GL code like 5500, or null\n"
            "- clarification_question: a follow-up question string if intent is clarification_needed, else null\n\n"
            "Division lookup: EX=Excavation, RC=Road Construction, SD=Site Development, "
            "LM=Landscaping Maintenance, RW=Retaining Walls\n"
            "Available periods: 2025-01 through 2026-02\n"
            "GL codes: 4100=Contract Revenue, 4200=Service Revenue, 5100=Materials, "
            "5200=Equipment Rental, 5300=Subcontractor, 5400=Direct Labor, "
            "5500=Fuel, 5600=Hauling, 6100-6600=Operating Expenses\n\n"
            "Examples:\n"
            '- "Pull me a P&L for Excavation for January 2026" → intent=p_and_l, division=EX, period=2026-01\n'
            '- "How does that compare to last year?" → intent=comparison (use context for division/period)\n'
            '- "How much did we spend on fuel?" → intent=expense_analysis, gl_filter=5500\n'
            '- "Give me job costs" → intent=clarification_needed (which division? which period?)\n'
        ),
        context_payload={
            "user_message": user_message,
            "conversation_history": history_for_llm,
        },
        max_tokens=400,
        temperature=0.0,
    )

    intent = intent_result.get("intent", "custom_query")
    division = intent_result.get("division")
    period = intent_result.get("period")
    compare_period = intent_result.get("compare_period")
    gl_filter = intent_result.get("gl_filter")

    await emitter.emit_tool_result(
        "classify_intent",
        {"intent": intent, "division": division, "period": period},
        f"Classified as {intent}" + (f" for {DIVISION_NAMES.get(division, division or 'all divisions')}" if division else ""),
    )
    await asyncio.sleep(0.2)

    # --- Handle clarification ---
    if intent == "clarification_needed":
        question = intent_result.get("clarification_question") or (
            "Could you be more specific? For example, which division and time period are you interested in?"
        )
        conversation.append_message("user", user_message)
        conversation.append_message("assistant", question)
        await emitter.emit_agent_message(question, msg_type="clarification")
        return {"type": "clarification", "question": question}

    # --- Step 3: Data access simulation ---
    await emitter.emit_reasoning(
        f"Connecting to Vista ERP to pull financial data"
        + (f" for {DIVISION_NAMES.get(division, 'all divisions')}" if division else "")
        + (f", period {period}" if period else "")
        + "."
    )
    await asyncio.sleep(0.3)

    await emitter.emit_tool_call("connect_vista_api", {"module": "General Ledger", "connection": "vista-prod-01"})
    await asyncio.sleep(0.4)
    await emitter.emit_tool_result("connect_vista_api", {"status": "connected"}, "Connected to Vista GL module.")
    await asyncio.sleep(0.2)

    # Build and display SQL query
    sql_query = _build_simulated_sql(intent, division, period, gl_filter)
    await emitter.emit_tool_call("query_financial_data", {"query_type": intent, "division": division, "period": period})
    await asyncio.sleep(0.2)
    await emitter.emit_code_block("sql", sql_query)
    await asyncio.sleep(0.3)

    # Actually filter data
    filtered = _filter_monthly_records(records, division, period)
    row_count = len(filtered)
    await emitter.emit_tool_result(
        "query_financial_data",
        {"rows_returned": row_count},
        f"Retrieved {row_count} GL transaction records.",
    )
    await asyncio.sleep(0.2)

    # --- Step 4: Report generation (LLM) ---
    await emitter.emit_reasoning("Aggregating results and generating the report narrative...")
    await asyncio.sleep(0.3)

    await emitter.emit_tool_call("aggregate_results", {"intent": intent, "rows": row_count})
    await asyncio.sleep(0.1)

    # Build context for report generation
    report_context: dict[str, Any] = {"filtered_records": filtered[:100]}  # cap for token budget
    if intent == "comparison" and "excavation_jan_comparison" in payload:
        report_context["comparison_data"] = payload["excavation_jan_comparison"]
    if "summary" in payload:
        report_context["summary"] = payload["summary"]

    report_data = await llm_json_response(
        agent_id="financial_reporting",
        objective=(
            f"The user asked: \"{user_message}\"\n"
            f"Intent: {intent}, Division: {division or 'all'}, Period: {period or 'all available'}\n\n"
            "Generate a financial report response. Return strict JSON with these keys:\n"
            "- report_title: descriptive title for this report (e.g. 'Excavation Division P&L — January 2026')\n"
            "- report_type: one of p_and_l, comparison, expense_analysis\n"
            "- response_text: conversational 2-4 sentence summary answering the user's question directly\n"
            "- data: structured report object with keys like revenue, cogs, gross_profit, operating_expenses, "
            "net_income, gross_margin_percent, net_margin_percent. For comparisons include current and prior "
            "period columns with variance_dollar and variance_percent.\n"
            "- narrative: 1-2 sentence executive insight about trends or anomalies\n"
            "- division_name: full name of the division or 'Company-Wide'\n"
            "- period_label: human-readable period label like 'January 2026' or 'Q4 2025'\n"
        ),
        context_payload=report_context,
        max_tokens=1800,
        temperature=0.1,
    )

    await emitter.emit_tool_result(
        "aggregate_results",
        {"report_type": report_data.get("report_type", intent)},
        f"Report generated: {report_data.get('report_title', 'Financial Report')}",
    )
    await asyncio.sleep(0.2)

    # --- Step 5: Emit results ---
    response_text = report_data.get("response_text", "Here is your report.")
    await emitter.emit_agent_message(response_text)
    await asyncio.sleep(0.15)

    report_id = str(uuid4())
    report_payload = {
        "report_id": report_id,
        "report_title": report_data.get("report_title", "Financial Report"),
        "report_type": report_data.get("report_type", intent),
        "data": report_data.get("data", {}),
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

    model_plan = await llm_json_response(
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

    result = await llm_json_response(
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


async def run_progress_tracking(conn, emitter: EventEmitter) -> dict[str, Any]:
    payload = await load_json("project_progress.json")
    projects = payload.get("projects", [])

    await emitter.emit_reasoning(
        f"Loading job cost data from Vista ERP. Reviewing {len(projects)} active construction projects "
        "for budget variances, schedule delays, and milestone risks."
    )
    await asyncio.sleep(0.3)

    await emitter.emit_tool_call("connect_vista_api", {"system": "Vista ERP", "module": "Job Cost"})
    await asyncio.sleep(0.25)

    await emitter.emit_tool_result(
        "connect_vista_api",
        {"status": "connected", "module": "Job Cost Reports"},
        "Connected to Vista ERP — Job Cost module.",
    )
    await asyncio.sleep(0.2)

    await emitter.emit_tool_call("pull_job_cost_reports", {
        "project_count": len(projects),
        "projects": [p.get("project_id", "") for p in projects],
    })
    await asyncio.sleep(0.3)

    total_budget = sum(p.get("budget_total", 0) for p in projects)
    total_spent = sum(p.get("actual_spent", 0) for p in projects)
    await emitter.emit_tool_result(
        "pull_job_cost_reports",
        {"total_budget": total_budget, "total_spent": total_spent, "projects": len(projects)},
        f"Pulled job cost data for {len(projects)} projects. "
        f"Total budget: ${total_budget:,.0f}, Total spent: ${total_spent:,.0f}.",
    )
    await asyncio.sleep(0.2)

    await emitter.emit_reasoning(
        "Analyzing budget burn rates, percent complete vs percent billed, "
        "change order impacts, and flagging projects at risk of overrun."
    )
    await asyncio.sleep(0.25)

    # Per-project analysis events
    for project in projects:
        pname = project.get("project_name", "Unknown")
        pid = project.get("project_id", "")
        await emitter.emit_tool_call("analyze_job_costs", {"project": pname, "project_id": pid})
        await asyncio.sleep(0.12)

        finding = project.get("finding", "on_track")
        budget = project.get("budget_total", 0)
        actual = project.get("actual_spent", 0)
        pct = project.get("percent_complete", 0)
        await emitter.emit_tool_result(
            "analyze_job_costs",
            {"project": pname, "budget": budget, "actual": actual, "percent_complete": pct, "status": finding},
            f"{pname}: {finding.replace('_', ' ').title()} — ${actual:,.0f} of ${budget:,.0f} ({pct}% complete)",
        )
        await asyncio.sleep(0.1)

    await emitter.emit_tool_call("generate_dashboard", {"projects": len(projects)})
    await asyncio.sleep(0.15)

    model_plan = await llm_json_response(
        agent_id="progress_tracking",
        objective=(
            "Analyze construction project progress data and return a JSON dashboard report. Include:\n"
            "- kpi_summary: object with total_budget, total_spent, on_track_count, at_risk_count, behind_count\n"
            "- findings: array with one entry per project, each including:\n"
            "  project_id, project_name, finding (on_track/at_risk/behind_schedule),\n"
            "  message (1-2 sentence summary), create_task (boolean),\n"
            "  task_title (if create_task), task_priority (high/medium/low),\n"
            "  budget_total (number), actual_spent (number),\n"
            "  percent_complete (number), contract_value (number),\n"
            "  variance_dollar (budget_total * percent_complete/100 - actual_spent),\n"
            "  variance_percent (variance as % of budget),\n"
            "  status_color (green for on_track, amber for at_risk, red for behind_schedule),\n"
            "  recommendation (1 sentence action item for PM)\n"
            "Create tasks only for at_risk or behind_schedule projects."
        ),
        context_payload=payload,
        max_tokens=2500,
        temperature=0.1,
        validator=validate_progress_findings,
    )
    findings = model_plan.get("findings")
    if not isinstance(findings, list):
        raise RuntimeError("progress_tracking: model output missing findings[]")

    kpi = model_plan.get("kpi_summary", {})
    await emitter.emit_tool_result(
        "generate_dashboard",
        {"on_track": kpi.get("on_track_count", 0), "at_risk": kpi.get("at_risk_count", 0), "behind": kpi.get("behind_count", 0)},
        f"Dashboard built: {kpi.get('on_track_count', 0)} on track, "
        f"{kpi.get('at_risk_count', 0)} at risk, {kpi.get('behind_count', 0)} behind schedule.",
    )
    await asyncio.sleep(0.15)

    at_risk = 0
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        create_task = bool(finding.get("create_task"))
        if create_task:
            at_risk += 1
            title = str(finding.get("task_title", "")).strip() or f"PM follow-up: {finding.get('project_name', '')}"
            description = str(finding.get("message", "")).strip() or "Model flagged project risk."
            priority = str(finding.get("task_priority", "")).strip() or "high"
            await insert_internal_task(conn, "progress_tracking", title, description, priority)

    await emitter.emit_status_change(
        "complete",
        f"Reviewed {len(findings)} projects: {at_risk} need attention.",
    )
    # Return both kpi_summary and findings for the dashboard
    return {"kpi_summary": kpi, "findings": findings, "projects_data": projects}


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

    model_plan = await llm_json_response(
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

    model_plan = await llm_json_response(
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

    plan = await llm_json_response(
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


async def run_cost_estimator(conn, emitter: EventEmitter) -> dict[str, Any]:
    payload = await load_json("productivity_rates.json")
    project = payload.get("project", {})
    scope_items = payload.get("scope_items", [])
    labor_rate = payload.get("labor_rate", 68.0)

    # --- Phase 1: Scope Analysis ---
    await emitter.emit_status_change(
        "working", "Phase 1 of 5: Analyzing project scope"
    )
    await asyncio.sleep(0.2)

    await emitter.emit_reasoning(
        f"Reviewing takeoff data for {project.get('name', 'project')}. "
        f"Client: {project.get('client', 'N/A')}. "
        f"Found {len(scope_items)} line items across "
        f"{len(set(s.get('category','') for s in scope_items))} categories."
    )
    await asyncio.sleep(0.3)

    await emitter.emit_tool_call("load_takeoff_data", {
        "project": project.get("name", ""),
        "project_id": project.get("project_id", ""),
        "line_items": len(scope_items),
    })
    await asyncio.sleep(0.25)

    categories = {}
    for si in scope_items:
        cat = si.get("category", "Other")
        categories.setdefault(cat, []).append(si.get("item", ""))

    await emitter.emit_tool_result(
        "load_takeoff_data",
        {"categories": {k: len(v) for k, v in categories.items()}, "total_items": len(scope_items)},
        f"Loaded {len(scope_items)} scope items: " + ", ".join(f"{k} ({len(v)})" for k, v in categories.items()),
    )
    await asyncio.sleep(0.2)

    # --- Phase 2: Labor Calculation ---
    await emitter.emit_status_change(
        "working", "Phase 2 of 5: Calculating labor costs"
    )
    await asyncio.sleep(0.15)

    await emitter.emit_reasoning(
        f"Computing labor hours for each line item using production rates. "
        f"Crew labor rate: ${labor_rate:.2f}/hr fully burdened."
    )
    await asyncio.sleep(0.25)

    await emitter.emit_tool_call("calculate_labor_costs", {
        "labor_rate": labor_rate,
        "items": len(scope_items),
    })
    await asyncio.sleep(0.2)

    total_labor_hrs = sum(
        si.get("quantity", 0) * si.get("labor_hours_per_unit", 0) for si in scope_items
    )
    total_labor_cost = round(total_labor_hrs * labor_rate, 2)

    await emitter.emit_tool_result(
        "calculate_labor_costs",
        {"total_hours": round(total_labor_hrs, 1), "total_labor": total_labor_cost},
        f"Total labor: {round(total_labor_hrs, 1)} hours = ${total_labor_cost:,.0f}",
    )
    await asyncio.sleep(0.2)

    # --- Phase 3: Material Pricing ---
    await emitter.emit_status_change(
        "working", "Phase 3 of 5: Pricing materials"
    )
    await asyncio.sleep(0.15)

    await emitter.emit_tool_call("price_materials", {"source": "vendor_price_sheets"})
    await asyncio.sleep(0.2)

    total_material = sum(
        si.get("quantity", 0) * si.get("material_cost_per_unit", 0) for si in scope_items
    )

    await emitter.emit_tool_result(
        "price_materials",
        {"total_material": round(total_material, 2)},
        f"Total materials: ${round(total_material):,} from vendor price sheets",
    )
    await asyncio.sleep(0.2)

    # --- Phase 4: Equipment Costs ---
    await emitter.emit_status_change(
        "working", "Phase 4 of 5: Calculating equipment costs"
    )
    await asyncio.sleep(0.15)

    await emitter.emit_tool_call("calculate_equipment_costs", {"source": "internal_rates"})
    await asyncio.sleep(0.2)

    total_equipment = sum(
        si.get("quantity", 0) * si.get("equipment_cost_per_unit", 0) for si in scope_items
    )

    await emitter.emit_tool_result(
        "calculate_equipment_costs",
        {"total_equipment": round(total_equipment, 2)},
        f"Total equipment: ${round(total_equipment):,} based on internal ownership rates",
    )
    await asyncio.sleep(0.2)

    # --- Phase 5: Markups & Estimate Generation ---
    await emitter.emit_status_change(
        "working", "Phase 5 of 5: Applying markups and generating estimate"
    )
    await asyncio.sleep(0.15)

    direct_cost = total_labor_cost + total_material + total_equipment
    overhead_rate = payload.get("overhead_rate", 0.15)
    profit_rate = payload.get("profit_rate", 0.10)
    contingency_rate = payload.get("contingency_rate", 0.05)

    await emitter.emit_reasoning(
        f"Direct cost subtotal: ${direct_cost:,.0f}. "
        f"Applying markups — Overhead: {overhead_rate*100:.0f}%, "
        f"Profit: {profit_rate*100:.0f}%, "
        f"Contingency: {contingency_rate*100:.0f}%, "
        f"Bond: {payload.get('bond_rate', 0.015)*100:.1f}%, "
        f"Mobilization: {payload.get('mobilization_percent', 0.03)*100:.0f}%."
    )
    await asyncio.sleep(0.3)

    await emitter.emit_tool_call("apply_markups", {
        "direct_cost": round(direct_cost, 2),
        "overhead": f"{overhead_rate*100:.0f}%",
        "profit": f"{profit_rate*100:.0f}%",
        "contingency": f"{contingency_rate*100:.0f}%",
    })
    await asyncio.sleep(0.15)

    # --- LLM call to produce the full structured estimate ---
    result = await llm_json_response(
        agent_id="cost_estimator",
        objective=(
            "Build a detailed construction cost estimate. The data includes scope_items with "
            "quantities, labor rates, material costs, and equipment costs per unit. "
            "Return JSON with these keys:\n"
            "- line_items: array of objects, one per scope item, each with: "
            "item, category, quantity, unit, labor_hours, labor_cost, material_cost, "
            "equipment_cost, subtotal (labor+material+equipment)\n"
            "- category_subtotals: object mapping category name to subtotal dollar amount\n"
            "- direct_cost_total: sum of all line item subtotals\n"
            "- markups: object with keys overhead, profit, contingency, bond, mobilization — "
            "each a dollar amount calculated from direct_cost_total using the rates provided\n"
            "- grand_total: direct_cost_total plus all markups\n"
            "- assumptions: array of 4-6 strings (e.g. 'Normal soil conditions', "
            "'No rock excavation required', 'Standard working hours')\n"
            "- exclusions: array of 3-5 strings (e.g. 'Building construction', "
            "'Electrical and mechanical systems', 'Permit fees')\n"
            "Calculate costs precisely from the input data. labor_cost = quantity * labor_hours_per_unit * labor_rate. "
            "material_cost = quantity * material_cost_per_unit. equipment_cost = quantity * equipment_cost_per_unit."
        ),
        context_payload=payload,
        max_tokens=3000,
        temperature=0.1,
        validator=validate_cost_estimate,
    )

    grand_total = result.get("grand_total", 0)
    await emitter.emit_tool_result(
        "apply_markups",
        {"grand_total": grand_total},
        f"Estimate complete. Grand total: ${grand_total:,.0f}" if _is_number(grand_total) else "Estimate complete.",
    )
    await asyncio.sleep(0.15)

    await emitter.emit_tool_call("generate_estimate", {
        "project_id": project.get("project_id", ""),
        "line_items": len(result.get("line_items", [])),
        "grand_total": grand_total,
    })
    await asyncio.sleep(0.15)

    await emitter.emit_tool_result(
        "generate_estimate",
        {"status": "complete", "grand_total": grand_total},
        f"Estimate generated for {project.get('name', 'project')}: "
        f"{len(result.get('line_items', []))} line items, "
        f"${grand_total:,.0f} grand total." if _is_number(grand_total) else "Estimate generated.",
    )

    # Attach project metadata to result for frontend
    result["project"] = project
    await emitter.emit_status_change(
        "complete",
        f"Estimate for {project.get('name', 'project')}: ${grand_total:,.0f}" if _is_number(grand_total) else "Estimate complete.",
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

    plan = await llm_json_response(
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

        await emitter.emit(
            "complete",
            {
                "agent_id": agent_id,
                "output": output,
                "metrics": {
                    "cost": round(emitter.total_cost, 6),
                    "input_tokens": emitter.total_input_tokens,
                    "output_tokens": emitter.total_output_tokens,
                },
            },
            message=f"{agent_id} completed run",
        )

        tasks_completed = infer_completed_tasks(output)
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
