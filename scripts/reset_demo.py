#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import os
import random
import shutil
import sqlite3
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
JSON_DIR = DATA_DIR / "json"
INVOICE_DIR = DATA_DIR / "invoices"

DEMO_DATE = date(2026, 2, 13)
RANDOM_SEED = 42


@dataclass(frozen=True)
class InvoiceLine:
    description: str
    quantity: float
    unit_price: float

    @property
    def line_total(self) -> float:
        return round(self.quantity * self.unit_price, 2)


@dataclass(frozen=True)
class DemoInvoice:
    invoice_number: str
    vendor: str
    invoice_date: date
    amount: float
    po_reference: Optional[str]
    payment_terms: str
    lines: list[InvoiceLine]


DEMO_INVOICES: list[DemoInvoice] = [
    DemoInvoice(
        invoice_number="INV-9001",
        vendor="Martin Materials LLC",
        invoice_date=date(2026, 2, 5),
        amount=12450.00,
        po_reference="PO-2024-0892",
        payment_terms="Net 30",
        lines=[
            InvoiceLine("Gravel", 500, 18.90),
            InvoiceLine("Sand", 200, 15.00),
        ],
    ),
    DemoInvoice(
        invoice_number="INV-9002",
        vendor="Southeast Grading Co.",
        invoice_date=date(2026, 2, 6),
        amount=47250.00,
        po_reference="PO-2024-0756",
        payment_terms="Net 30",
        lines=[InvoiceLine("Site grading Phase 2 — lump sum", 1, 47250.00)],
    ),
    DemoInvoice(
        invoice_number="INV-9003",
        vendor="Quick Stop Fuel & Supply",
        invoice_date=date(2026, 2, 6),
        amount=387.50,
        po_reference=None,
        payment_terms="Net 30",
        lines=[InvoiceLine("Diesel", 250, 1.55)],
    ),
    DemoInvoice(
        invoice_number="INV-9004",
        vendor="Blue Ridge Equipment Rental",
        invoice_date=date(2026, 2, 7),
        amount=8200.00,
        po_reference="PO-2024-1102",
        payment_terms="Net 30",
        lines=[InvoiceLine("CAT 320 Excavator rental (2 weeks)", 2, 4100.00)],
    ),
    DemoInvoice(
        invoice_number="INV-9005",
        vendor="Consolidated Concrete Inc.",
        invoice_date=date(2026, 2, 8),
        amount=6780.00,
        po_reference=None,
        payment_terms="Net 30",
        lines=[InvoiceLine("Ready-mix concrete", 60, 113.00)],
    ),
    DemoInvoice(
        invoice_number="INV-9006",
        vendor="Martin Materials LLC",
        invoice_date=date(2026, 2, 8),
        amount=12450.00,
        po_reference="PO-2024-0892",
        payment_terms="Net 30",
        lines=[
            InvoiceLine("Gravel", 500, 18.90),
            InvoiceLine("Sand", 200, 15.00),
        ],
    ),
    DemoInvoice(
        invoice_number="INV-9007",
        vendor="Piedmont Lumber & Supply",
        invoice_date=date(2026, 2, 9),
        amount=14820.00,
        po_reference="PO-2024-1187",
        payment_terms="Net 30",
        lines=[InvoiceLine("Treated lumber 4x6x16", 400, 37.05)],
    ),
]

AGENTS = [
    "po_match",
    "ar_followup",
    "financial_reporting",
    "vendor_compliance",
    "schedule_optimizer",
    "progress_tracking",
    "maintenance_scheduler",
    "training_compliance",
    "onboarding",
    "cost_estimator",
    "inquiry_router",
]

PROJECTS = [
    {
        "id": "MR-2024-015",
        "name": "Maple Ridge Site Development",
        "division_id": "SD",
        "budget_text": "$1,240,000",
        "percent_complete": 48,
        "pm_name": "James Callahan",
        "pm_email": "jcallahan@rpmx.com",
    },
    {
        "id": "EX-2024-022",
        "name": "Highway 9 Interchange Grading",
        "division_id": "EX",
        "budget_text": "$2,180,000",
        "percent_complete": 60,
        "pm_name": "Sarah Whitfield",
        "pm_email": "swhitfield@rpmx.com",
    },
    {
        "id": "ES-2024-009",
        "name": "Elm Street Retaining Wall",
        "division_id": "RW",
        "budget_text": "$485,000",
        "percent_complete": 72,
        "pm_name": "Marcus Rivera",
        "pm_email": "mrivera@rpmx.com",
    },
    {
        "id": "RC-2024-011",
        "name": "County Road 42 Resurfacing",
        "division_id": "RC",
        "budget_text": "$890,000",
        "percent_complete": 85,
        "pm_name": "James Callahan",
        "pm_email": "jcallahan@rpmx.com",
    },
    {
        "id": "LM-2024-003",
        "name": "Greenfield Business Park Maint.",
        "division_id": "LM",
        "budget_text": "$156,000/yr",
        "percent_complete": None,
        "pm_name": "Tyler Brandt",
        "pm_email": "tbrandt@rpmx.com",
    },
    {
        "id": "SD-2024-018",
        "name": "Summit Office Park Phase 2",
        "division_id": "SD",
        "budget_text": "$1,650,000",
        "percent_complete": 35,
        "pm_name": "Sarah Whitfield",
        "pm_email": "swhitfield@rpmx.com",
    },
    {
        "id": "EX-2024-027",
        "name": "Riverdale Flood Mitigation",
        "division_id": "EX",
        "budget_text": "$3,200,000",
        "percent_complete": 22,
        "pm_name": "Marcus Rivera",
        "pm_email": "mrivera@rpmx.com",
    },
    {
        "id": "CR-2024-008",
        "name": "Clearwater Reservoir Access Road",
        "division_id": "RC",
        "budget_text": "$720,000",
        "percent_complete": 95,
        "pm_name": "Tyler Brandt",
        "pm_email": "tbrandt@rpmx.com",
    },
]

