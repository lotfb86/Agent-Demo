#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.services.agent_runtime import run_agent_session
from api.services.session_manager import session_manager
from api.services.skills import append_training_instruction
from scripts.reset_demo import main as reset_main


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def run_agent(agent_id: str) -> dict[str, Any]:
    session = await session_manager.create(agent_id)
    result = await run_agent_session(agent_id, session.session_id)
    return result.output


def check_po_match_pre(output: dict[str, Any]) -> None:
    processed = output.get("processed")
    assert_true(isinstance(processed, list), "po_match pre: processed must be array")

    by_invoice = {row.get("invoice_number"): row for row in processed if isinstance(row, dict)}
    expected = {"INV-9001", "INV-9002", "INV-9003", "INV-9004"}
    assert_true(set(by_invoice.keys()) == expected, f"po_match pre: expected invoices {expected}, got {set(by_invoice.keys())}")

    assert_true(by_invoice["INV-9001"].get("status") == "matched", "INV-9001 must be matched")
    assert_true(by_invoice["INV-9002"].get("reason") == "price_variance", "INV-9002 must be price_variance")
    assert_true(
        by_invoice["INV-9003"].get("reason") in ("no_po_found", "no_matching_po", "no_po_match"),
        f"INV-9003 must be no-PO exception, got {by_invoice['INV-9003'].get('reason')}",
    )
    assert_true(
        by_invoice["INV-9004"].get("reason") in ("duplicate_po", "duplicate_payment", "duplicate_invoice"),
        f"INV-9004 must be duplicate exception, got {by_invoice['INV-9004'].get('reason')}",
    )


def check_po_match_post(output: dict[str, Any]) -> None:
    processed = output.get("processed")
    assert_true(isinstance(processed, list), "po_match post: processed must be array")
    assert_true(len(processed) == 1, f"po_match post: expected 1 invoice, got {len(processed)}")

    row = processed[0]
    assert_true(row.get("invoice_number") == "INV-9007", "po_match post: expected INV-9007")
    assert_true(row.get("reason") == "price_variance", "po_match post: INV-9007 must be price_variance")


def check_po_match_pm_email() -> None:
    conn = sqlite3.connect(ROOT / "data" / "rpmx.db")
    try:
        count = conn.execute(
            """
            SELECT COUNT(*) FROM communications
            WHERE agent_id='po_match' AND recipient='mrivera@rpmx.com'
            """
        ).fetchone()[0]
    finally:
        conn.close()
    assert_true(count >= 1, "po_match post: expected PM email to mrivera@rpmx.com")


def check_ar_followup(output: dict[str, Any]) -> None:
    results = output.get("results")
    assert_true(isinstance(results, list), "ar_followup: results must be array")
    assert_true(len(results) == 5, f"ar_followup: expected 5 results, got {len(results)}")

    actions = {row.get("customer"): row.get("action") for row in results if isinstance(row, dict)}
    expected_customers = {
        "Greenfield Development", "Summit Property Group",
        "Parkview Associates", "Riverside Municipal", "Oak Valley Homes",
    }
    assert_true(
        set(actions.keys()) == expected_customers,
        f"ar_followup: missing customers, got {set(actions.keys())}",
    )

    # Verify actions match aging bucket logic (allow reasonable LLM variation)
    assert_true(
        actions.get("Greenfield Development") == "polite_reminder",
        f"Greenfield (35 days) should be polite_reminder, got {actions.get('Greenfield Development')}",
    )
    assert_true(
        actions.get("Summit Property Group") == "firm_email_plus_internal_task",
        f"Summit (67 days) should be firm_email_plus_internal_task, got {actions.get('Summit Property Group')}",
    )
    assert_true(
        actions.get("Parkview Associates") == "escalated_to_collections",
        f"Parkview (95 days) should be escalated_to_collections, got {actions.get('Parkview Associates')}",
    )
    assert_true(
        actions.get("Riverside Municipal") == "skip_retainage",
        f"Riverside (retainage) should be skip_retainage, got {actions.get('Riverside Municipal')}",
    )
    assert_true(
        actions.get("Oak Valley Homes") == "no_action_within_terms",
        f"Oak Valley (15 days) should be no_action_within_terms, got {actions.get('Oak Valley Homes')}",
    )


def check_financial_reporting(output: dict[str, Any]) -> None:
    sections = output.get("sections")
    assert_true(isinstance(sections, list) and len(sections) >= 1, "financial_reporting: sections must be non-empty array")
    has_table = any(s.get("type") == "table" for s in sections if isinstance(s, dict))
    has_narrative = any(s.get("type") == "narrative" for s in sections if isinstance(s, dict))
    assert_true(has_table or has_narrative, "financial_reporting: expected at least one table or narrative section")


