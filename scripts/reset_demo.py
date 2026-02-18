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
    """Rich progress tracking data: 3 projects with proposal-vs-actuals, labor, schedule, change orders."""
    return {"as_of_date":"2026-01-15","projects":[
        {"project_id":"RW-2025-003","project_name":"Highway 9 Interchange Grading & Paving","division":"Road & Highway Construction","division_id":"RW","project_manager":"Mike Torres","superintendent":"Dave Kowalski","client":"Colorado DOT — Region 4","start_date":"2025-03-15","original_end_date":"2025-12-20","current_projected_end_date":"2026-02-28","finding":"behind_schedule",
         "proposal":{"contract_value":28500000,"estimated_cost":26900000,"target_margin_pct":5.6,"bid_date":"2025-01-22","scope_summary":"Complete interchange reconstruction including earthwork, drainage, asphalt paving, concrete barriers, signage, and striping for the Highway 9 / County Road 42 interchange.","key_assumptions":["Fuel at $3.85/gal average","No rock excavation required below 8ft depth","Subcontractor availability for concrete barriers by August","No winter weather delays past November 15","Material escalation capped at 3% via supplier contracts"],
          "cost_estimate_by_code":{"01-Mobilization":1200000,"02-Earthwork & Grading":6800000,"03-Drainage & Utilities":3200000,"04-Aggregate Base":2400000,"05-Asphalt Paving":5800000,"06-Concrete Barriers":2100000,"07-Signage & Striping":900000,"08-Traffic Control":1600000,"09-Erosion Control":750000,"10-General Conditions":2150000},
          "labor_estimate":{"total_labor_hours":68500,"avg_loaded_rate":78.50,"peak_crew_size":45,"estimated_labor_cost":5377250,"labor_pct_of_total":20.0},
          "schedule_estimate":{"total_duration_days":280,"phases":[{"phase":"Mobilization & Site Prep","duration_days":25,"start":"2025-03-15","end":"2025-04-08"},{"phase":"Earthwork & Grading","duration_days":75,"start":"2025-04-09","end":"2025-06-22"},{"phase":"Drainage & Utilities","duration_days":45,"start":"2025-05-20","end":"2025-07-03"},{"phase":"Aggregate Base","duration_days":30,"start":"2025-07-04","end":"2025-08-02"},{"phase":"Asphalt Paving","duration_days":50,"start":"2025-08-03","end":"2025-09-21"},{"phase":"Concrete Barriers & Finishing","duration_days":40,"start":"2025-09-22","end":"2025-10-31"},{"phase":"Signage, Striping & Punch List","duration_days":35,"start":"2025-11-01","end":"2025-12-05"},{"phase":"Final Inspection & Closeout","duration_days":15,"start":"2025-12-06","end":"2025-12-20"}]}},
         "actuals":{"total_cost_to_date":22847316,"percent_complete":62,"percent_billed":68,
          "cost_by_code":{"01-Mobilization":{"budgeted":1200000,"actual":1215400,"pct_complete":100},"02-Earthwork & Grading":{"budgeted":6800000,"actual":7483200,"pct_complete":100},"03-Drainage & Utilities":{"budgeted":3200000,"actual":3488000,"pct_complete":95},"04-Aggregate Base":{"budgeted":2400000,"actual":2280000,"pct_complete":100},"05-Asphalt Paving":{"budgeted":5800000,"actual":4176000,"pct_complete":60},"06-Concrete Barriers":{"budgeted":2100000,"actual":1596000,"pct_complete":40},"07-Signage & Striping":{"budgeted":900000,"actual":0,"pct_complete":0},"08-Traffic Control":{"budgeted":1600000,"actual":1408716,"pct_complete":75},"09-Erosion Control":{"budgeted":750000,"actual":512000,"pct_complete":55},"10-General Conditions":{"budgeted":2150000,"actual":1688000,"pct_complete":65}},
          "labor":{"total_hours_to_date":52340,"avg_actual_loaded_rate":83.20,"current_crew_size":38,"labor_cost_to_date":4354688,"overtime_hours":4800,"overtime_cost":576000,"productivity_index":0.87,"monthly_labor":[{"month":"2025-03","hours":2100,"cost":164850,"crew_size":18},{"month":"2025-04","hours":5400,"cost":423900,"crew_size":32},{"month":"2025-05","hours":6800,"cost":533800,"crew_size":42},{"month":"2025-06","hours":7200,"cost":565200,"crew_size":45},{"month":"2025-07","hours":6900,"cost":541650,"crew_size":44},{"month":"2025-08","hours":6500,"cost":510250,"crew_size":40},{"month":"2025-09","hours":5800,"cost":455300,"crew_size":38},{"month":"2025-10","hours":4200,"cost":329700,"crew_size":35},{"month":"2025-11","hours":3800,"cost":298350,"crew_size":30},{"month":"2025-12","hours":2140,"cost":168038,"crew_size":22},{"month":"2026-01","hours":1500,"cost":117750,"crew_size":18}]},
          "schedule":{"days_elapsed":306,"days_behind":70,"critical_path_delay_cause":"Rock excavation encountered at 6ft depth (bid assumed no rock below 8ft). Added 35 calendar days to earthwork phase. Concrete barrier subcontractor delayed mobilization by 3 weeks due to other project commitments.","milestones":[{"name":"Mobilization Complete","planned":"2025-04-08","actual":"2025-04-10","status":"complete","days_delta":2},{"name":"Earthwork 100%","planned":"2025-06-22","actual":"2025-08-01","status":"complete","days_delta":40},{"name":"Drainage & Utilities","planned":"2025-07-03","actual":"2025-08-15","status":"complete","days_delta":43},{"name":"Base Course Complete","planned":"2025-08-02","actual":"2025-09-20","status":"complete","days_delta":49},{"name":"Paving 50%","planned":"2025-08-27","actual":"2025-11-05","status":"complete","days_delta":70},{"name":"Paving 100%","planned":"2025-09-21","actual":None,"status":"in_progress","days_delta":None},{"name":"Barriers Complete","planned":"2025-10-31","actual":None,"status":"in_progress","days_delta":None},{"name":"Signage & Striping","planned":"2025-12-05","actual":None,"status":"not_started","days_delta":None},{"name":"Final Inspection","planned":"2025-12-20","actual":None,"status":"not_started","days_delta":None}]}},
         "change_orders":[{"co_number":"CO-001","description":"Rock excavation — unforeseen subsurface conditions","amount":682000,"status":"approved","date":"2025-06-15","impact_days":35},{"co_number":"CO-002","description":"Extended traffic control due to schedule extension","amount":245000,"status":"approved","date":"2025-09-01","impact_days":0},{"co_number":"CO-003","description":"Additional erosion control for extended winter exposure","amount":118000,"status":"pending","date":"2025-12-10","impact_days":0}],
         "risk_flags":["Budget burn (84.8%) exceeds completion (62%) by 22.8 percentage points","Earthwork overran estimate by $683K (10%) due to unforeseen rock","Project 70 days behind original schedule","Winter paving window closing — asphalt plant shuts down mid-February","Overtime hours (4,800) represent 9.2% of total hours, indicating crew strain","Productivity index at 0.87 (13% below estimate)"]},
        {"project_id":"EX-2025-011","project_name":"Maple Ridge Residential Site Development","division":"Site Development","division_id":"SD","project_manager":"Sarah Chen","superintendent":"Tony Vasquez","client":"Maple Ridge Development Group LLC","start_date":"2025-05-01","original_end_date":"2025-11-30","current_projected_end_date":"2025-12-15","finding":"on_track",
         "proposal":{"contract_value":8750000,"estimated_cost":7960000,"target_margin_pct":9.0,"bid_date":"2025-03-10","scope_summary":"Full site development for 142-lot residential subdivision including mass grading, storm drainage, sanitary sewer, water main, curb & gutter, and road base for Maple Ridge Phase 3.","key_assumptions":["Soil conditions per geotech report — no remediation needed","City utility connections available by June 15","No FEMA floodplain impacts on grading design","Fuel at $3.75/gal average","Standard 5-day work weeks with no mandatory overtime"],
          "cost_estimate_by_code":{"01-Mobilization":320000,"02-Mass Grading":2100000,"03-Storm Drainage":1450000,"04-Sanitary Sewer":1180000,"05-Water Main":980000,"06-Curb & Gutter":680000,"07-Road Base":750000,"08-Erosion Control":280000,"09-General Conditions":220000},
          "labor_estimate":{"total_labor_hours":28200,"avg_loaded_rate":72.00,"peak_crew_size":28,"estimated_labor_cost":2030400,"labor_pct_of_total":25.5},
          "schedule_estimate":{"total_duration_days":214,"phases":[{"phase":"Mobilization","duration_days":10,"start":"2025-05-01","end":"2025-05-10"},{"phase":"Mass Grading","duration_days":45,"start":"2025-05-11","end":"2025-06-24"},{"phase":"Underground Utilities","duration_days":75,"start":"2025-06-10","end":"2025-08-23"},{"phase":"Curb & Gutter","duration_days":35,"start":"2025-08-15","end":"2025-09-18"},{"phase":"Road Base & Grading","duration_days":30,"start":"2025-09-19","end":"2025-10-18"},{"phase":"Punch List & Closeout","duration_days":25,"start":"2025-10-19","end":"2025-11-12"}]}},
         "actuals":{"total_cost_to_date":7624800,"percent_complete":92,"percent_billed":90,
          "cost_by_code":{"01-Mobilization":{"budgeted":320000,"actual":318500,"pct_complete":100},"02-Mass Grading":{"budgeted":2100000,"actual":2058000,"pct_complete":100},"03-Storm Drainage":{"budgeted":1450000,"actual":1421000,"pct_complete":100},"04-Sanitary Sewer":{"budgeted":1180000,"actual":1180000,"pct_complete":100},"05-Water Main":{"budgeted":980000,"actual":950600,"pct_complete":100},"06-Curb & Gutter":{"budgeted":680000,"actual":665600,"pct_complete":100},"07-Road Base":{"budgeted":750000,"actual":675000,"pct_complete":85},"08-Erosion Control":{"budgeted":280000,"actual":207100,"pct_complete":70},"09-General Conditions":{"budgeted":220000,"actual":149000,"pct_complete":65}},
          "labor":{"total_hours_to_date":25100,"avg_actual_loaded_rate":73.50,"current_crew_size":12,"labor_cost_to_date":1844850,"overtime_hours":980,"overtime_cost":108780,"productivity_index":1.04,"monthly_labor":[{"month":"2025-05","hours":2800,"cost":205800,"crew_size":18},{"month":"2025-06","hours":4200,"cost":308700,"crew_size":26},{"month":"2025-07","hours":4500,"cost":330750,"crew_size":28},{"month":"2025-08","hours":4100,"cost":301350,"crew_size":26},{"month":"2025-09","hours":3800,"cost":279300,"crew_size":24},{"month":"2025-10","hours":2900,"cost":213150,"crew_size":18},{"month":"2025-11","hours":1800,"cost":132300,"crew_size":14},{"month":"2025-12","hours":700,"cost":51450,"crew_size":12},{"month":"2026-01","hours":300,"cost":22050,"crew_size":8}]},
          "schedule":{"days_elapsed":260,"days_behind":0,"days_ahead":5,"critical_path_delay_cause":None,"milestones":[{"name":"Mobilization Complete","planned":"2025-05-10","actual":"2025-05-09","status":"complete","days_delta":-1},{"name":"Mass Grading 100%","planned":"2025-06-24","actual":"2025-06-20","status":"complete","days_delta":-4},{"name":"Storm Drainage Complete","planned":"2025-08-05","actual":"2025-08-02","status":"complete","days_delta":-3},{"name":"Sanitary Sewer Complete","planned":"2025-08-15","actual":"2025-08-14","status":"complete","days_delta":-1},{"name":"Water Main Complete","planned":"2025-08-23","actual":"2025-08-20","status":"complete","days_delta":-3},{"name":"Curb & Gutter Complete","planned":"2025-09-18","actual":"2025-09-15","status":"complete","days_delta":-3},{"name":"Road Base Complete","planned":"2025-10-18","actual":None,"status":"in_progress","days_delta":None},{"name":"Punch List & Closeout","planned":"2025-11-12","actual":None,"status":"not_started","days_delta":None}]}},
         "change_orders":[{"co_number":"CO-001","description":"Additional 12 lots added to Phase 3 scope","amount":420000,"status":"approved","date":"2025-07-20","impact_days":15}],
         "risk_flags":[]},
        {"project_id":"RC-2025-007","project_name":"Blue Mountain Mining Access Road","division":"Road & Highway Construction","division_id":"RW","project_manager":"James Whitfield","superintendent":"Carlos Mendez","client":"Blue Mountain Mining Corporation","start_date":"2025-06-01","original_end_date":"2026-03-15","current_projected_end_date":"2026-05-30","finding":"at_risk",
         "proposal":{"contract_value":14200000,"estimated_cost":12900000,"target_margin_pct":9.2,"bid_date":"2025-04-05","scope_summary":"Construction of 4.2-mile heavy-haul access road including cut/fill operations, rock blasting, retaining walls, bridge abutment, aggregate base, and asphalt paving to Blue Mountain mine site elevation 8,200ft.","key_assumptions":["Blasting restricted to 8am-4pm per county permit","Mountain access road passable for equipment delivery by June 15","No endangered species habitat disruption (per environmental survey)","Retaining wall design finalized — no redesign needed","Winter shutdown December 15 through March 1 (70 calendar days)","Fuel delivery surcharge 8% for mountain elevation"],
          "cost_estimate_by_code":{"01-Mobilization":580000,"02-Clearing & Grubbing":420000,"03-Rock Blasting":2800000,"04-Cut & Fill":2400000,"05-Retaining Walls":1850000,"06-Bridge Abutment":1200000,"07-Aggregate Base":1150000,"08-Asphalt Paving":1400000,"09-Erosion & Environmental":600000,"10-General Conditions":500000},
          "labor_estimate":{"total_labor_hours":42000,"avg_loaded_rate":82.00,"peak_crew_size":35,"estimated_labor_cost":3444000,"labor_pct_of_total":26.7},
          "schedule_estimate":{"total_duration_days":288,"phases":[{"phase":"Mobilization & Access","duration_days":20,"start":"2025-06-01","end":"2025-06-20"},{"phase":"Clearing & Grubbing","duration_days":25,"start":"2025-06-21","end":"2025-07-15"},{"phase":"Rock Blasting & Excavation","duration_days":60,"start":"2025-07-16","end":"2025-09-13"},{"phase":"Cut, Fill & Retaining Walls","duration_days":55,"start":"2025-08-15","end":"2025-10-08"},{"phase":"Bridge Abutment","duration_days":40,"start":"2025-09-20","end":"2025-10-29"},{"phase":"Winter Shutdown","duration_days":70,"start":"2025-12-15","end":"2026-02-22"},{"phase":"Aggregate Base & Paving","duration_days":45,"start":"2026-02-23","end":"2026-04-08"},{"phase":"Closeout & Final Inspection","duration_days":15,"start":"2026-04-09","end":"2026-04-23"}]}},
         "actuals":{"total_cost_to_date":8934500,"percent_complete":48,"percent_billed":52,
          "cost_by_code":{"01-Mobilization":{"budgeted":580000,"actual":612000,"pct_complete":100},"02-Clearing & Grubbing":{"budgeted":420000,"actual":445200,"pct_complete":100},"03-Rock Blasting":{"budgeted":2800000,"actual":3248000,"pct_complete":85},"04-Cut & Fill":{"budgeted":2400000,"actual":1920000,"pct_complete":65},"05-Retaining Walls":{"budgeted":1850000,"actual":1258000,"pct_complete":55},"06-Bridge Abutment":{"budgeted":1200000,"actual":540000,"pct_complete":30},"07-Aggregate Base":{"budgeted":1150000,"actual":0,"pct_complete":0},"08-Asphalt Paving":{"budgeted":1400000,"actual":0,"pct_complete":0},"09-Erosion & Environmental":{"budgeted":600000,"actual":486300,"pct_complete":70},"10-General Conditions":{"budgeted":500000,"actual":425000,"pct_complete":72}},
          "labor":{"total_hours_to_date":24800,"avg_actual_loaded_rate":86.50,"current_crew_size":0,"labor_cost_to_date":2145200,"overtime_hours":3200,"overtime_cost":416000,"productivity_index":0.82,"monthly_labor":[{"month":"2025-06","hours":2400,"cost":207600,"crew_size":22},{"month":"2025-07","hours":4100,"cost":354650,"crew_size":30},{"month":"2025-08","hours":4600,"cost":397900,"crew_size":34},{"month":"2025-09","hours":4800,"cost":415200,"crew_size":35},{"month":"2025-10","hours":4200,"cost":363300,"crew_size":32},{"month":"2025-11","hours":3500,"cost":302750,"crew_size":28},{"month":"2025-12","hours":1200,"cost":103800,"crew_size":12}]},
          "schedule":{"days_elapsed":229,"days_behind":25,"critical_path_delay_cause":"Rock blasting yielded 40% more material than geological survey predicted, extending excavation by 18 days. Retaining wall redesign required due to unstable slope conditions discovered during excavation — added 12 days for engineering review and revised foundation design. Currently in winter shutdown.","milestones":[{"name":"Mobilization Complete","planned":"2025-06-20","actual":"2025-06-22","status":"complete","days_delta":2},{"name":"Clearing & Grubbing","planned":"2025-07-15","actual":"2025-07-18","status":"complete","days_delta":3},{"name":"Rock Blasting 100%","planned":"2025-09-13","actual":None,"status":"in_progress","days_delta":None},{"name":"Cut & Fill Complete","planned":"2025-10-08","actual":None,"status":"in_progress","days_delta":None},{"name":"Bridge Abutment","planned":"2025-10-29","actual":None,"status":"in_progress","days_delta":None},{"name":"Retaining Walls Complete","planned":"2025-11-15","actual":None,"status":"in_progress","days_delta":None},{"name":"Winter Shutdown Start","planned":"2025-12-15","actual":"2025-12-15","status":"complete","days_delta":0},{"name":"Aggregate Base & Paving","planned":"2026-04-08","actual":None,"status":"not_started","days_delta":None},{"name":"Final Inspection","planned":"2026-04-23","actual":None,"status":"not_started","days_delta":None}]}},
         "change_orders":[{"co_number":"CO-001","description":"Additional rock blasting — excess material volume","amount":385000,"status":"approved","date":"2025-08-22","impact_days":18},{"co_number":"CO-002","description":"Retaining wall redesign — unstable slope conditions","amount":290000,"status":"approved","date":"2025-10-15","impact_days":12},{"co_number":"CO-003","description":"Environmental mitigation — raptor nesting buffer zone","amount":145000,"status":"pending","date":"2025-11-28","impact_days":8}],
         "risk_flags":["Rock blasting 16% over budget ($448K overrun on $2.8M estimate)","Retaining wall redesign added $290K in approved change orders","Productivity index at 0.82 (18% below target) — difficult terrain conditions","Overtime at 12.9% of total hours — above 8% threshold","Environmental change order pending — may add 8 more days to schedule","Project currently 25 days behind schedule with 48% complete","Estimated cost at completion exceeds original estimate by ~$820K before pending CO"]}
    ]}


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