CRITICAL_PURCHASE_ORDERS = [
    {
        "po_number": "PO-2024-0892",
        "vendor": "Martin Materials LLC",
        "amount": 12450.00,
        "job_id": "MR-2024-015",
        "gl_code": "5100",
    },
    {
        "po_number": "PO-2024-0756",
        "vendor": "Southeast Grading Co.",
        "amount": 45000.00,
        "job_id": "EX-2024-022",
        "gl_code": "5300",
    },
    {
        "po_number": "PO-2024-1102",
        "vendor": "Blue Ridge Equipment Rental",
        "amount": 8200.00,
        "job_id": "ES-2024-009",
        "gl_code": "5200",
    },
    {
        "po_number": "PO-2024-0998",
        "vendor": "Consolidated Concrete Inc.",
        "amount": 6780.00,
        "job_id": "MR-2024-015",
        "gl_code": "5100",
    },
    {
        "po_number": "PO-2024-1187",
        "vendor": "Piedmont Lumber & Supply",
        "amount": 13200.00,
        "job_id": "ES-2024-009",
        "gl_code": "5100",
    },
]

CRITICAL_VENDOR_RULES = {
    "Southeast Grading Co.": {
        "insurance_expiry": "2026-02-24",
        "contract_expiry": "2026-10-15",
        "w9_on_file": 1,
        "notes": "Insurance renewal required in 14 days.",
    },
    "Piedmont Lumber & Supply": {
        "insurance_expiry": "2026-02-18",
        "contract_expiry": "2026-11-01",
        "w9_on_file": 1,
        "notes": "Insurance renewal required this week.",
    },
    "Summit Environmental Services": {
        "insurance_expiry": "2026-02-20",
        "contract_expiry": "2026-09-30",
        "w9_on_file": 1,
        "notes": "Insurance renewal required in 7 days.",
    },
    "Carolina Steel Fabricators": {
        "insurance_expiry": "2026-01-28",
        "contract_expiry": "2026-12-31",
        "w9_on_file": 1,
        "notes": "Insurance expired; urgent hold recommendation.",
    },
    "Tri-State Paving": {
        "insurance_expiry": "2026-08-30",
        "contract_expiry": "2026-03-31",
        "w9_on_file": 0,
        "notes": "Missing W-9 and contract renewal review needed.",
    },
    "Valley Forge Welding": {
        "insurance_expiry": "2026-09-20",
        "contract_expiry": "2026-03-15",
        "w9_on_file": 1,
        "notes": "Contract renewal in 30 days.",
    },
}

DEMO_VENDORS = [
    "Martin Materials LLC",
    "Southeast Grading Co.",
    "Quick Stop Fuel & Supply",
    "Blue Ridge Equipment Rental",
    "Consolidated Concrete Inc.",
    "Piedmont Lumber & Supply",
    "Summit Environmental Services",
    "Carolina Steel Fabricators",
    "Tri-State Paving",
    "Valley Forge Welding",
    "Raleigh Asphalt Partners",
]

BACKGROUND_LOCATIONS = [
    "Raleigh",
    "Durham",
    "Cary",
    "Apex",
    "Wake Forest",
    "Garner",
    "Knightdale",
    "Holly Springs",
    "Morrisville",
    "Fuquay",
    "Chapel Hill",
    "Clayton",
    "Burlington",
    "Sanford",
]
BACKGROUND_TRADES = [
    "Concrete",
    "Hauling",
    "Earthworks",
    "Pipe",
    "Stone",
    "Landscape",
    "Welding",
    "Demolition",
    "Utility",
    "Paving",
    "Drilling",
    "Rebar",
    "Masonry",
    "Hydroseed",
]
ENTITY_TYPES = ["LLC", "Inc.", "Group", "Services", "Co.", "Supply"]


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def db_path() -> Path:
    configured = os.getenv("DATABASE_PATH")
    if configured:
        path = Path(configured)
        if not path.is_absolute():
            path = BASE_DIR / path
        return path
    return DATA_DIR / "rpmx.db"


def ensure_dirs() -> None:
    JSON_DIR.mkdir(parents=True, exist_ok=True)
    INVOICE_DIR.mkdir(parents=True, exist_ok=True)


def load_sql(conn: sqlite3.Connection, path: Path) -> None:
    conn.executescript(path.read_text())


def create_vendor_payload() -> list[dict[str, Any]]:
    random.seed(RANDOM_SEED)
    payload: list[dict[str, Any]] = []

    for vendor in DEMO_VENDORS:
        rules = CRITICAL_VENDOR_RULES.get(vendor)
        payload.append(
            {
                "name": vendor,
                "email": f"{vendor.lower().replace(' ', '.').replace('&', 'and').replace('.', '').replace('-', '')[:20]}@vendors.rpmx.com",
                "insurance_expiry": rules["insurance_expiry"] if rules else "2026-12-31",
                "contract_expiry": rules["contract_expiry"] if rules else "2026-11-30",
                "w9_on_file": rules["w9_on_file"] if rules else 1,
                "notes": rules["notes"] if rules else "Compliant background vendor.",
            }
        )

    seen = {v["name"] for v in payload}
    while len(payload) < 50:
        loc = random.choice(BACKGROUND_LOCATIONS)
        trade = random.choice(BACKGROUND_TRADES)
        entity = random.choice(ENTITY_TYPES)
        name = f"{loc} {trade} {entity}"
        if name in seen:
            continue
        seen.add(name)
        payload.append(
            {
                "name": name,
                "email": f"{loc.lower()}.{trade.lower()}@vendors.rpmx.com".replace(" ", ""),
                "insurance_expiry": (DEMO_DATE + timedelta(days=random.randint(120, 330))).isoformat(),
                "contract_expiry": (DEMO_DATE + timedelta(days=random.randint(150, 360))).isoformat(),
                "w9_on_file": 1,
                "notes": "Compliant background vendor.",
            }
        )

    return payload


