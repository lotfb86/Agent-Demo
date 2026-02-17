from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentMeta:
    id: str
    name: str
    department: str
    workspace_type: str
    description: str = ""
    tools: tuple[str, ...] = ()


AGENTS: list[AgentMeta] = [
    AgentMeta(
        "po_match", "PO Match Agent", "Accounts Payable", "invoice",
        description="Matches incoming invoices to purchase orders, assigns GL coding, detects duplicates, and posts to Vista.",
        tools=(
            "read_invoice", "search_purchase_orders", "select_po", "check_duplicate",
            "assign_coding", "mark_complete", "post_to_vista", "flag_exception",
            "get_project_details", "send_notification", "complete_invoice",
        ),
    ),
    AgentMeta(
        "ar_followup", "AR Follow-Up Agent", "Accounts Receivable", "email",
        description="Reviews aging receivables and determines collection actions from polite reminders to escalation.",
        tools=(
            "scan_ar_aging", "determine_action", "send_collection_email",
            "create_internal_task", "escalate_account",
        ),
    ),
    AgentMeta(
        "financial_reporting", "Financial Reporting Agent", "General Accounting", "report",
        description="Generates P&L reports, expense analyses, and period comparisons from Vista GL data.",
        tools=(
            "classify_intent", "connect_vista_api", "query_financial_data",
            "aggregate_results", "generate_report", "compile_narrative", "load_financial_data",
        ),
    ),
    AgentMeta(
        "vendor_compliance", "Vendor Compliance Monitor", "Procurement", "table",
        description="Scans vendor records for missing documents, expiring insurance, and contract renewals.",
        tools=(
            "scan_vendor_records", "check_vendor", "send_renewal_request", "create_compliance_task",
        ),
    ),
    AgentMeta(
        "schedule_optimizer", "Schedule Optimizer", "Scheduling", "map",
        description="Assigns landscaping crews to jobs by skill and geographic proximity to reduce drive time.",
        tools=(
            "load_dispatch_data", "optimize_routes", "assign_crew",
        ),
    ),
    AgentMeta(
        "progress_tracking", "Progress Tracking Agent", "Project Management", "table",
        description="Analyzes project schedule and budget indicators, flags risk, and recommends actions.",
        tools=(
            "load_project_data", "analyze_project_health", "track_project_health",
        ),
    ),
    AgentMeta(
        "maintenance_scheduler", "Maintenance Scheduler", "Fleet & Equipment", "table",
        description="Monitors fleet service due dates and generates timely work orders with priority levels.",
        tools=(
            "scan_maintenance_records", "inspect_unit", "schedule_maintenance",
        ),
    ),
    AgentMeta(
        "training_compliance", "Training Compliance Agent", "Safety", "table",
        description="Ensures employee certifications and orientation requirements are current before site assignment.",
        tools=(
            "audit_employee_certifications", "check_employee", "create_compliance_task",
        ),
    ),
    AgentMeta(
        "onboarding", "Onboarding Agent", "Human Resources", "checklist",
        description="Orchestrates pre-start tasks so new hires are work-ready on day one.",
        tools=(
            "load_new_hire", "prepare_documents", "prepare_training",
            "prepare_equipment", "send_welcome_email",
        ),
    ),
    AgentMeta(
        "cost_estimator", "Cost Estimator", "Estimating", "report",
        description="Produces defendable contract pricing using productivity rates, overhead, and target margin.",
        tools=(
            "load_takeoff_data", "apply_labor_rates", "apply_markups", "generate_estimate",
        ),
    ),
    AgentMeta(
        "inquiry_router", "Inquiry Router", "Customer Service", "email",
        description="Classifies inbound customer messages and routes to the correct department with extracted details.",
        tools=(
            "classify_inquiry", "route_email",
        ),
    ),
]

BY_ID = {agent.id: agent for agent in AGENTS}
