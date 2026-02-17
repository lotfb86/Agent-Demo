PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS activity_logs;
DROP TABLE IF EXISTS communications;
DROP TABLE IF EXISTS review_queue;
DROP TABLE IF EXISTS agent_status;
DROP TABLE IF EXISTS collections_queue;
DROP TABLE IF EXISTS internal_tasks;
DROP TABLE IF EXISTS financial_monthly;
DROP TABLE IF EXISTS invoices;
DROP TABLE IF EXISTS purchase_orders;
DROP TABLE IF EXISTS projects;
DROP TABLE IF EXISTS vendors;
DROP TABLE IF EXISTS gl_accounts;
DROP TABLE IF EXISTS ar_aging;
DROP TABLE IF EXISTS agents;
DROP TABLE IF EXISTS divisions;

CREATE TABLE divisions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    department TEXT NOT NULL,
    description TEXT NOT NULL,
    workspace_type TEXT NOT NULL
);

CREATE TABLE agent_status (
    agent_id TEXT PRIMARY KEY REFERENCES agents(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'idle',
    current_activity TEXT NOT NULL DEFAULT 'Ready',
    last_run_at TEXT,
    cost_today REAL NOT NULL DEFAULT 0,
    tasks_completed_today INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE gl_accounts (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    category TEXT NOT NULL
);

CREATE TABLE vendors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL,
    insurance_expiry TEXT,
    contract_expiry TEXT,
    w9_on_file INTEGER NOT NULL DEFAULT 1,
    notes TEXT
);

CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    division_id TEXT NOT NULL REFERENCES divisions(id),
    budget_text TEXT NOT NULL,
    percent_complete REAL,
    pm_name TEXT NOT NULL,
    pm_email TEXT NOT NULL
);

CREATE TABLE purchase_orders (
    po_number TEXT PRIMARY KEY,
    vendor_id INTEGER NOT NULL REFERENCES vendors(id),
    amount REAL NOT NULL,
    job_id TEXT NOT NULL REFERENCES projects(id),
    gl_code TEXT NOT NULL REFERENCES gl_accounts(code),
    status TEXT NOT NULL DEFAULT 'open'
);

CREATE TABLE invoices (
    invoice_number TEXT PRIMARY KEY,
    vendor_id INTEGER NOT NULL REFERENCES vendors(id),
    amount REAL NOT NULL,
    po_reference TEXT REFERENCES purchase_orders(po_number),
    invoice_date TEXT NOT NULL,
    file_path TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    job_id TEXT REFERENCES projects(id),
    gl_code TEXT REFERENCES gl_accounts(code),
    processing_stage TEXT NOT NULL DEFAULT 'primary',
    notes TEXT
);

CREATE TABLE review_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL REFERENCES agents(id),
    item_ref TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    details TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL,
    action TEXT,
    actioned_at TEXT
);

CREATE TABLE communications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL REFERENCES agents(id),
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    channel TEXT NOT NULL DEFAULT 'email',
    created_at TEXT NOT NULL
);

CREATE TABLE activity_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL REFERENCES agents(id),
    session_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    cost REAL NOT NULL DEFAULT 0,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    timestamp TEXT NOT NULL
);

CREATE TABLE ar_aging (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name TEXT NOT NULL,
    days_out INTEGER NOT NULL,
    amount REAL NOT NULL,
    is_retainage INTEGER NOT NULL DEFAULT 0,
    notes TEXT
);

CREATE TABLE collections_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name TEXT NOT NULL,
    amount REAL NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE internal_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL REFERENCES agents(id),
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    priority TEXT NOT NULL,
    due_date TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL
);

CREATE TABLE financial_monthly (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period TEXT NOT NULL,
    division_id TEXT NOT NULL REFERENCES divisions(id),
    gl_code TEXT NOT NULL REFERENCES gl_accounts(code),
    amount REAL NOT NULL
);