def create_background_projects() -> list[dict[str, Any]]:
    random.seed(RANDOM_SEED)
    divisions = ["EX", "RC", "SD", "LM", "RW"]
    names = [
        "North Creek Utility Rehab",
        "Westpoint Earthwork Package",
        "Redwood Commercial Grade",
        "Briarwood Retaining Segment",
        "Pine Hollow Streetscape",
        "Stonebridge Channel Repair",
        "Highland Yard Expansion",
        "Lakeview Access Improvement",
        "Arden Park Beautification",
        "Kingsmill Drainage Phase",
        "Hampton Freight Yard",
        "Summerset Median Overhaul",
        "Cedar Run Sidewalk Repairs",
        "Ironwood Slope Stabilization",
        "Wilcrest Culvert Replacement",
        "Oakline Campus Grounds",
        "Trinity Lot Regrade",
        "Wellington Barrier Retrofit",
        "Riverbend Landscape Contract",
        "Carson Interchange Drainage",
        "Mayfair Sports Complex Grounds",
        "Mason Ridge Utility Tie-in",
    ]

    rows: list[dict[str, Any]] = []
    for idx, name in enumerate(names, start=1):
        div = random.choice(divisions)
        budget = random.randint(280000, 3200000)
        pct = round(random.uniform(8, 98), 1)
        rows.append(
            {
                "id": f"BG-2025-{idx:03d}",
                "name": name,
                "division_id": div,
                "budget_text": f"${budget:,.0f}",
                "percent_complete": pct,
                "pm_name": random.choice(["James Callahan", "Sarah Whitfield", "Marcus Rivera", "Tyler Brandt"]),
                "pm_email": random.choice(
                    [
                        "jcallahan@rpmx.com",
                        "swhitfield@rpmx.com",
                        "mrivera@rpmx.com",
                        "tbrandt@rpmx.com",
                    ]
                ),
            }
        )
    return rows


def make_po_number(index: int) -> str:
    return f"PO-2025-{index:04d}"


def make_invoice_number(index: int) -> str:
    return f"INV-BG-{index:04d}"


def render_invoice_pdf(invoice: DemoInvoice, vendor_meta: dict[str, dict[str, Any]]) -> Path:
    vendor_info = vendor_meta[invoice.vendor]
    target = INVOICE_DIR / f"{invoice.invoice_number}.pdf"
    c = canvas.Canvas(str(target), pagesize=LETTER)
    width, height = LETTER

    c.setFont("Helvetica-Bold", 16)
    c.drawString(0.75 * inch, height - 0.85 * inch, invoice.vendor)
    c.setFont("Helvetica", 10)
    c.drawString(0.75 * inch, height - 1.10 * inch, "1200 Vendor Park Drive")
    c.drawString(0.75 * inch, height - 1.28 * inch, "Raleigh, NC 27609")
    c.drawString(0.75 * inch, height - 1.46 * inch, f"billing@{invoice.vendor.lower().replace(' ', '').replace('&', 'and').replace('.', '')}.com")

    c.setFont("Helvetica-Bold", 24)
    c.drawRightString(width - 0.75 * inch, height - 0.90 * inch, "Invoice")

    c.setFont("Helvetica", 10)
    c.drawRightString(width - 0.75 * inch, height - 1.20 * inch, f"Invoice #: {invoice.invoice_number}")
    c.drawRightString(width - 0.75 * inch, height - 1.38 * inch, f"Date: {invoice.invoice_date.isoformat()}")
    if invoice.po_reference:
        c.drawRightString(width - 0.75 * inch, height - 1.56 * inch, f"PO Ref: {invoice.po_reference}")

    c.setStrokeColor(colors.HexColor("#1f2937"))
    c.setLineWidth(1)
    c.rect(0.75 * inch, height - 2.45 * inch, 3.3 * inch, 0.9 * inch, stroke=1, fill=0)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(0.85 * inch, height - 1.72 * inch, "Bill To")
    c.setFont("Helvetica", 9.5)
    c.drawString(0.85 * inch, height - 1.92 * inch, "RPMX Construction")
    c.drawString(0.85 * inch, height - 2.08 * inch, "4200 Westgate Blvd, Suite 300")
    c.drawString(0.85 * inch, height - 2.24 * inch, "Raleigh, NC 27607")

    table_top = height - 3.0 * inch
    c.setFillColor(colors.HexColor("#e5e7eb"))
    c.rect(0.75 * inch, table_top, width - 1.5 * inch, 0.32 * inch, stroke=0, fill=1)
    c.setFillColor(colors.black)

    headers = ["Description", "Qty", "Unit Price", "Line Total"]
    x_positions = [0.85 * inch, 4.75 * inch, 5.55 * inch, 6.60 * inch]
    c.setFont("Helvetica-Bold", 9)
    for header, x in zip(headers, x_positions):
        c.drawString(x, table_top + 0.12 * inch, header)

    y = table_top - 0.25 * inch
    c.setFont("Helvetica", 9)
    subtotal = 0.0
    for line in invoice.lines:
        subtotal += line.line_total
        c.drawString(0.85 * inch, y, line.description)
        c.drawRightString(5.20 * inch, y, f"{line.quantity:,.2f}".rstrip("0").rstrip("."))
        c.drawRightString(6.20 * inch, y, f"${line.unit_price:,.2f}")
        c.drawRightString(7.55 * inch, y, f"${line.line_total:,.2f}")
        y -= 0.22 * inch

    y -= 0.16 * inch
    c.setLineWidth(0.7)
    c.line(5.55 * inch, y, 7.55 * inch, y)
    y -= 0.20 * inch

    c.setFont("Helvetica", 10)
    c.drawRightString(6.80 * inch, y, "Subtotal:")
    c.drawRightString(7.55 * inch, y, f"${subtotal:,.2f}")
    y -= 0.20 * inch
    c.drawRightString(6.80 * inch, y, "Total:")
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(7.55 * inch, y, f"${invoice.amount:,.2f}")

    c.setFont("Helvetica", 9)
    c.drawString(0.85 * inch, 1.15 * inch, f"Payment Terms: {invoice.payment_terms}")
    c.drawString(0.85 * inch, 0.95 * inch, f"Vendor Contact: {vendor_info['email']}")
    c.drawString(0.85 * inch, 0.75 * inch, "Please include invoice number on all remittances.")

    c.showPage()
    c.save()
    return target