def build_takeoff_dataset() -> dict[str, Any]:
    return {
        "project": {
            "name": "Creekside Business Park — Site Development",
            "project_id": "SD-2026-042",
            "client": "Creekside Development Group LLC",
            "location": "4200 Creekside Parkway, Charlotte, NC 28277",
            "date": "2026-02-17",
            "estimator": "James Callahan, PE",
            "bid_date": "2026-03-07",
            "description": (
                "Complete site development package for a 12-acre commercial business park "
                "including mass grading, storm drainage, water and sewer utilities, concrete "
                "curb and sidewalk, asphalt paving, and erosion control measures."
            ),
        },
        "takeoff": [
            # ── Earthwork ──
            {"item": "Strip & Stockpile Topsoil", "category": "Earthwork", "quantity": 4800, "unit": "CY",
             "description": "Strip 6\" topsoil, stockpile on-site for reuse"},
            {"item": "Mass Grading — Cut", "category": "Earthwork", "quantity": 18500, "unit": "CY",
             "description": "Bulk excavation to subgrade elevation per grading plan"},
            {"item": "Mass Grading — Fill & Compaction", "category": "Earthwork", "quantity": 14200, "unit": "CY",
             "description": "Place and compact structural fill to 95% standard proctor"},
            {"item": "Fine Grading", "category": "Earthwork", "quantity": 52000, "unit": "SY",
             "description": "Fine grade subgrade to ±0.1' tolerance"},
            # ── Utilities ──
            {"item": "8\" DIP Water Main", "category": "Utilities", "quantity": 2400, "unit": "LF",
             "description": "Install 8\" ductile iron water main with fittings"},
            {"item": "Fire Hydrant Assembly", "category": "Utilities", "quantity": 6, "unit": "EA",
             "description": "Fire hydrant with valve, tee, and thrust block"},
            {"item": "8\" PVC Sanitary Sewer", "category": "Utilities", "quantity": 1800, "unit": "LF",
             "description": "Install 8\" SDR-35 PVC sanitary sewer"},
            {"item": "Sanitary Manhole (4' dia)", "category": "Utilities", "quantity": 8, "unit": "EA",
             "description": "Precast concrete sanitary manholes to 8' depth average"},
            {"item": "18\" RCP Storm Drain", "category": "Utilities", "quantity": 1600, "unit": "LF",
             "description": "18\" reinforced concrete storm drain pipe"},
            {"item": "Storm Drain Inlet", "category": "Utilities", "quantity": 12, "unit": "EA",
             "description": "Precast drop inlet with grate, 4'×4'×6' avg depth"},
            # ── Paving ──
            {"item": "6\" Aggregate Base Course", "category": "Paving", "quantity": 28000, "unit": "SY",
             "description": "6\" compacted aggregate base for roadways and parking"},
            {"item": "3\" HMA Surface Course", "category": "Paving", "quantity": 28000, "unit": "SY",
             "description": "3\" hot-mix asphalt surface course, S9.5B"},
            # ── Concrete ──
            {"item": "Concrete Curb & Gutter", "category": "Concrete", "quantity": 4200, "unit": "LF",
             "description": "2'-6\" standard curb and gutter per NCDOT detail"},
            {"item": "4\" Concrete Sidewalk", "category": "Concrete", "quantity": 8400, "unit": "SF",
             "description": "4\" reinforced concrete sidewalk, broom finish"},
            {"item": "6\" Concrete Driveway Apron", "category": "Concrete", "quantity": 3200, "unit": "SF",
             "description": "6\" reinforced concrete at driveway entrances"},
            # ── Erosion Control ──
            {"item": "Silt Fence", "category": "Erosion Control", "quantity": 3600, "unit": "LF",
             "description": "Install and maintain silt fence perimeter"},
            {"item": "Construction Entrance", "category": "Erosion Control", "quantity": 2, "unit": "EA",
             "description": "50' stabilized rock construction entrance"},
            {"item": "Seeding & Mulching", "category": "Erosion Control", "quantity": 42000, "unit": "SY",
             "description": "Hydroseed disturbed areas with permanent seed mix"},
        ],
        "cost_database": {
            "Earthwork": {
                "Strip & Stockpile Topsoil":       {"labor_rate": 1.85, "material_rate": 0.00, "equipment_rate": 2.40},
                "Mass Grading — Cut":              {"labor_rate": 1.60, "material_rate": 0.00, "equipment_rate": 2.75},
                "Mass Grading — Fill & Compaction": {"labor_rate": 2.10, "material_rate": 0.45, "equipment_rate": 3.20},
                "Fine Grading":                    {"labor_rate": 0.55, "material_rate": 0.00, "equipment_rate": 0.70},
            },
            "Utilities": {
                "8\" DIP Water Main":       {"labor_rate": 18.50, "material_rate": 32.00, "equipment_rate": 8.50},
                "Fire Hydrant Assembly":    {"labor_rate": 480.00, "material_rate": 2850.00, "equipment_rate": 320.00},
                "8\" PVC Sanitary Sewer":   {"labor_rate": 16.00, "material_rate": 14.50, "equipment_rate": 9.00},
                "Sanitary Manhole (4' dia)": {"labor_rate": 650.00, "material_rate": 2200.00, "equipment_rate": 450.00},
                "18\" RCP Storm Drain":     {"labor_rate": 14.00, "material_rate": 22.00, "equipment_rate": 7.50},
                "Storm Drain Inlet":        {"labor_rate": 720.00, "material_rate": 1850.00, "equipment_rate": 380.00},
            },
            "Paving": {
                "6\" Aggregate Base Course": {"labor_rate": 1.20, "material_rate": 3.80, "equipment_rate": 1.50},
                "3\" HMA Surface Course":    {"labor_rate": 1.00, "material_rate": 5.20, "equipment_rate": 1.80},
            },
            "Concrete": {
                "Concrete Curb & Gutter":     {"labor_rate": 6.50, "material_rate": 8.00, "equipment_rate": 2.20},
                "4\" Concrete Sidewalk":      {"labor_rate": 2.80, "material_rate": 3.50, "equipment_rate": 0.60},
                "6\" Concrete Driveway Apron": {"labor_rate": 3.40, "material_rate": 4.80, "equipment_rate": 0.80},
            },
            "Erosion Control": {
                "Silt Fence":             {"labor_rate": 1.20, "material_rate": 0.85, "equipment_rate": 0.30},
                "Construction Entrance":  {"labor_rate": 800.00, "material_rate": 2400.00, "equipment_rate": 600.00},
                "Seeding & Mulching":     {"labor_rate": 0.15, "material_rate": 0.22, "equipment_rate": 0.08},
            },
        },
        "markup_schedule": {
            "overhead": 0.12,
            "profit": 0.10,
            "contingency": 0.05,
            "bond": 0.015,
            "mobilization": 0.03,
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
    """Generate 24 months of realistic financial data for an ~$800M construction company."""
    import math

    # ── Period range: 2024-01 through 2026-01 (25 months for full YoY) ──
    periods: list[str] = []
    current = date(2024, 1, 1)
    end = date(2026, 1, 1)
    while current <= end:
        periods.append(current.strftime("%Y-%m"))
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)

    # ── Company info ──
    company = {
        "name": "RPMX Construction Group",
        "fiscal_year_end": "December",
        "annual_revenue_target": 850_000_000,
        "employee_count": 1200,
        "regions": ["Southwest", "Mountain West", "Pacific Northwest"],
        "divisions": {
            "EX": "Excavation & Earthwork",
            "RC": "Road & Highway Construction",
            "SD": "Site Development",
            "LM": "Landscape & Maintenance",
            "RW": "Retaining Walls & Structures",
        },
    }

    # ── GL chart of accounts ──
    gl_chart = {
        "4100": {"desc": "Contract Revenue", "category": "revenue"},
        "4200": {"desc": "Service Revenue", "category": "revenue"},
        "4300": {"desc": "Change Order Revenue", "category": "revenue"},
        "5100": {"desc": "Materials", "category": "cogs"},
        "5200": {"desc": "Equipment Rental", "category": "cogs"},
        "5300": {"desc": "Subcontractor Costs", "category": "cogs"},
        "5400": {"desc": "Direct Labor", "category": "cogs"},
        "5500": {"desc": "Fuel & Lubricants", "category": "cogs"},
        "5600": {"desc": "Hauling & Freight", "category": "cogs"},
        "5700": {"desc": "Permits & Fees", "category": "cogs"},
        "5800": {"desc": "Equipment Maintenance", "category": "cogs"},
        "6100": {"desc": "Office & Admin", "category": "opex"},
        "6200": {"desc": "Insurance", "category": "opex"},
        "6300": {"desc": "Vehicle & Fleet", "category": "opex"},
        "6400": {"desc": "IT & Software", "category": "opex"},
        "6500": {"desc": "Professional Fees", "category": "opex"},
        "6600": {"desc": "Depreciation", "category": "opex"},
    }

    # ── Base monthly revenue per division (annual targets) ──
    # EX ~$198M, RC ~$216M, SD ~$168M, LM ~$54M, RW ~$126M = ~$762M base (2025)
    div_monthly_base = {
        "EX": 16_500_000,
        "RC": 18_000_000,
        "SD": 14_000_000,
        "LM":  4_500_000,
        "RW": 10_500_000,
    }

    # Seasonal multipliers (construction peaks Q2/Q3, dips Q1/Q4)
    seasonal = {
        1: 0.78, 2: 0.82, 3: 0.92, 4: 1.08, 5: 1.15, 6: 1.18,
        7: 1.20, 8: 1.16, 9: 1.10, 10: 0.96, 11: 0.84, 12: 0.76,
    }

    # Cost structure as % of revenue per division
    cost_pcts = {
        "EX": {"5100": 0.22, "5200": 0.07, "5300": 0.10, "5400": 0.14, "5500": 0.065, "5600": 0.025, "5700": 0.008, "5800": 0.018},
        "RC": {"5100": 0.24, "5200": 0.06, "5300": 0.12, "5400": 0.13, "5500": 0.055, "5600": 0.022, "5700": 0.010, "5800": 0.015},
        "SD": {"5100": 0.20, "5200": 0.08, "5300": 0.11, "5400": 0.12, "5500": 0.050, "5600": 0.020, "5700": 0.009, "5800": 0.016},
        "LM": {"5100": 0.15, "5200": 0.04, "5300": 0.08, "5400": 0.25, "5500": 0.035, "5600": 0.018, "5700": 0.005, "5800": 0.020},
        "RW": {"5100": 0.26, "5200": 0.05, "5300": 0.09, "5400": 0.11, "5500": 0.045, "5600": 0.020, "5700": 0.007, "5800": 0.014},
    }

    opex_pcts = {
        "EX": {"6100": 0.022, "6200": 0.015, "6300": 0.012, "6400": 0.006, "6500": 0.005, "6600": 0.008},
        "RC": {"6100": 0.024, "6200": 0.016, "6300": 0.013, "6400": 0.007, "6500": 0.006, "6600": 0.009},
        "SD": {"6100": 0.023, "6200": 0.015, "6300": 0.011, "6400": 0.006, "6500": 0.005, "6600": 0.008},
        "LM": {"6100": 0.030, "6200": 0.018, "6300": 0.014, "6400": 0.008, "6500": 0.007, "6600": 0.010},
        "RW": {"6100": 0.021, "6200": 0.014, "6300": 0.010, "6400": 0.005, "6500": 0.005, "6600": 0.007},
    }

    # ── YoY growth + margin pressure story ──
    # 2024: baseline. 2025 H1: healthy 10% growth. 2025 H2: fuel +15%, labor +8% pressure.
    def yoy_growth(period_str: str) -> float:
        y, m = int(period_str[:4]), int(period_str[5:7])
        if y == 2024:
            return 1.0
        months_from_2024 = (y - 2024) * 12 + m - 1
        return 1.0 + (months_from_2024 * 0.008)  # ~9.6% annual growth at month 12

    def cost_inflation(period_str: str, gl_code: str) -> float:
        """Extra cost inflation for fuel and labor in 2025 H2+."""
        y, m = int(period_str[:4]), int(period_str[5:7])
        if y < 2025 or (y == 2025 and m <= 6):
            return 1.0
        months_past = m - 6 if y == 2025 else m + 6
        if gl_code == "5500":  # fuel
            return 1.0 + (months_past * 0.022)  # ~15% over 7 months
        if gl_code == "5400":  # labor
            return 1.0 + (months_past * 0.012)  # ~8% over 7 months
        if gl_code == "5100":  # materials
            return 1.0 + (months_past * 0.006)  # ~4% over 7 months
        return 1.0

    rng = random.Random(42)

    # ── Generate monthly_gl and monthly_budget ──
    monthly_gl: list[dict] = []
    monthly_budget: list[dict] = []

    for period in periods:
        month = int(period[5:7])
        s_mult = seasonal[month]
        g_mult = yoy_growth(period)

        for div_id, base_rev in div_monthly_base.items():
            # Revenue: seasonal * growth * small noise
            noise = 1.0 + rng.uniform(-0.03, 0.03)
            rev = round(base_rev * s_mult * g_mult * noise, 2)

            # Split revenue: 85% contract, 10% service, 5% change orders
            rev_4100 = round(rev * 0.85, 2)
            rev_4200 = round(rev * 0.10, 2)
            rev_4300 = round(rev * 0.05, 2)

            for gl, amt in [("4100", rev_4100), ("4200", rev_4200), ("4300", rev_4300)]:
                monthly_gl.append({"period": period, "division_id": div_id, "gl_code": gl, "amount": amt})
                # Budget = planned without noise, no cost inflation
                budget_base = base_rev * s_mult * yoy_growth(period)
                if gl == "4100":
                    budget_amt = round(budget_base * 0.85, 2)
                elif gl == "4200":
                    budget_amt = round(budget_base * 0.10, 2)
                else:
                    budget_amt = round(budget_base * 0.05, 2)
                monthly_budget.append({"period": period, "division_id": div_id, "gl_code": gl, "budget_amount": budget_amt})

            # COGS line items
            for gl_code, pct in cost_pcts[div_id].items():
                c_noise = 1.0 + rng.uniform(-0.02, 0.02)
                c_infl = cost_inflation(period, gl_code)
                amt = round(rev * pct * c_noise * c_infl, 2)
                monthly_gl.append({"period": period, "division_id": div_id, "gl_code": gl_code, "amount": amt})
                budget_amt = round(base_rev * s_mult * yoy_growth(period) * pct, 2)
                monthly_budget.append({"period": period, "division_id": div_id, "gl_code": gl_code, "budget_amount": budget_amt})

            # OpEx line items
            for gl_code, pct in opex_pcts[div_id].items():
                o_noise = 1.0 + rng.uniform(-0.015, 0.015)
                amt = round(rev * pct * o_noise, 2)
                monthly_gl.append({"period": period, "division_id": div_id, "gl_code": gl_code, "amount": amt})
                budget_amt = round(base_rev * s_mult * yoy_growth(period) * pct, 2)
                monthly_budget.append({"period": period, "division_id": div_id, "gl_code": gl_code, "budget_amount": budget_amt})

    # ── Jobs (active projects) ──
    job_statuses = ["active", "active", "active", "active", "completed", "on_hold"]
    job_templates = [
        ("J-1001", "Highway 9 Interchange Grading", "EX", 28_500_000, 0.62, "active"),
        ("J-1002", "Riverfront Commercial Excavation", "EX", 14_200_000, 0.85, "active"),
        ("J-1003", "Mountain View Residential Mass Grade", "EX", 8_700_000, 0.91, "active"),
        ("J-1004", "Airport Runway Extension Earthwork", "EX", 41_000_000, 0.34, "active"),
        ("J-1005", "Downtown Utility Relocation", "EX", 6_300_000, 1.00, "completed"),
        ("J-1006", "Lakeside Dam Remediation", "EX", 19_800_000, 0.48, "active"),
        ("J-2001", "I-25 Corridor Widening Phase III", "RC", 52_000_000, 0.55, "active"),
        ("J-2002", "County Road 44 Reconstruction", "RC", 18_600_000, 0.72, "active"),
        ("J-2003", "Industrial Park Access Road", "RC", 9_400_000, 0.88, "active"),
        ("J-2004", "State Highway 191 Resurfacing", "RC", 31_200_000, 0.41, "active"),
        ("J-2005", "Bridge Deck Overlay — CR 12", "RC", 7_800_000, 1.00, "completed"),
        ("J-2006", "Transit Authority Bus Rapid Lane", "RC", 22_500_000, 0.28, "active"),
        ("J-3001", "Copper Ridge Mixed-Use Site Development", "SD", 16_400_000, 0.67, "active"),
        ("J-3002", "Westfield Hospital Campus Grading", "SD", 23_100_000, 0.52, "active"),
        ("J-3003", "Tech Park Phase II Utilities", "SD", 11_800_000, 0.79, "active"),
        ("J-3004", "Retail Center Parking & Storm Drain", "SD", 8_200_000, 0.93, "active"),
        ("J-3005", "Solar Farm Site Prep", "SD", 14_600_000, 0.38, "active"),
        ("J-3006", "School District Athletic Complex", "SD", 6_900_000, 1.00, "completed"),
        ("J-4001", "City Parks Annual Maintenance Contract", "LM", 4_800_000, 0.60, "active"),
        ("J-4002", "HOA Landscape Maintenance — Mesa Verde", "LM", 2_100_000, 0.75, "active"),
        ("J-4003", "Commercial Campus Grounds — Quarterly", "LM", 3_600_000, 0.50, "active"),
        ("J-4004", "Highway Median Maintenance — CDOT", "LM", 5_200_000, 0.42, "active"),
        ("J-5001", "Hillside Stabilization — Lot 14-22", "RW", 12_300_000, 0.71, "active"),
        ("J-5002", "Highway 82 Retaining Wall Replacement", "RW", 18_900_000, 0.56, "active"),
        ("J-5003", "Residential Terrace Walls — Elk Ridge", "RW", 5_400_000, 0.88, "active"),
        ("J-5004", "Bridge Abutment Reinforcement", "RW", 9_700_000, 0.44, "active"),
        ("J-5005", "Flood Channel Retaining Walls", "RW", 15_600_000, 0.33, "active"),
        ("J-5006", "Commercial Loading Dock Walls", "RW", 4_200_000, 1.00, "completed"),
        ("J-1007", "Pipeline Corridor Clearing", "EX", 11_400_000, 0.15, "on_hold"),
        ("J-2007", "Interchange Ramp Realignment", "RC", 8_900_000, 0.22, "on_hold"),
        ("J-3007", "Warehouse District Infrastructure", "SD", 19_200_000, 0.08, "on_hold"),
    ]

    jobs = []
    for jid, name, div, contract_val, pct_complete, status in job_templates:
        costs_to_date = round(contract_val * pct_complete * rng.uniform(0.88, 0.98), 2)
        labor_pct = cost_pcts[div].get("5400", 0.13)
        mat_pct = cost_pcts[div].get("5100", 0.22)
        sub_pct = cost_pcts[div].get("5300", 0.10)
        equip_pct = cost_pcts[div].get("5200", 0.06)
        other_pct = 1.0 - labor_pct - mat_pct - sub_pct - equip_pct
        jobs.append({
            "job_id": jid,
            "name": name,
            "division_id": div,
            "contract_value": contract_val,
            "status": status,
            "percent_complete": pct_complete,
            "costs": {
                "labor": round(costs_to_date * labor_pct / (labor_pct + mat_pct + sub_pct + equip_pct + other_pct), 2),
                "materials": round(costs_to_date * mat_pct / (labor_pct + mat_pct + sub_pct + equip_pct + other_pct), 2),
                "subcontractor": round(costs_to_date * sub_pct / (labor_pct + mat_pct + sub_pct + equip_pct + other_pct), 2),
                "equipment": round(costs_to_date * equip_pct / (labor_pct + mat_pct + sub_pct + equip_pct + other_pct), 2),
                "other": round(costs_to_date * other_pct / (labor_pct + mat_pct + sub_pct + equip_pct + other_pct), 2),
                "total": costs_to_date,
            },
            "estimated_completion": "2025-12" if status == "active" and pct_complete > 0.7 else "2026-06" if status == "active" else None,
            "profit_margin_pct": round((1.0 - costs_to_date / (contract_val * max(pct_complete, 0.01))) * 100, 1) if pct_complete > 0 else None,
        })

    # ── AR Aging Snapshot ──
    ar_customers = [
        ("Greenfield Development Corp", "EX", 1_240_000, 380_000, 0, 0, 0),
        ("Summit Property Group", "RC", 890_000, 420_000, 210_000, 0, 0),
        ("Parkview Associates LLC", "SD", 0, 0, 340_000, 560_000, 280_000),
        ("Riverside Municipal District", "RC", 2_100_000, 0, 0, 0, 0),
        ("Oak Valley Homes Inc", "EX", 640_000, 0, 0, 0, 0),
        ("Metro Transit Authority", "RC", 3_200_000, 1_800_000, 0, 0, 0),
        ("Cascade Energy Partners", "SD", 0, 920_000, 460_000, 0, 0),
        ("Alpine Ski Resort Corp", "RW", 780_000, 310_000, 0, 0, 0),
        ("Desert Sun Solar LLC", "SD", 1_100_000, 0, 0, 0, 0),
        ("Horizon Healthcare System", "SD", 0, 0, 0, 890_000, 420_000),
        ("CDOT Region 4", "LM", 2_400_000, 600_000, 0, 0, 0),
        ("Pinnacle Developers", "EX", 560_000, 280_000, 140_000, 0, 0),
        ("Westridge HOA", "LM", 180_000, 90_000, 45_000, 0, 0),
        ("Blue Mountain Mining Co", "EX", 0, 0, 0, 0, 1_200_000),
        ("Lakefront Properties Inc", "RW", 440_000, 220_000, 0, 0, 0),
    ]

    ar_aging_snapshot = []
    for cust, div, curr, d30, d60, d90, over90 in ar_customers:
        total = curr + d30 + d60 + d90 + over90
        ar_aging_snapshot.append({
            "customer": cust,
            "division_id": div,
            "current": curr,
            "days_1_30": d30,
            "days_31_60": d60,
            "days_61_90": d90,
            "days_over_90": over90,
            "total_outstanding": total,
        })

    # ── Backlog by Division ──
    backlog = [
        {"division_id": "EX", "contracted_backlog": 85_000_000, "expected_12mo_burn": 62_000_000, "new_awards_ytd": 48_000_000, "proposal_pipeline": 120_000_000},
        {"division_id": "RC", "contracted_backlog": 112_000_000, "expected_12mo_burn": 78_000_000, "new_awards_ytd": 65_000_000, "proposal_pipeline": 180_000_000},
        {"division_id": "SD", "contracted_backlog": 72_000_000, "expected_12mo_burn": 55_000_000, "new_awards_ytd": 41_000_000, "proposal_pipeline": 95_000_000},
        {"division_id": "LM", "contracted_backlog": 18_000_000, "expected_12mo_burn": 15_000_000, "new_awards_ytd": 12_000_000, "proposal_pipeline": 28_000_000},
        {"division_id": "RW", "contracted_backlog": 48_000_000, "expected_12mo_burn": 36_000_000, "new_awards_ytd": 29_000_000, "proposal_pipeline": 72_000_000},
    ]

    # ── Cash Flow ──
    cash_flow: list[dict] = []
    cash_balance = 24_000_000.0
    for period in periods:
        month = int(period[5:7])
        g = yoy_growth(period)
        s = seasonal[month]
        total_rev = sum(div_monthly_base[d] for d in div_monthly_base) * s * g
        cash_in = round(total_rev * rng.uniform(0.88, 0.95), 2)  # collections lag
        cash_out = round(total_rev * 0.82 * rng.uniform(0.96, 1.04), 2)  # operating disbursements
        capex = round(rng.uniform(800_000, 2_400_000), 2)
        net = round(cash_in - cash_out - capex, 2)
        cash_balance = round(cash_balance + net, 2)
        cash_flow.append({
            "period": period,
            "operating_cash_in": cash_in,
            "operating_cash_out": cash_out,
            "capital_expenditures": capex,
            "net_cash_flow": net,
            "ending_cash_balance": cash_balance,
        })

    # ── KPI Targets ──
    kpi_targets = {
        "gross_margin_target": 18.5,
        "net_margin_target": 5.2,
        "dso_target": 52,
        "overhead_ratio_target": 8.5,
        "backlog_to_revenue_target": 1.4,
        "revenue_per_employee_target": 680_000,
    }

    return {
        "company": company,
        "gl_chart": gl_chart,
        "monthly_gl": monthly_gl,
        "monthly_budget": monthly_budget,
        "jobs": jobs,
        "ar_aging_snapshot": ar_aging_snapshot,
        "backlog": backlog,
        "cash_flow": cash_flow,
        "kpi_targets": kpi_targets,
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
        financial_payload["monthly_gl"],
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
        "takeoff_data.json": build_takeoff_dataset(),
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
    print("- 5 invoice PDFs generated")
    print("- JSON scenario payloads refreshed")
    print("- Skills files restored from skills_original.md")


if __name__ == "__main__":
    main()
