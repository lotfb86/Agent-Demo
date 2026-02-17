INSERT INTO divisions (id, name) VALUES
  ('EX', 'Excavation'),
  ('RC', 'Road Construction'),
  ('SD', 'Site Development'),
  ('LM', 'Landscaping Maintenance'),
  ('RW', 'Retaining Walls');

INSERT INTO agents (id, name, department, description, workspace_type) VALUES
  ('po_match', 'PO Match Agent', 'Accounts Payable', 'Matches invoice PDFs to purchase orders, assigns coding, flags exceptions, and posts to ERP.', 'invoice'),
  ('ar_followup', 'AR Follow-Up Agent', 'Accounts Receivable', 'Processes aging data and executes collection actions by delinquency bucket.', 'email'),
  ('financial_reporting', 'Financial Reporting Agent', 'General Accounting', 'Builds conversational P&L and comparison reports across divisions and periods.', 'report'),
  ('vendor_compliance', 'Vendor Compliance Monitor', 'Procurement', 'Scans vendor records for expiring insurance, missing W-9s, and contract risks.', 'table'),
  ('schedule_optimizer', 'Schedule Optimizer', 'Scheduling', 'Optimizes crew assignments and route sequences across job sites.', 'map'),
  ('progress_tracking', 'Progress Tracking Agent', 'Project Management', 'Flags budget and schedule risks across active projects.', 'table'),
  ('maintenance_scheduler', 'Maintenance Scheduler', 'Fleet & Equipment', 'Identifies upcoming and overdue fleet maintenance and schedules work orders.', 'table'),
  ('training_compliance', 'Training Compliance Agent', 'Safety', 'Finds expiring and missing safety certifications for employees.', 'table'),
  ('onboarding', 'Onboarding Agent', 'Human Resources', 'Runs end-to-end onboarding workflow for new hires.', 'checklist'),
  ('cost_estimator', 'Cost Estimator', 'Estimating', 'Builds contract pricing from productivity rates, overhead, and margin targets.', 'report'),
  ('inquiry_router', 'Inquiry Router', 'Customer Service', 'Routes inbound customer emails to the correct operational queue.', 'email');

INSERT INTO agent_status (agent_id, status, current_activity, cost_today, tasks_completed_today)
SELECT id, 'idle', 'Ready', 0, 0 FROM agents;

INSERT INTO gl_accounts (code, name, type, category) VALUES
  ('4100', 'Contract Revenue', 'Revenue', 'Revenue'),
  ('4200', 'Service Revenue', 'Revenue', 'Revenue'),
  ('4300', 'T&M Revenue', 'Revenue', 'Revenue'),
  ('5100', 'Materials', 'Expense', 'COGS — Direct'),
  ('5200', 'Equipment Rental', 'Expense', 'COGS — Direct'),
  ('5300', 'Subcontractor Costs', 'Expense', 'COGS — Direct'),
  ('5400', 'Direct Labor', 'Expense', 'COGS — Direct'),
  ('5500', 'Fuel & Lubricants', 'Expense', 'COGS — Direct'),
  ('5600', 'Hauling & Trucking', 'Expense', 'COGS — Direct'),
  ('5700', 'Permits & Fees', 'Expense', 'COGS — Direct'),
  ('6100', 'Salaries — Office', 'Expense', 'Operating'),
  ('6200', 'Benefits & Insurance', 'Expense', 'Operating'),
  ('6300', 'Rent & Utilities', 'Expense', 'Operating'),
  ('6400', 'Vehicle Expense', 'Expense', 'Operating'),
  ('6500', 'Professional Services', 'Expense', 'Operating'),
  ('6600', 'Office Supplies', 'Expense', 'Operating'),
  ('6700', 'Depreciation', 'Expense', 'Operating'),
  ('6800', 'Repairs & Maintenance', 'Expense', 'Operating');