def haversine_minutes(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    radius_miles = 3958.8
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    miles = radius_miles * c
    return max(6, int((miles / 32.0) * 60) + 4)


def build_dispatch_dataset() -> dict[str, Any]:
    yard = {"id": "YARD", "name": "RPMX Dispatch Yard", "lat": 35.7915, "lng": -78.6382}
    crews = [
        {"id": "crew_a", "name": "Crew A", "skills": ["tree_work", "general_maintenance"]},
        {"id": "crew_b", "name": "Crew B", "skills": ["heavy_mowing", "general_maintenance"]},
        {"id": "crew_c", "name": "Crew C", "skills": ["general_maintenance"]},
    ]
    jobs = [
        {"id": "JOB-1001", "name": "Wake Forest Medical Plaza", "zone": "North Raleigh/Wake Forest", "lat": 35.9801, "lng": -78.5097, "required_skill": "tree_work"},
        {"id": "JOB-1002", "name": "Falls Point Retail", "zone": "North Raleigh/Wake Forest", "lat": 35.9104, "lng": -78.5854, "required_skill": "heavy_mowing"},
        {"id": "JOB-1003", "name": "Capital Hills HOA", "zone": "North Raleigh/Wake Forest", "lat": 35.9045, "lng": -78.5407, "required_skill": "general_maintenance"},
        {"id": "JOB-1004", "name": "Cary Commerce Park", "zone": "Cary/Apex", "lat": 35.7846, "lng": -78.7811, "required_skill": "heavy_mowing"},
        {"id": "JOB-1005", "name": "Apex Professional Center", "zone": "Cary/Apex", "lat": 35.7325, "lng": -78.8503, "required_skill": "general_maintenance"},
        {"id": "JOB-1006", "name": "West Cary Tech Campus", "zone": "Cary/Apex", "lat": 35.8380, "lng": -78.8551, "required_skill": "tree_work"},
        {"id": "JOB-1007", "name": "RTP South Labs", "zone": "South Durham/RTP", "lat": 35.8931, "lng": -78.8636, "required_skill": "general_maintenance"},
        {"id": "JOB-1008", "name": "Herndon Office Commons", "zone": "South Durham/RTP", "lat": 35.9041, "lng": -78.9037, "required_skill": "heavy_mowing"},
        {"id": "JOB-1009", "name": "South Durham Schools", "zone": "South Durham/RTP", "lat": 35.9324, "lng": -78.9105, "required_skill": "general_maintenance"},
        {"id": "JOB-1010", "name": "Brier Creek Plaza", "zone": "North Raleigh/Wake Forest", "lat": 35.9055, "lng": -78.7879, "required_skill": "tree_work"},
        {"id": "JOB-1011", "name": "Apex West Industrial", "zone": "Cary/Apex", "lat": 35.7483, "lng": -78.9204, "required_skill": "general_maintenance"},
        {"id": "JOB-1012", "name": "Durham South Retail", "zone": "South Durham/RTP", "lat": 35.9653, "lng": -78.9513, "required_skill": "general_maintenance"},
    ]

    locations = [yard, *jobs]
    travel_times = []
    for origin in locations:
        for dest in locations:
            minutes = 0 if origin["id"] == dest["id"] else haversine_minutes(origin["lat"], origin["lng"], dest["lat"], dest["lng"])
            travel_times.append({"from": origin["id"], "to": dest["id"], "minutes": minutes})

    return {
        "yard": yard,
        "crews": crews,
        "jobs": jobs,
        "travel_times": travel_times,
        "unoptimized_drive_minutes": 148,
        "optimized_drive_minutes": 115,
        "improvement_percent": 22.3,
    }


def build_progress_dataset() -> dict[str, Any]:
    return {
        "projects": [
            {
                "project_id": "MR-2024-015",
                "project_name": "Maple Ridge Site Development",
                "budget_used_percent": 45,
                "percent_complete": 48,
                "finding": "on_track",
                "message": "On track. Budget 45% used, 48% complete.",
            },
            {
                "project_id": "EX-2024-022",
                "project_name": "Highway 9 Interchange",
                "budget_used_percent": 78,
                "percent_complete": 60,
                "finding": "at_risk",
                "projected_overrun": 18400,
                "message": "Budget 78% used but only 60% complete. Projected overrun $18,400.",
            },
            {
                "project_id": "SD-2024-018",
                "project_name": "Summit Office Phase 2",
                "days_behind": 3,
                "productivity_gap_percent": 15,
                "finding": "behind_schedule",
                "message": "3 days behind schedule and productivity 15% below estimate.",
            },
            {
                "project_id": "RC-2024-011",
                "project_name": "County Road 42 Resurfacing",
                "days_ahead": 2,
                "finding": "on_track",
                "message": "On track and 2 days ahead of schedule.",
            },
            {
                "project_id": "EX-2024-027",
                "project_name": "Riverdale Flood Mitigation",
                "finding": "at_risk",
                "change_order": "CO-045",
                "change_order_amount": 256000,
                "message": "At risk pending CO-045 approval. Within budget if approved.",
            },
        ]
    }


def build_equipment_dataset() -> dict[str, Any]:
    items: list[dict[str, Any]] = [
        {
            "unit": "2022 Ford F-550 #107",
            "issue": "Oil change due in 2 days",
            "action": "Generate work order and find downtime window.",
            "severity": "medium",
        },
        {
            "unit": "2021 Kenworth T370 #112",
            "issue": "Oil change due in 3 days",
            "action": "Generate work order and schedule low-utilization afternoon.",
            "severity": "medium",
        },
        {
            "unit": "2020 CAT 320 #319",
            "issue": "DOT inspection due in 5 days",
            "action": "Schedule inspection and notify ops manager.",
            "severity": "high",
        },
        {
            "unit": "2019 Peterbilt 348 #223",
            "issue": "Brake inspection overdue by 6 days",
            "action": "URGENT: remove from service immediately.",
            "severity": "critical",
        },
    ]

    random.seed(RANDOM_SEED)
    makes = ["CAT", "John Deere", "Ford", "Chevrolet", "Mack", "Komatsu"]
    models = ["320", "210", "F-750", "T470", "LCF", "PC210"]
    for idx in range(26):
        unit_number = 300 + idx
        year = 2018 + (idx % 7)
        make = random.choice(makes)
        model = random.choice(models)
        items.append(
            {
                "unit": f"{year} {make} {model} #{unit_number}",
                "issue": "No maintenance due",
                "action": "No action required.",
                "severity": "none",
            }
        )

    return {"equipment": items}


def build_hr_dataset() -> dict[str, Any]:
    employees = [
        {
            "name": "Jake Morrison",
            "status": "expiring_osha",
            "detail": "OSHA 10-Hour expires 2026-02-28",
        },
        {
            "name": "Luis Herrera",
            "status": "expiring_osha",
            "detail": "OSHA 10-Hour expires 2026-03-05",
        },
        {
            "name": "Tommy Pham",
            "status": "expiring_osha",
            "detail": "OSHA 10-Hour expires 2026-02-25",
        },
        {
            "name": "Ana Reyes",
            "status": "expiring_osha",
            "detail": "OSHA 10-Hour expires 2026-03-01",
        },
        {
            "name": "Mike Kowalski",
            "status": "missing_cert",
            "detail": "Missing Skid Steer Operator certification",
        },
        {
            "name": "Chris Tate",
            "status": "missing_cert",
            "detail": "Missing Excavator Spotter certification",
        },
        {
            "name": "Brandon Wells",
            "status": "missing_orientation",
            "detail": "Start date 2026-02-10 and orientation safety training incomplete",
        },
    ]

    random.seed(RANDOM_SEED)
    first_names = [
        "Evan",
        "Noah",
        "Mason",
        "Lucas",
        "Owen",
        "Liam",
        "Aiden",
        "Caleb",
        "Levi",
        "Wyatt",
        "Chase",
        "Cole",
        "Brett",
        "Isaac",
        "Dylan",
    ]
    last_names = [
        "Howard",
        "Bennett",
        "Lopez",
        "Davis",
        "Turner",
        "Fletcher",
        "Reid",
        "Graham",
        "Soto",
        "Parker",
        "Mills",
        "Ortega",
        "Murray",
        "Flores",
        "Morgan",
    ]

    seen = {item["name"] for item in employees}
    while len(employees) < 40:
        name = f"{random.choice(first_names)} {random.choice(last_names)}"
        if name in seen:
            continue
        seen.add(name)
        employees.append(
            {
                "name": name,
                "status": "compliant",
                "detail": "All required safety and equipment certifications current",
            }
        )

    return {"employees": employees}


def build_onboarding_dataset() -> dict[str, Any]:
    return {
        "new_hire": {
            "name": "Marcus Johnson",
            "role": "Equipment Operator",
            "division": "Excavation",
            "start_date": "2026-02-24",
            "hiring_manager": "Sarah Whitfield",
            "documents_required": ["W-4", "I-9", "Direct Deposit", "Handbook Acknowledgment"],
            "training_required": ["OSHA 10-Hour", "Equipment Operator Cert", "Site Safety Orientation"],
            "equipment_needs": ["Hard hat", "Safety vest", "Steel-toe boots", "Radio"],
        }
    }


def build_productivity_dataset() -> dict[str, Any]:
    return {
        "contract_input": {
            "turf_acres": 2.5,
            "edging_linear_feet": 1200,
            "shrubs": 45,
            "trees": 12,
            "service_window": "April-October",
            "visits": 28,
            "distance_miles": 22,
            "overhead_rate": 0.15,
            "target_margin": 0.25,
        },
        "productivity_rates": {
            "mowing_hours_per_acre": 0.95,
            "edging_hours_per_100ft": 0.22,
            "shrub_hours_each": 0.08,
            "tree_hours_each": 0.14,
            "labor_rate_per_hour": 62.0,
            "vehicle_cost_per_visit": 46.0,
            "materials_per_visit": 18.0,
        },
        "expected_output": {
            "per_visit": 399,
            "monthly": 694,
            "annual": 9715,
        },
    }


def build_inquiry_dataset() -> dict[str, Any]:
    return {
        "emails": [
            {
                "from": "accounts@greenfield.com",
                "subject": "Invoice #7744 payment status",
                "body": "Checking status on Invoice #7744. Please advise remittance timeline.",
                "expected_route": "Accounts Receivable",
            },
            {
                "from": "facilities@northhillsmed.com",
                "subject": "Missed weekly maintenance",
                "body": "Our weekly maintenance was missed yesterday at North Hills Medical campus. Grass is overgrown and the client is unhappy. Please send a crew ASAP.",
                "expected_route": "Dispatch",
            },
            {
                "from": "jreynolds@summitoffice.com",
                "subject": "Quote for additional landscaping",
                "body": "Need a quote for expanded landscape scope at Summit Office Park. Adding irrigation to the east courtyard and new plantings along the main entrance.",
                "expected_route": "Estimating",
            },
            {
                "from": "mthompson@durhampublic.org",
                "subject": "Certificate of Insurance needed",
                "body": "We need an updated COI for the Durham Public Schools contract renewal. Please send to our risk management office by Friday.",
                "expected_route": "Management",
            },
            {
                "from": "procurement@trianglemed.com",
                "subject": "PO-2024-1205 discrepancy",
                "body": "Invoice amount for PO-2024-1205 is $2,400 higher than the purchase order. Please review and provide a corrected invoice or explanation for the overage.",
                "expected_route": "Accounts Receivable",
            },
            {
                "from": "ops@carytowncenter.com",
                "subject": "Emergency tree removal needed",
                "body": "A large oak branch fell in the parking lot after last night's storm. Need emergency removal before stores open at 9am tomorrow. This is urgent.",
                "expected_route": "Dispatch",
            },
            {
                "from": "swhitfield@rpmx.com",
                "subject": "New hire equipment for Marcus Johnson",
                "body": "Marcus Johnson starts next Monday in the Excavation division. Please make sure his PPE kit (hard hat, vest, boots, radio) is ready for pickup Friday.",
                "expected_route": "Operations",
            },
            {
                "from": "legal@mapleridgedev.com",
                "subject": "Change order #3 for site work",
                "body": "Attached is change order #3 for the Maple Ridge site work project. Additional storm drainage required per revised civil drawings. Please provide pricing within 48 hours.",
                "expected_route": "Estimating",
            },
        ]
    }


def build_financial_payload() -> dict[str, Any]:
    periods = []
    current = date(2025, 1, 1)
    end = date(2026, 2, 1)
    while current <= end:
        periods.append(current.strftime("%Y-%m"))
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)

    divisions = ["EX", "RC", "SD", "LM", "RW"]
    base = {
        "EX": {"4100": 430000, "5100": 128000, "5200": 39000, "5300": 52000, "5400": 47000, "5500": 34000, "5600": 9000, "6100": 21000, "6200": 12000, "6300": 9300},
        "RC": {"4100": 510000, "5100": 174000, "5200": 45000, "5300": 67000, "5400": 62000, "5500": 42000, "5600": 11000, "6100": 26000, "6200": 14500, "6300": 10200},
        "SD": {"4100": 460000, "5100": 149000, "5200": 41000, "5300": 59000, "5400": 54000, "5500": 36000, "5600": 9000, "6100": 23000, "6200": 13000, "6300": 9500},
        "LM": {"4200": 190000, "5100": 49000, "5200": 13000, "5300": 19000, "5400": 43000, "5500": 11000, "5600": 7000, "6100": 13000, "6200": 8400, "6300": 6400},
        "RW": {"4100": 290000, "5100": 88000, "5200": 22000, "5300": 31000, "5400": 32000, "5500": 19000, "5600": 6200, "6100": 16500, "6200": 9300, "6300": 7800},
    }

    rows = []
    for period_idx, period in enumerate(periods):
        trend = 1.0 + (period_idx * 0.004)
        for division in divisions:
            for gl_code, amount in base[division].items():
                adjusted = round(amount * trend, 2)
                rows.append({"period": period, "division_id": division, "gl_code": gl_code, "amount": adjusted})

    # Force exact excavation Jan 2025 and Jan 2026 values required by the demo.
    exact_ex = {
        "2025-01": {
            "4100": 420000,
            "5100": 126000,
            "5200": 37800,
            "5300": 50400,
            "5400": 46200,
            "5500": 33600,
            "5600": 8400,
            "6100": 21000,
            "6200": 11500,
            "6300": 8900,
            "6400": 6500,
            "6500": 5800,
            "6600": 5100,
        },
        "2026-01": {
            "4100": 470400,
            "5100": 148680,
            "5200": 42336,
            "5300": 56448,
            "5400": 49896,
            "5500": 40992,
            "5600": 9408,
            "6100": 22680,
            "6200": 12420,
            "6300": 9612,
            "6400": 7020,
            "6500": 6264,
            "6600": 5508,
        },
    }

    rows = [r for r in rows if not (r["division_id"] == "EX" and r["period"] in exact_ex)]
    for period, values in exact_ex.items():
        rows.extend(
            {"period": period, "division_id": "EX", "gl_code": gl_code, "amount": float(amount)}
            for gl_code, amount in values.items()
        )

    summary = {
        "q4_2025_company": {
            "revenue": 4610000,
            "cogs": 3260250,
            "gross_margin_percent": 29.3,
            "operating_expenses": 681850,
            "net_income": 667900,
            "net_margin_percent": 14.5,
            "divisions": {
                "Excavation": {"net_margin_percent": 14.2},
                "Road Construction": {"net_margin_percent": 12.5},
                "Site Development": {"net_margin_percent": 16.0},
                "Landscaping Maintenance": {"net_margin_percent": 13.0},
                "Retaining Walls": {"net_margin_percent": 16.0},
            },
        }
    }

    return {
        "monthly_records": rows,
        "excavation_jan_comparison": {
            "2025": {
                "revenue": 420000,
                "materials": 126000,
                "equipment_rental": 37800,
                "subcontractor": 50400,
                "direct_labor": 46200,
                "fuel": 33600,
                "hauling": 8400,
                "total_cogs": 302400,
                "gross_profit": 117600,
                "gross_margin_percent": 28.0,
                "operating_expenses": 58800,
                "net_income": 58800,
                "net_margin_percent": 14.0,
            },
            "2026": {
                "revenue": 470400,
                "materials": 148680,
                "equipment_rental": 42336,
                "subcontractor": 56448,
                "direct_labor": 49896,
                "fuel": 40992,
                "hauling": 9408,
                "total_cogs": 347760,
                "gross_profit": 122640,
                "gross_margin_percent": 26.1,
                "operating_expenses": 63504,
                "net_income": 59136,
                "net_margin_percent": 12.6,
            },
        },
        "summary": summary,
    }


