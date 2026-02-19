// Flow diagram configurations for all 11 RPMX agents
// Each config defines nodes (steps) and edges (connections) that the
// BlueprintRenderer draws as an interactive SVG flow diagram.

export const FLOW_CONFIGS = {

  /* ───────────────────── 1. PO MATCH ───────────────────── */
  po_match: {
    id: 'po_match',
    title: 'Invoice-to-PO Matching',
    subtitle: 'Accounts Payable',
    description: 'Reads vendor invoices, matches them to purchase orders, flags exceptions for human review, and posts approved invoices to the ERP system.',
    nodes: [
      { id: 'queue',         type: 'source',      col: 0, row: 1, icon: 'inbox',    label: 'Invoice Queue',      description: 'PDF invoices from vendor emails and the AP scanner.' },
      { id: 'read',          type: 'process',      col: 1, row: 1, icon: 'scan',     label: 'Read Invoice',       description: 'Extracts vendor name, dollar amount, PO reference, and line items from the PDF.',                 tools: ['read_invoice'] },
      { id: 'match',         type: 'ai_decision',  col: 2, row: 1, icon: 'brain',    label: 'AI Match Logic',     description: 'Searches purchase orders by number, vendor, and amount. Selects the best match or flags as unmatched.', tools: ['search_purchase_orders', 'select_po'] },
      { id: 'dup_check',     type: 'process',      col: 3, row: 1, icon: 'shield',   label: 'Duplicate Check',    description: 'Verifies no other invoice has already been matched to this PO.',                                    tools: ['check_duplicate'] },
      { id: 'coding',        type: 'process',      col: 4, row: 0, icon: 'tag',      label: 'Assign GL Code',     description: 'Assigns the GL account code and job ID from the matched purchase order.',                             tools: ['assign_coding'] },
      { id: 'exception',     type: 'human',        col: 4, row: 2, icon: 'user',     label: 'Human Review',       description: 'AP specialist reviews price variances, missing POs, and potential duplicates.',                      tools: ['flag_exception'] },
      { id: 'post',          type: 'output',       col: 5, row: 0, icon: 'database', label: 'Post to Vista',      description: 'Approved invoice is posted to the Vista ERP accounting system.',                                     tools: ['post_to_vista'] },
      { id: 'notify',        type: 'output',       col: 5, row: 2, icon: 'mail',     label: 'Notifications',      description: 'Emails stakeholders with match results, variance alerts, and a daily AP summary.',                   tools: ['send_notification'] },
    ],
    edges: [
      { from: 'queue',     to: 'read' },
      { from: 'read',      to: 'match' },
      { from: 'match',     to: 'dup_check',  label: 'Match found' },
      { from: 'match',     to: 'exception',  label: 'No match',       style: 'exception' },
      { from: 'dup_check', to: 'coding',     label: 'Clean' },
      { from: 'dup_check', to: 'exception',  label: 'Duplicate risk', style: 'exception' },
      { from: 'coding',    to: 'post' },
      { from: 'exception', to: 'notify' },
      { from: 'post',      to: 'notify',     label: 'Summary',        style: 'exception' },
    ],
    loop: { label: 'Repeats for each invoice in queue', startNode: 'read', endNode: 'dup_check' },
  },

  /* ───────────────────── 2. AR FOLLOW-UP ───────────────────── */
  ar_followup: {
    id: 'ar_followup',
    title: 'Accounts Receivable Follow-Up',
    subtitle: 'Accounts Receivable',
    description: 'Scans the AR aging report and takes collection actions based on how overdue each account is.',
    nodes: [
      { id: 'aging',       type: 'source',      col: 0, row: 1, icon: 'chart',    label: 'AR Aging Report',   description: 'Customer balances with days outstanding and retainage flags.' },
      { id: 'analyze',     type: 'ai_decision',  col: 1, row: 1, icon: 'brain',    label: 'AI Action Plan',    description: 'Classifies each account by aging bucket and determines the appropriate collection action.' },
      { id: 'email',       type: 'output',       col: 2, row: 0, icon: 'mail',     label: 'Send Email',        description: '30-59 days: polite reminder. 60-89 days: firm follow-up with payment terms.',                       tools: ['send_collection_email'] },
      { id: 'task',        type: 'output',       col: 3, row: 0, icon: 'clipboard', label: 'Create Task',       description: 'Internal task created for the AR team to track the follow-up.',                                      tools: ['create_internal_task'] },
      { id: 'escalate',    type: 'human',        col: 2, row: 2, icon: 'alert',    label: 'Escalate (90+ days)', description: '90+ day accounts are escalated to the collections queue for manager review.',                       tools: ['escalate_account'] },
      { id: 'skip',        type: 'process',      col: 3, row: 2, icon: 'shield',   label: 'Skip Retainage',    description: 'Retainage balances are excluded from collection actions with an explanation.' },
    ],
    edges: [
      { from: 'aging',    to: 'analyze' },
      { from: 'analyze',  to: 'email',    label: '30-89 days' },
      { from: 'analyze',  to: 'escalate', label: '90+ days',    style: 'exception' },
      { from: 'analyze',  to: 'skip',     label: 'Retainage' },
      { from: 'email',    to: 'task' },
      { from: 'escalate', to: 'task' },
    ],
  },

  /* ───────────────────── 3. FINANCIAL REPORTING ───────────────────── */
  financial_reporting: {
    id: 'financial_reporting',
    title: 'Financial Report Generation',
    subtitle: 'General Accounting',
    description: 'Generates P&L reports from the GL, compares periods, and answers financial questions conversationally.',
    nodes: [
      { id: 'gl_data',     type: 'source',      col: 0, row: 0, icon: 'database', label: 'Vista GL Data',     description: 'Monthly general ledger records across all divisions and periods.' },
      { id: 'user_query',  type: 'source',      col: 0, row: 2, icon: 'user',     label: 'User Query',        description: 'A question or report request from the accounting team (e.g., "P&L for Excavation, January").' },
      { id: 'intent',      type: 'ai_decision',  col: 1, row: 1, icon: 'brain',    label: 'AI Intent & Query', description: 'Classifies the request type (P&L, comparison, expense analysis) and builds the data query.',         tools: ['load_financial_data'] },
      { id: 'report_gen',  type: 'ai_decision',  col: 2, row: 1, icon: 'chart',    label: 'AI Report Builder', description: 'Generates the financial report with structured tables, variances, and a narrative summary.',          tools: ['generate_report'] },
      { id: 'report',      type: 'output',       col: 3, row: 0, icon: 'clipboard', label: 'P&L Report',        description: 'Formatted profit & loss statement with revenue, COGS, gross profit, OpEx, and net income.' },
      { id: 'narrative',   type: 'output',       col: 3, row: 2, icon: 'mail',     label: 'Narrative Summary',  description: 'Plain-language summary of key trends, variances, and recommendations.' },
    ],
    edges: [
      { from: 'gl_data',    to: 'intent' },
      { from: 'user_query', to: 'intent' },
      { from: 'intent',     to: 'report_gen' },
      { from: 'report_gen', to: 'report' },
      { from: 'report_gen', to: 'narrative' },
    ],
  },

  /* ───────────────────── 4. VENDOR COMPLIANCE ───────────────────── */
  vendor_compliance: {
    id: 'vendor_compliance',
    title: 'Vendor Compliance Monitor',
    subtitle: 'Procurement',
    description: 'Scans all active vendors for insurance, W-9, contract, and licensing gaps, then takes corrective action.',
    nodes: [
      { id: 'vendors',     type: 'source',      col: 0, row: 1, icon: 'building', label: 'Vendor Records',    description: 'Active vendor list with insurance expiry dates, W-9 status, contract terms, and license info.' },
      { id: 'scan',        type: 'ai_decision',  col: 1, row: 1, icon: 'brain',    label: 'AI Compliance Scan', description: 'Evaluates each vendor against compliance thresholds: 14-day insurance warning, missing W-9, 30-day contract expiry.' },
      { id: 'renewal',     type: 'output',       col: 2, row: 0, icon: 'mail',     label: 'Renewal Email',     description: 'Sends insurance renewal reminder to vendors expiring within 14 days.' },
      { id: 'w9',          type: 'output',       col: 3, row: 0, icon: 'mail',     label: 'W-9 Request',       description: 'Requests missing W-9 tax documentation from the vendor.' },
      { id: 'hold',        type: 'human',        col: 2, row: 2, icon: 'alert',    label: 'Urgent Hold',       description: 'Vendors with expired insurance are placed on hold. Procurement manager reviews before reactivation.', tools: ['flag_vendor'] },
      { id: 'contract',    type: 'output',       col: 3, row: 2, icon: 'clipboard', label: 'Contract Task',     description: 'Internal task created to renew contracts expiring within 30 days.' },
    ],
    edges: [
      { from: 'vendors', to: 'scan' },
      { from: 'scan',    to: 'renewal',  label: 'Expiring' },
      { from: 'scan',    to: 'w9',       label: 'Missing W-9' },
      { from: 'scan',    to: 'hold',     label: 'Expired',       style: 'exception' },
      { from: 'scan',    to: 'contract', label: 'Contract due' },
    ],
  },

  /* ───────────────────── 5. SCHEDULE OPTIMIZER ───────────────────── */
  schedule_optimizer: {
    id: 'schedule_optimizer',
    title: 'Crew Schedule Optimization',
    subtitle: 'Scheduling',
    description: 'Assigns landscaping jobs to crews based on skills and geography, minimizing drive time.',
    nodes: [
      { id: 'jobs',       type: 'source',      col: 0, row: 0, icon: 'clipboard', label: 'Dispatch Jobs',     description: '12 landscaping jobs with locations, GPS coordinates, and required crew skills.' },
      { id: 'crews',      type: 'source',      col: 0, row: 2, icon: 'users',     label: 'Available Crews',   description: '3 crews with skill sets (mow, edge, prune, irrigate) and current locations.' },
      { id: 'optimize',   type: 'ai_decision',  col: 1, row: 1, icon: 'brain',    label: 'AI Route Optimizer', description: 'Matches jobs to crews by skill first, then clusters nearby jobs to minimize drive time.', tools: ['optimize_routes'] },
      { id: 'routes',     type: 'output',       col: 2, row: 1, icon: 'route',    label: 'Optimized Routes',  description: 'Ordered job assignments per crew with calculated drive times.' },
      { id: 'savings',    type: 'output',       col: 3, row: 0, icon: 'clock',    label: 'Time Savings',      description: 'Comparison of optimized vs. baseline drive time (target: 20%+ improvement).' },
      { id: 'dispatch',   type: 'human',        col: 3, row: 2, icon: 'user',     label: 'Dispatcher Review', description: 'Dispatch manager confirms assignments and adjusts for crew availability.' },
    ],
    edges: [
      { from: 'jobs',     to: 'optimize' },
      { from: 'crews',    to: 'optimize' },
      { from: 'optimize', to: 'routes' },
      { from: 'routes',   to: 'savings' },
      { from: 'routes',   to: 'dispatch' },
    ],
  },

  /* ───────────────────── 6. PROGRESS TRACKING ───────────────────── */
  progress_tracking: {
    id: 'progress_tracking',
    title: 'Project Health Dashboard',
    subtitle: 'Project Management',
    description: 'Analyzes budget burn vs. completion for each project and flags at-risk jobs.',
    nodes: [
      { id: 'projects',    type: 'source',      col: 0, row: 1, icon: 'building', label: 'Project Data',      description: 'Active projects with budget totals, actual spend, percent complete, and schedule status.' },
      { id: 'classify',    type: 'ai_decision',  col: 1, row: 1, icon: 'brain',    label: 'AI Health Check',   description: 'Analyzes each project: compares budget burn to completion, detects schedule slippage, classifies as on-track / at-risk / behind.' },
      { id: 'variance',    type: 'process',      col: 2, row: 1, icon: 'chart',    label: 'Variance Calc',     description: 'Calculates dollar and percentage variance between expected and actual cost at current completion.' },
      { id: 'findings',    type: 'output',       col: 3, row: 0, icon: 'clipboard', label: 'Findings & Recs',   description: 'Per-project findings with status color (green/amber/red), variance data, and recommendations.' },
      { id: 'pm_review',   type: 'human',        col: 3, row: 2, icon: 'user',     label: 'PM Escalation',     description: 'Project managers review at-risk and behind-schedule projects for corrective action.' },
    ],
    edges: [
      { from: 'projects', to: 'classify' },
      { from: 'classify', to: 'variance' },
      { from: 'variance', to: 'findings',  label: 'On track' },
      { from: 'variance', to: 'pm_review', label: 'At risk / Behind', style: 'exception' },
      { from: 'pm_review', to: 'findings' },
    ],
  },

  /* ───────────────────── 7. MAINTENANCE SCHEDULER ───────────────────── */
  maintenance_scheduler: {
    id: 'maintenance_scheduler',
    title: 'Equipment Maintenance Scheduler',
    subtitle: 'Fleet & Equipment',
    description: 'Scans the fleet for overdue service, safety inspections, and upcoming maintenance windows.',
    nodes: [
      { id: 'equipment',   type: 'source',      col: 0, row: 1, icon: 'truck',    label: 'Equipment Records', description: '30 units: excavators, loaders, trucks, and generators with service dates, hour meters, and inspection logs.' },
      { id: 'detect',      type: 'ai_decision',  col: 1, row: 1, icon: 'brain',    label: 'AI Issue Detection', description: 'Identifies overdue maintenance, missed safety inspections, and hour-meter thresholds.' },
      { id: 'severity',    type: 'process',      col: 2, row: 1, icon: 'alert',    label: 'Severity Rating',   description: 'Classifies each issue as critical, high, medium, or low based on safety impact and overdue duration.' },
      { id: 'tasks',       type: 'output',       col: 3, row: 0, icon: 'clipboard', label: 'Work Orders',       description: 'Maintenance tasks created with priority, description, and recommended downtime window.' },
      { id: 'maint_mgr',   type: 'human',        col: 3, row: 2, icon: 'user',     label: 'Maintenance Mgr',   description: 'Fleet manager schedules work orders around project timelines and equipment availability.' },
    ],
    edges: [
      { from: 'equipment', to: 'detect' },
      { from: 'detect',    to: 'severity' },
      { from: 'severity',  to: 'tasks',      label: 'Critical / High' },
      { from: 'severity',  to: 'maint_mgr',  label: 'All issues' },
      { from: 'maint_mgr', to: 'tasks',      style: 'exception' },
    ],
  },

  /* ───────────────────── 8. TRAINING COMPLIANCE ───────────────────── */
  training_compliance: {
    id: 'training_compliance',
    title: 'Safety Training Audit',
    subtitle: 'Safety',
    description: 'Audits employee certifications for OSHA, first aid, equipment operation, and new-hire orientation.',
    nodes: [
      { id: 'certs',       type: 'source',      col: 0, row: 1, icon: 'users',    label: 'HR Certifications', description: '40 employees with OSHA expiry, first aid expiry, equipment cert status, and orientation dates.' },
      { id: 'audit',       type: 'ai_decision',  col: 1, row: 1, icon: 'brain',    label: 'AI Cert Audit',     description: 'Flags certifications expiring within 30 days, missing equipment certs, and new hires without orientation.' },
      { id: 'classify',    type: 'process',      col: 2, row: 1, icon: 'tag',      label: 'Issue Classification', description: 'Categorizes each finding: expired, expiring soon, missing certification, or new hire gap.' },
      { id: 'tasks',       type: 'output',       col: 3, row: 0, icon: 'clipboard', label: 'Remediation Tasks', description: 'Training tasks created with priority and due dates for each non-compliant employee.' },
      { id: 'hr',          type: 'human',        col: 3, row: 2, icon: 'user',     label: 'HR Scheduling',     description: 'HR manager schedules training sessions and tracks completion.' },
    ],
    edges: [
      { from: 'certs',    to: 'audit' },
      { from: 'audit',    to: 'classify' },
      { from: 'classify', to: 'tasks' },
      { from: 'classify', to: 'hr' },
      { from: 'hr',       to: 'tasks',  style: 'exception' },
    ],
  },

  /* ───────────────────── 9. ONBOARDING ───────────────────── */
  onboarding: {
    id: 'onboarding',
    title: 'New Hire Onboarding',
    subtitle: 'Human Resources',
    description: 'Builds a role-specific onboarding checklist, tracks document and training completion, and sends a welcome email.',
    nodes: [
      { id: 'hire',        type: 'source',      col: 0, row: 1, icon: 'user',      label: 'New Hire Profile',  description: 'Employee name, role, division, start date, and hiring manager information.' },
      { id: 'checklist',   type: 'ai_decision',  col: 1, row: 1, icon: 'brain',     label: 'AI Checklist Builder', description: 'Generates a role-specific onboarding checklist covering documents, training requirements, and equipment.' },
      { id: 'docs',        type: 'process',      col: 2, row: 0, icon: 'clipboard', label: 'Documents',         description: 'W-4, I-9, direct deposit, handbook acknowledgment. Statuses set based on what has been submitted.' },
      { id: 'training',    type: 'process',      col: 2, row: 1, icon: 'shield',   label: 'Training',          description: 'OSHA 10-Hour, equipment operator certification, site safety orientation.' },
      { id: 'equipment',   type: 'process',      col: 2, row: 2, icon: 'wrench',   label: 'Equipment',         description: 'Hard hat, safety vest, steel-toe boots, radio — issued based on role requirements.' },
      { id: 'welcome',     type: 'output',       col: 3, row: 0, icon: 'mail',     label: 'Welcome Email',     description: 'Personalized welcome email sent to the new hire with first-day details and contact info.' },
      { id: 'hr_complete', type: 'human',        col: 3, row: 2, icon: 'user',     label: 'HR Completes',      description: 'HR manager and hiring manager work through the checklist, marking items complete.' },
    ],
    edges: [
      { from: 'hire',       to: 'checklist' },
      { from: 'checklist',  to: 'docs' },
      { from: 'checklist',  to: 'training' },
      { from: 'checklist',  to: 'equipment' },
      { from: 'docs',       to: 'welcome' },
      { from: 'training',   to: 'hr_complete' },
      { from: 'equipment',  to: 'hr_complete' },
    ],
  },

  /* ───────────────────── 10. COST ESTIMATOR ───────────────────── */
  cost_estimator: {
    id: 'cost_estimator',
    title: 'Contract Cost Estimator',
    subtitle: 'Estimating',
    description: 'Builds a detailed cost estimate from project scope: labor, materials, equipment, markups, and assumptions.',
    nodes: [
      { id: 'scope',       type: 'source',      col: 0, row: 1, icon: 'clipboard', label: 'Project Scope',     description: 'Takeoff data with quantities, categories, labor hours per unit, material and equipment costs.' },
      { id: 'labor',       type: 'process',      col: 1, row: 0, icon: 'users',    label: 'Labor Calculation',  description: 'Phase 2: Hours times burdened labor rate per scope item.' },
      { id: 'materials',   type: 'process',      col: 1, row: 1, icon: 'building', label: 'Material Pricing',   description: 'Phase 3: Quantity times material cost per unit for each line item.' },
      { id: 'equip',       type: 'process',      col: 1, row: 2, icon: 'truck',    label: 'Equipment Costs',    description: 'Phase 4: Quantity times equipment cost per unit for required machinery.' },
      { id: 'assemble',    type: 'ai_decision',  col: 2, row: 1, icon: 'brain',    label: 'AI Estimate Assembly', description: 'Combines all cost components, applies markups (overhead, profit, contingency, bond, mobilization), generates assumptions and exclusions.' },
      { id: 'estimate',    type: 'output',       col: 3, row: 0, icon: 'dollar',   label: 'Cost Estimate',     description: 'Complete estimate with 10+ line items, category subtotals, markup breakdown, and grand total.' },
      { id: 'review',      type: 'human',        col: 3, row: 2, icon: 'user',     label: 'Estimator Review',  description: 'Senior estimator reviews for reasonableness, adjusts contingency, and submits for client approval.' },
    ],
    edges: [
      { from: 'scope',     to: 'labor' },
      { from: 'scope',     to: 'materials' },
      { from: 'scope',     to: 'equip' },
      { from: 'labor',     to: 'assemble' },
      { from: 'materials', to: 'assemble' },
      { from: 'equip',     to: 'assemble' },
      { from: 'assemble',  to: 'estimate' },
      { from: 'assemble',  to: 'review' },
    ],
  },

  /* ───────────────────── 11. INQUIRY ROUTER ───────────────────── */
  inquiry_router: {
    id: 'inquiry_router',
    title: 'Customer Inquiry Router',
    subtitle: 'Customer Service',
    description: 'Reads inbound customer emails, classifies the inquiry type, and routes to the correct department with priority.',
    nodes: [
      { id: 'emails',      type: 'source',      col: 0, row: 1, icon: 'inbox',    label: 'Inbound Emails',    description: '8 customer emails covering billing questions, missed service complaints, quote requests, and general inquiries.' },
      { id: 'classify',    type: 'ai_decision',  col: 1, row: 1, icon: 'brain',    label: 'AI Classification', description: 'Reads each email, extracts key details, classifies as billing / service / quote / general, and sets priority.', tools: ['classify_inquiry'] },
      { id: 'ar',          type: 'output',       col: 2, row: 0, icon: 'dollar',   label: 'Route: AR',         description: 'Billing and payment questions routed to Accounts Receivable.' },
      { id: 'dispatch',    type: 'output',       col: 3, row: 0, icon: 'truck',    label: 'Route: Dispatch',   description: 'Missed or urgent service issues routed to Dispatch (urgent priority).' },
      { id: 'estimating',  type: 'output',       col: 2, row: 2, icon: 'clipboard', label: 'Route: Estimating', description: 'Quote requests flagged as new opportunities and routed to the Estimating team.' },
      { id: 'management',  type: 'output',       col: 3, row: 2, icon: 'building', label: 'Route: Management', description: 'General inquiries and escalations routed to Management.' },
      { id: 'dept_review', type: 'human',        col: 4, row: 1, icon: 'user',     label: 'Department Review', description: 'Receiving department reviews the routed email and takes action.' },
    ],
    edges: [
      { from: 'emails',    to: 'classify' },
      { from: 'classify',  to: 'ar',         label: 'Billing' },
      { from: 'classify',  to: 'dispatch',   label: 'Service' },
      { from: 'classify',  to: 'estimating', label: 'Quote' },
      { from: 'classify',  to: 'management', label: 'General' },
      { from: 'ar',        to: 'dept_review' },
      { from: 'dispatch',  to: 'dept_review' },
      { from: 'estimating', to: 'dept_review' },
      { from: 'management', to: 'dept_review' },
    ],
  },
}