def check_vendor_compliance(output: dict[str, Any]) -> None:
    findings = output.get("findings")
    assert_true(isinstance(findings, list) and len(findings) >= 6, "vendor_compliance: expected at least 6 findings")
    issues_text = " ".join(str(row) for row in findings)
    assert_true("Tri-State Paving" in issues_text and "missing" in issues_text.lower(), "vendor_compliance: expected Tri-State missing W-9 finding")


def check_schedule_optimizer(output: dict[str, Any]) -> None:
    assignments = output.get("assignments")
    improvement = output.get("improvement_percent")
    assert_true(isinstance(assignments, dict) and len(assignments) == 3, "schedule_optimizer: expected 3 crew assignments")
    assert_true(isinstance(improvement, (int, float)) and float(improvement) >= 20, "schedule_optimizer: improvement should be >= 20%")


def check_progress_tracking(output: dict[str, Any]) -> None:
    findings = output.get("findings")
    assert_true(isinstance(findings, list) and len(findings) >= 5, "progress_tracking: expected >= 5 findings")


def check_maintenance_scheduler(output: dict[str, Any]) -> None:
    issues = output.get("issues")
    assert_true(isinstance(issues, list) and len(issues) >= 4, "maintenance_scheduler: expected >= 4 issues")


def check_training_compliance(output: dict[str, Any]) -> None:
    issues = output.get("issues")
    assert_true(isinstance(issues, list) and len(issues) >= 7, "training_compliance: expected >= 7 issues")


def check_onboarding(output: dict[str, Any]) -> None:
    hire = output.get("hire")
    checklist = output.get("checklist")
    assert_true(isinstance(hire, dict) and hire.get("name") == "Marcus Johnson", "onboarding: expected Marcus Johnson")
    assert_true(isinstance(checklist, dict), "onboarding: checklist required")


def check_cost_estimator(output: dict[str, Any]) -> None:
    line_items = output.get("line_items")
    assert_true(isinstance(line_items, list) and len(line_items) >= 15, "cost_estimator: expected ≥15 line items")
    grand_total = output.get("grand_total")
    assert_true(isinstance(grand_total, (int, float)) and grand_total > 400000, "cost_estimator: grand_total should be >$400K")
    cat_subs = output.get("category_subtotals")
    assert_true(isinstance(cat_subs, dict) and len(cat_subs) >= 4, "cost_estimator: expected ≥4 category subtotals")
    markups = output.get("markups")
    assert_true(isinstance(markups, dict) and "overhead" in markups, "cost_estimator: markups dict required")
    assumptions = output.get("assumptions")
    assert_true(isinstance(assumptions, list) and len(assumptions) >= 4, "cost_estimator: expected ≥4 assumptions")
    exclusions = output.get("exclusions")
    assert_true(isinstance(exclusions, list) and len(exclusions) >= 3, "cost_estimator: expected ≥3 exclusions")


def check_inquiry_router(output: dict[str, Any]) -> None:
    routes = output.get("routes")
    assert_true(isinstance(routes, list) and len(routes) == 3, "inquiry_router: expected exactly 3 routes")


async def run_iteration(index: int) -> None:
    print(f"\n=== Reliability Iteration {index} ===")
    reset_main()

    po_pre = await run_agent("po_match")
    check_po_match_pre(po_pre)

    append_training_instruction(
        "po_match",
        "When a price variance exceeds $1,000, send an email to the project manager with invoice number, PO number, variance amount, and variance percentage.",
    )
    po_post = await run_agent("po_match")
    check_po_match_post(po_post)
    check_po_match_pm_email()

    checks = [
        ("ar_followup", check_ar_followup),
        ("financial_reporting", check_financial_reporting),
        ("vendor_compliance", check_vendor_compliance),
        ("schedule_optimizer", check_schedule_optimizer),
        ("progress_tracking", check_progress_tracking),
        ("maintenance_scheduler", check_maintenance_scheduler),
        ("training_compliance", check_training_compliance),
        ("onboarding", check_onboarding),
        ("cost_estimator", check_cost_estimator),
        ("inquiry_router", check_inquiry_router),
    ]

    for agent_id, validator in checks:
        output = await run_agent(agent_id)
        validator(output)

    print(f"Iteration {index}: PASS")


async def main_async(runs: int) -> None:
    for idx in range(1, runs + 1):
        await run_iteration(idx)
    print(f"\nAll reliability checks passed ({runs} run(s)).")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run multi-pass model reliability checks")
    parser.add_argument("--runs", type=int, default=5, help="Number of full demo iterations")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(main_async(args.runs))


if __name__ == "__main__":
    main()