def seed_database(conn: sqlite3.Connection) -> None:
    load_sql(conn, DATA_DIR / "schema.sql")
    load_sql(conn, DATA_DIR / "seed.sql")

    vendors = create_vendor_payload()
    conn.executemany(
        """
        INSERT INTO vendors (name, email, insurance_expiry, contract_expiry, w9_on_file, notes)
        VALUES (:name, :email, :insurance_expiry, :contract_expiry, :w9_on_file, :notes)
        """,
        vendors,
    )

    projects = [*PROJECTS, *create_background_projects()]
    conn.executemany(
        """
        INSERT INTO projects (id, name, division_id, budget_text, percent_complete, pm_name, pm_email)
        VALUES (:id, :name, :division_id, :budget_text, :percent_complete, :pm_name, :pm_email)
        """,
        projects,
    )

    vendor_lookup = {
        row["name"]: row["id"]
        for row in conn.execute("SELECT id, name FROM vendors").fetchall()
    }
    project_ids = [row[0] for row in conn.execute("SELECT id FROM projects").fetchall()]

    po_rows: list[dict[str, Any]] = []
    for po in CRITICAL_PURCHASE_ORDERS:
        po_rows.append(
            {
                "po_number": po["po_number"],
                "vendor_id": vendor_lookup[po["vendor"]],
                "amount": po["amount"],
                "job_id": po["job_id"],
                "gl_code": po["gl_code"],
            }
        )

    random.seed(RANDOM_SEED)
    vendor_ids = [row[0] for row in conn.execute("SELECT id FROM vendors").fetchall()]
    gl_codes = [row[0] for row in conn.execute("SELECT code FROM gl_accounts WHERE code LIKE '5%' OR code='5200'").fetchall()]

    while len(po_rows) < 150:
        idx = len(po_rows) + 1
        amount = round(random.uniform(1800, 89000), 2)
        if abs(amount % 1000) < 1:
            amount += 37.75
        po_rows.append(
            {
                "po_number": make_po_number(idx),
                "vendor_id": random.choice(vendor_ids),
                "amount": amount,
                "job_id": random.choice(project_ids),
                "gl_code": random.choice(gl_codes),
            }
        )

    conn.executemany(
        """
        INSERT INTO purchase_orders (po_number, vendor_id, amount, job_id, gl_code)
        VALUES (:po_number, :vendor_id, :amount, :job_id, :gl_code)
        """,
        po_rows,
    )

    invoice_rows = []
    for idx, invoice in enumerate(DEMO_INVOICES, start=1):
        stage = "post_training" if invoice.invoice_number == "INV-9007" else "primary"
        invoice_rows.append(
            {
                "invoice_number": invoice.invoice_number,
                "vendor_id": vendor_lookup[invoice.vendor],
                "amount": invoice.amount,
                "po_reference": invoice.po_reference,
                "invoice_date": invoice.invoice_date.isoformat(),
                "file_path": str((INVOICE_DIR / f"{invoice.invoice_number}.pdf").relative_to(BASE_DIR)),
                "status": "pending_post_training" if stage == "post_training" else "pending",
                "job_id": None,
                "gl_code": None,
                "processing_stage": stage,
                "notes": "Demo invoice",
            }
        )

    all_po_numbers = [row[0] for row in conn.execute("SELECT po_number FROM purchase_orders").fetchall()]
    for idx in range(1, 194):
        po_ref = random.choice(all_po_numbers) if idx % 5 == 0 else None
        amount = round(random.uniform(450, 72000), 2)
        if abs(amount % 1000) < 1:
            amount += 19.25
        invoice_rows.append(
            {
                "invoice_number": make_invoice_number(idx),
                "vendor_id": random.choice(vendor_ids),
                "amount": amount,
                "po_reference": po_ref,
                "invoice_date": (date(2025, 1, 1) + timedelta(days=idx % 365)).isoformat(),
                "file_path": "data/invoices/background-placeholder.pdf",
                "status": "archived",
                "job_id": None,
                "gl_code": None,
                "processing_stage": "background",
                "notes": "Background invoice",
            }
        )

    conn.executemany(
        """
        INSERT INTO invoices (invoice_number, vendor_id, amount, po_reference, invoice_date, file_path, status, job_id, gl_code, processing_stage, notes)
        VALUES (:invoice_number, :vendor_id, :amount, :po_reference, :invoice_date, :file_path, :status, :job_id, :gl_code, :processing_stage, :notes)
        """,
        invoice_rows,
    )

    aging_rows = [
        {"customer_name": "Greenfield Development", "days_out": 35, "amount": 22400, "is_retainage": 0, "notes": ""},
        {"customer_name": "Summit Property Group", "days_out": 67, "amount": 41800, "is_retainage": 0, "notes": ""},
        {"customer_name": "Parkview Associates", "days_out": 95, "amount": 28500, "is_retainage": 0, "notes": "Multiple reminders sent"},
        {"customer_name": "Riverside Municipal", "days_out": 45, "amount": 67200, "is_retainage": 1, "notes": "Retainage"},
        {"customer_name": "Oak Valley Homes", "days_out": 15, "amount": 8900, "is_retainage": 0, "notes": "Within terms"},
    ]
    conn.executemany(
        """
        INSERT INTO ar_aging (customer_name, days_out, amount, is_retainage, notes)
        VALUES (:customer_name, :days_out, :amount, :is_retainage, :notes)
        """,
        aging_rows,
    )

    financial_payload = build_financial_payload()
    conn.executemany(
        """
        INSERT INTO financial_monthly (period, division_id, gl_code, amount)
        VALUES (:period, :division_id, :gl_code, :amount)
        """,
        financial_payload["monthly_records"],
    )


