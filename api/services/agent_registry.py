from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentMeta:
    id: str
    name: str
    department: str
    workspace_type: str


AGENTS: list[AgentMeta] = [
    AgentMeta("po_match", "PO Match Agent", "Accounts Payable", "invoice"),
    AgentMeta("ar_followup", "AR Follow-Up Agent", "Accounts Receivable", "email"),
    AgentMeta("financial_reporting", "Financial Reporting Agent", "General Accounting", "report"),
    AgentMeta("vendor_compliance", "Vendor Compliance Monitor", "Procurement", "table"),
    AgentMeta("schedule_optimizer", "Schedule Optimizer", "Scheduling", "map"),
    AgentMeta("progress_tracking", "Progress Tracking Agent", "Project Management", "table"),
    AgentMeta("maintenance_scheduler", "Maintenance Scheduler", "Fleet & Equipment", "table"),
    AgentMeta("training_compliance", "Training Compliance Agent", "Safety", "table"),
    AgentMeta("onboarding", "Onboarding Agent", "Human Resources", "checklist"),
    AgentMeta("cost_estimator", "Cost Estimator", "Estimating", "report"),
    AgentMeta("inquiry_router", "Inquiry Router", "Customer Service", "email"),
]

BY_ID = {agent.id: agent for agent in AGENTS}
