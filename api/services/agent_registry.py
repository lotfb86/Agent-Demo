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
        description="Comprehensive financial analysis for an $850M construction company — P&L, job costing, AR aging, backlog, cash flow, margin trends, budget variance, and KPI dashboards with charts and executive narrative.",
        tools=(
            "classify_intent", "query_gl_data", "query_job_data", "query_ar_aging",
            "query_backlog", "compute_metrics", "generate_report", "load_financial_data",
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
        description="Performs proposal-vs-actual analysis with earned value metrics, labor productivity tracking, cost code variance, and schedule milestone analysis for active construction projects.",
        tools=(
            "load_project_data", "analyze_project", "compute_earned_value",
            "analyze_labor_productivity", "generate_analysis",
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
        description="Receives construction takeoffs, prices each scope category against the cost database, applies standard markups, and generates professional cost proposals.",
        tools=(
            "load_takeoff_data", "lookup_cost_database", "price_category",
            "apply_markups", "generate_proposal",
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