def write_json_files(conn: sqlite3.Connection) -> None:
    vendors = [dict(row) for row in conn.execute("SELECT id, name, email, insurance_expiry, contract_expiry, w9_on_file, notes FROM vendors ORDER BY name").fetchall()]
    purchase_orders = [
        dict(row)
        for row in conn.execute(
            """
            SELECT p.po_number, v.name AS vendor, p.amount, p.job_id, p.gl_code, p.status
            FROM purchase_orders p
            JOIN vendors v ON p.vendor_id = v.id
            ORDER BY p.po_number
            """
        ).fetchall()
    ]
    projects = [dict(row) for row in conn.execute("SELECT * FROM projects ORDER BY id").fetchall()]

    financial_payload = build_financial_payload()
    dispatch_payload = build_dispatch_dataset()

    files: dict[str, Any] = {
        "vendors.json": {"demo_date": DEMO_DATE.isoformat(), "vendors": vendors},
        "purchase_orders.json": {"purchase_orders": purchase_orders},
        "projects.json": {"projects": projects},
        "ar_aging.json": {
            "accounts": [dict(row) for row in conn.execute("SELECT customer_name, days_out, amount, is_retainage, notes FROM ar_aging").fetchall()]
        },
        "vendor_compliance_records.json": {"demo_date": DEMO_DATE.isoformat(), "vendors": vendors},
        "dispatch_jobs.json": dispatch_payload,
        "project_progress.json": build_progress_dataset(),
        "equipment_maintenance.json": build_equipment_dataset(),
        "hr_certifications.json": build_hr_dataset(),
        "onboarding_new_hire.json": build_onboarding_dataset(),
        "productivity_rates.json": build_productivity_dataset(),
        "inquiry_emails.json": build_inquiry_dataset(),
        "financial_reporting.json": financial_payload,
    }

    for name, payload in files.items():
        path = JSON_DIR / name
        path.write_text(json.dumps(payload, indent=2))


def reset_skills_files() -> None:
    agents_dir = BASE_DIR / "agents"
    if not agents_dir.exists():
        return
    for agent_dir in agents_dir.iterdir():
        if not agent_dir.is_dir():
            continue
        source = agent_dir / "skills_original.md"
        target = agent_dir / "skills.md"
        if source.exists():
            shutil.copyfile(source, target)


def run_integrity_checks(conn: sqlite3.Connection) -> None:
    checks = {
        "invoice_vendor_fk": "SELECT COUNT(*) FROM invoices i LEFT JOIN vendors v ON i.vendor_id = v.id WHERE v.id IS NULL",
        "invoice_po_fk": "SELECT COUNT(*) FROM invoices i LEFT JOIN purchase_orders p ON i.po_reference = p.po_number WHERE i.po_reference IS NOT NULL AND p.po_number IS NULL",
        "po_vendor_fk": "SELECT COUNT(*) FROM purchase_orders p LEFT JOIN vendors v ON p.vendor_id = v.id WHERE v.id IS NULL",
        "po_project_fk": "SELECT COUNT(*) FROM purchase_orders p LEFT JOIN projects pr ON p.job_id = pr.id WHERE pr.id IS NULL",
        "po_gl_fk": "SELECT COUNT(*) FROM purchase_orders p LEFT JOIN gl_accounts g ON p.gl_code = g.code WHERE g.code IS NULL",
        "project_division_fk": "SELECT COUNT(*) FROM projects p LEFT JOIN divisions d ON p.division_id = d.id WHERE d.id IS NULL",
    }

    failures = []
    for name, query in checks.items():
        count = conn.execute(query).fetchone()[0]
        if count != 0:
            failures.append(f"{name} failed ({count})")

    rounded_count = conn.execute(
        "SELECT COUNT(*) FROM purchase_orders WHERE amount % 1000 = 0 OR amount % 5000 = 0"
    ).fetchone()[0]
    if rounded_count > 10:
        failures.append("too many round-number purchase order amounts")

    placeholder_vendor_count = conn.execute(
        "SELECT COUNT(*) FROM vendors WHERE lower(name) LIKE '%test vendor%'"
    ).fetchone()[0]
    if placeholder_vendor_count:
        failures.append("placeholder vendor names detected")

    if failures:
        raise RuntimeError("Integrity checks failed: " + "; ".join(failures))


def generate_invoice_pdfs(conn: sqlite3.Connection) -> None:
    vendor_meta = {
        row["name"]: dict(row)
        for row in conn.execute("SELECT name, email FROM vendors").fetchall()
    }

    for invoice in DEMO_INVOICES:
        render_invoice_pdf(invoice, vendor_meta)


def reset_agent_status(conn: sqlite3.Connection) -> None:
    conn.execute("UPDATE agent_status SET status='idle', current_activity='Ready', last_run_at=NULL, cost_today=0, tasks_completed_today=0")
    conn.execute("DELETE FROM review_queue")
    conn.execute("DELETE FROM communications")
    conn.execute("DELETE FROM activity_logs")
    conn.execute("DELETE FROM internal_tasks")
    conn.execute("DELETE FROM collections_queue")


def main() -> None:
    ensure_dirs()
    database_path = db_path()
    database_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row

    try:
        seed_database(conn)
        reset_agent_status(conn)
        generate_invoice_pdfs(conn)
        write_json_files(conn)
        run_integrity_checks(conn)
        reset_skills_files()
        conn.commit()
    finally:
        conn.close()

    print(f"Reset complete: {database_path}")
    print("- SQLite schema rebuilt")
    print("- 50 vendors, 30 projects, 150 purchase orders, 200 invoices seeded")
    print("- 7 invoice PDFs generated")
    print("- JSON scenario payloads refreshed")
    print("- Skills files restored from skills_original.md")


if __name__ == "__main__":
    main()
