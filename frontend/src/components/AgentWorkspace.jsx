import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { apiGet, apiPost, apiPut, wsUrl } from '../api'
import ArtifactRenderer from './ArtifactRenderer'

const TABS = ['work', 'review', 'comms', 'chat', 'training', 'profile']
const FINANCIAL_TABS = ['work', 'history', 'comms', 'chat', 'training', 'profile']

const TOOL_LABELS = {
  // PO Match
  read_invoice: 'Reading Invoice',
  search_purchase_orders: 'Searching Purchase Orders',
  select_po: 'Selecting Purchase Order',
  check_duplicate: 'Checking for Duplicates',
  assign_coding: 'Assigning GL Code',
  mark_complete: 'Marking Complete',
  post_to_vista: 'Posting to Vista',
  flag_exception: 'Flagging Exception',
  get_project_details: 'Looking Up Project',
  send_notification: 'Sending Notification',
  complete_invoice: 'Completing Invoice',
  // AR Follow-Up
  scan_ar_aging: 'Scanning AR Aging',
  determine_action: 'Determining Action',
  escalate_account: 'Escalating Account',
  // Financial Reporting
  load_financial_data: 'Loading Financial Data',
  generate_report: 'Generating Report',
  compile_narrative: 'Compiling Narrative',
  connect_vista_api: 'Connecting to Vista',
  query_financial_data: 'Querying Financial Data',
  aggregate_results: 'Aggregating Results',
  // Vendor Compliance
  scan_vendor_records: 'Scanning Vendor Records',
  check_vendor: 'Checking Vendor',
  // Schedule Optimizer
  load_dispatch_data: 'Loading Dispatch Data',
  optimize_routes: 'Optimizing Routes',
  assign_crew: 'Assigning Crew',
  // Progress Tracking
  analyze_project_progress: 'Analyzing Projects',
  assess_project: 'Assessing Project',
  pull_job_cost_reports: 'Pulling Job Cost Data',
  analyze_job_costs: 'Analyzing Job Costs',
  generate_dashboard: 'Building Dashboard',
  // Maintenance Scheduler
  scan_maintenance_records: 'Scanning Equipment',
  inspect_unit: 'Inspecting Unit',
  // Training Compliance
  audit_employee_certifications: 'Auditing Certifications',
  check_employee: 'Checking Employee',
  // Onboarding
  load_new_hire: 'Loading New Hire',
  run_onboarding_workflow: 'Running Onboarding',
  prepare_documents: 'Preparing Documents',
  prepare_training: 'Preparing Training',
  prepare_equipment: 'Preparing Equipment',
  // Cost Estimator
  load_takeoff_data: 'Reading Takeoff Data',
  calculate_labor_costs: 'Calculating Labor',
  price_materials: 'Pricing Materials',
  calculate_equipment_costs: 'Equipment Costs',
  apply_markups: 'Applying Markups',
  generate_estimate: 'Generating Estimate',
  // Inquiry Router
  load_inquiry_emails: 'Loading Inbox',
  route_inquiries: 'Routing Inquiries',
  route_email: 'Routing Email',
  // Generic / additional
  llm_analysis: 'LLM Analysis',
  classify_intent: 'Classifying Intent',
  classify_inquiry: 'Classifying Inquiry',
  send_collection_email: 'Sending Collection Email',
  create_internal_task: 'Creating Internal Task',
  send_renewal_request: 'Sending Renewal Request',
  create_compliance_task: 'Creating Compliance Task',
  load_project_data: 'Loading Project Data',
  analyze_project_health: 'Analyzing Project Health',
  track_project_health: 'Tracking Project Health',
  schedule_maintenance: 'Scheduling Maintenance',
  send_welcome_email: 'Sending Welcome Email',
  apply_labor_rates: 'Applying Labor Rates',
}

const TOOL_DESCRIPTIONS = {
  // PO Match
  read_invoice: 'Extract vendor, amount, PO reference, and line items from PDF invoice',
  search_purchase_orders: 'Find matching POs by number, vendor name, or amount',
  select_po: 'Choose the best-matching purchase order for an invoice',
  check_duplicate: 'Verify no other invoice already matched to this PO',
  assign_coding: 'Assign GL account code and job ID to the invoice',
  mark_complete: 'Mark invoice as successfully matched',
  post_to_vista: 'Post approved invoice to Vista ERP system',
  flag_exception: 'Route invoice to human review queue with reason',
  get_project_details: 'Look up project manager and job details',
  send_notification: 'Email stakeholder about invoice status or variance',
  complete_invoice: 'Finalize invoice processing with confidence score',
  // AR Follow-Up
  scan_ar_aging: 'Load aging buckets and identify overdue accounts',
  determine_action: 'Choose collection action based on aging tier',
  send_collection_email: 'Send polite or firm reminder email to customer',
  create_internal_task: 'Create follow-up task for internal team',
  escalate_account: 'Move account to collections queue',
  // Financial Reporting
  classify_intent: 'Determine report type from user request',
  connect_vista_api: 'Establish connection to Vista accounting system',
  query_financial_data: 'Pull GL records for the requested period',
  aggregate_results: 'Summarize financial data by division or category',
  generate_report: 'Build structured P&L or expense report',
  compile_narrative: 'Write executive summary with margin analysis',
  load_financial_data: 'Load raw financial data from Vista export',
  // Vendor Compliance
  scan_vendor_records: 'Load all vendor documents and expiry dates',
  check_vendor: 'Audit one vendor for insurance, W-9, and contract status',
  send_renewal_request: 'Email vendor requesting updated documents',
  create_compliance_task: 'Create compliance remediation or renewal task',
  // Schedule Optimizer
  load_dispatch_data: 'Load job locations, crew skills, and yard position',
  optimize_routes: 'Calculate optimal crew-to-job assignments by proximity',
  assign_crew: 'Finalize and save crew route assignments',
  // Progress Tracking
  load_project_data: 'Load budget, schedule, and completion data per project',
  analyze_project_health: 'Compare burn rate to completion percentage',
  track_project_health: 'Flag at-risk projects with recommendations',
  // Maintenance Scheduler
  scan_maintenance_records: 'Load fleet service history and due dates',
  inspect_unit: 'Check one unit for overdue or upcoming maintenance',
  schedule_maintenance: 'Create work order with priority and timing',
  // Training Compliance
  audit_employee_certifications: 'Load all employee cert records',
  check_employee: 'Check one employee for OSHA, equipment, and orientation',
  // Onboarding
  load_new_hire: 'Load new employee details and requirements',
  prepare_documents: 'Track required HR documents and completion status',
  prepare_training: 'Schedule orientation and assign required training',
  prepare_equipment: 'Assign PPE and equipment needs by role',
  send_welcome_email: 'Send onboarding notification to hiring manager',
  // Cost Estimator
  load_takeoff_data: 'Parse scope quantities from the contract',
  apply_labor_rates: 'Calculate labor hours and cost per line item',
  apply_markups: 'Add overhead, profit, contingency, and bond',
  generate_estimate: 'Produce the final estimate with assumptions',
  // Inquiry Router
  classify_inquiry: 'Identify inquiry type and extract key references',
  route_email: 'Route to correct department with priority and context',
}

const CHAT_PROMPTS = {
  po_match: ['Why the exceptions?', 'Match confidence levels', 'Any duplicate POs?'],
  ar_followup: ['Which accounts were escalated?', 'Why skip retainage?', 'Email tone summary'],
  financial_reporting: ['Margin trends?', 'Biggest cost driver?', 'Division comparison'],
  vendor_compliance: ['Which vendors need PO holds?', 'Expiring this week?', 'Missing W-9s?'],
  schedule_optimizer: ['Drive time saved?', 'Why that crew assignment?', 'Unassigned jobs?'],
  progress_tracking: ['Which projects at risk?', 'Budget concerns?', 'Schedule slippage?'],
  maintenance_scheduler: ["What's critical?", 'Overdue inspections?', 'Next scheduled?'],
  training_compliance: ['Who needs training now?', 'OSHA expirations?', 'New hires missing certs?'],
  onboarding: ["What's still pending?", 'Equipment needed?', 'Orientation scheduled?'],
  cost_estimator: ['Break down the estimate', 'What assumptions?', 'Markup percentages?'],
  inquiry_router: ['How were emails classified?', 'Urgent items?', 'Routing accuracy?'],
}

function fmtMoney(value) {
  return `$${Number(value || 0).toFixed(2)}`
}

function fmtTs(ts) {
  if (!ts) return ''
  return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function humanToolName(tool) {
  return TOOL_LABELS[tool] || tool?.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()) || 'Processing'
}

function extractToolCallDetail(payload) {
  const tool = payload?.tool || ''
  const args = payload?.args || {}
  if (tool === 'read_invoice') return args.file_path?.replace('data/invoices/', '') || ''
  if (tool === 'search_purchase_orders') {
    const parts = []
    if (args.po_number) parts.push(args.po_number)
    if (args.vendor) parts.push(args.vendor)
    if (args.amount) parts.push(`$${Number(args.amount).toLocaleString()}`)
    return parts.join(' | ')
  }
  if (tool === 'assign_coding') return `${args.gl_code || ''} ${args.job_id ? `/ ${args.job_id}` : ''}`
  if (tool === 'flag_exception') return args.reason_code?.replace(/_/g, ' ') || ''
  if (tool === 'send_notification') return args.recipient || ''
  if (tool === 'complete_invoice') return `${args.final_status || ''} (${args.confidence || 'high'})`
  const keys = Object.keys(args)
  if (keys.length === 0) return ''
  if (keys.length <= 2) return keys.map((k) => `${args[k]}`).join(', ')
  return ''
}

function extractToolResultDetail(payload) {
  const tool = payload?.tool || ''
  const result = payload?.result || {}
  if (tool === 'search_purchase_orders' && result.matches) {
    const matches = result.matches
    if (matches.length === 0) return 'No matches found'
    const best = matches[0]
    return `${best.po_number} | $${Number(best.amount).toLocaleString()} | ${(best.confidence * 100).toFixed(0)}% confidence`
  }
  if (tool === 'read_invoice' && result.vendor) {
    return `${result.vendor} | ${result.invoice_number || ''} | $${Number(result.total || 0).toLocaleString()}`
  }
  if (tool === 'check_duplicate' && result.duplicates) {
    return result.duplicates.length === 0 ? 'No duplicates found' : `${result.duplicates.length} duplicate(s) detected`
  }
  if (tool === 'assign_coding') return `GL ${result.gl_code || ''} / Job ${result.job_id || ''}`
  if (tool === 'flag_exception') return result.reason?.replace(/_/g, ' ') || ''
  return ''
}

/* ── Grouped activity events: pair tool_call + tool_result ── */
function groupEvents(events) {
  const grouped = []
  let i = 0
  while (i < events.length) {
    const ev = events[i]
    if (
      ev.type === 'tool_call' &&
      i + 1 < events.length &&
      events[i + 1].type === 'tool_result' &&
      events[i + 1].payload?.tool === ev.payload?.tool
    ) {
      grouped.push({ kind: 'tool_pair', call: ev, result: events[i + 1], key: `${ev.timestamp}-${i}` })
      i += 2
    } else {
      grouped.push({ kind: 'single', event: ev, key: `${ev.timestamp}-${i}` })
      i += 1
    }
  }
  return grouped
}

/* ── Inline SVG icons ── */
const IconThink = () => (
  <svg className="h-3.5 w-3.5 shrink-0 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
  </svg>
)
const IconTool = () => (
  <svg className="h-3.5 w-3.5 shrink-0 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
    <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
  </svg>
)
const IconCheck = () => (
  <svg className="h-3.5 w-3.5 shrink-0 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
)
const IconMail = () => (
  <svg className="h-3.5 w-3.5 shrink-0 text-fuchsia-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
  </svg>
)
const IconAlert = () => (
  <svg className="h-3.5 w-3.5 shrink-0 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
  </svg>
)

/* ── Event rendering components ── */
function ReasoningEvent({ event }) {
  const text = event.payload?.text || ''
  // Detect invoice start lines
  const isInvoiceStart = /Processing\s+INV-/i.test(text)
  if (isInvoiceStart) {
    return (
      <div className="flex items-center gap-2 rounded-lg bg-indigo-50/60 px-3 py-2 text-xs text-indigo-700 animate-slide-in">
        <span className="font-semibold">{text}</span>
      </div>
    )
  }
  return (
    <div className="flex gap-2 border-l-[3px] border-blue-200 py-1.5 pl-3 pr-2 text-xs animate-slide-in">
      <IconThink />
      <p className="italic text-rpmx-steel leading-relaxed">{text}</p>
    </div>
  )
}

function ToolPairEvent({ call, result }) {
  const toolName = humanToolName(call.payload?.tool)
  const callDetail = extractToolCallDetail(call.payload)
  const summary = result.payload?.summary || ''
  const resultDetail = extractToolResultDetail(result.payload)

  return (
    <div className="rounded-lg border border-rpmx-slate/40 bg-white text-xs animate-slide-in overflow-hidden">
      <div className="flex items-center gap-2 border-l-[3px] border-amber-400 bg-amber-50/40 px-3 py-2">
        <IconTool />
        <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold text-amber-800">{toolName}</span>
        {callDetail && <span className="text-rpmx-steel truncate">{callDetail}</span>}
      </div>
      <div className="flex items-start gap-2 border-l-[3px] border-emerald-400 bg-emerald-50/30 px-3 py-2">
        <IconCheck />
        <div className="min-w-0">
          <p className="text-rpmx-ink">{summary}</p>
          {resultDetail && <p className="mt-0.5 text-[10px] text-rpmx-steel">{resultDetail}</p>}
        </div>
      </div>
    </div>
  )
}

function ToolCallEvent({ event }) {
  const toolName = humanToolName(event.payload?.tool)
  const detail = extractToolCallDetail(event.payload)
  return (
    <div className="flex items-center gap-2 border-l-[3px] border-amber-400 bg-amber-50/40 rounded-lg px-3 py-2 text-xs animate-slide-in">
      <IconTool />
      <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold text-amber-800">{toolName}</span>
      {detail && <span className="text-rpmx-steel truncate">{detail}</span>}
    </div>
  )
}

function ToolResultEvent({ event }) {
  const summary = event.payload?.summary || 'Completed'
  const detail = extractToolResultDetail(event.payload)
  return (
    <div className="flex items-start gap-2 border-l-[3px] border-emerald-400 bg-emerald-50/30 rounded-lg px-3 py-2 text-xs animate-slide-in">
      <IconCheck />
      <div className="min-w-0">
        <p className="text-rpmx-ink">{summary}</p>
        {detail && <p className="mt-0.5 text-[10px] text-rpmx-steel">{detail}</p>}
      </div>
    </div>
  )
}

function StatusChangeEvent({ event }) {
  return (
    <div className="flex items-center justify-center gap-2 py-1 text-[10px] text-indigo-500 animate-fade-in">
      <span className="h-px flex-1 bg-indigo-200/60" />
      <span className="px-2 font-medium">{event.payload?.detail || 'Status changed'}</span>
      <span className="h-px flex-1 bg-indigo-200/60" />
    </div>
  )
}

function CommunicationEvent({ event }) {
  return (
    <div className="flex items-start gap-2 border-l-[3px] border-fuchsia-400 bg-fuchsia-50/40 rounded-lg px-3 py-2 text-xs animate-slide-in">
      <IconMail />
      <div className="min-w-0">
        <p className="font-semibold text-fuchsia-800">{event.payload?.subject || 'Email sent'}</p>
        <p className="text-rpmx-steel">To: {event.payload?.recipient || 'recipient'}</p>
      </div>
    </div>
  )
}

const UNIT_LABELS = {
  po_match: 'invoice',
  ar_followup: 'account',
  inquiry_router: 'email',
  financial_reporting: 'report',
  vendor_compliance: 'vendor audited',
  schedule_optimizer: 'route optimized',
  progress_tracking: 'project analyzed',
  maintenance_scheduler: 'unit inspected',
  training_compliance: 'employee checked',
  onboarding: 'hire onboarded',
  cost_estimator: 'estimate',
}

function CompleteEvent({ event, agentId }) {
  const metrics = event.payload?.metrics || {}
  const totalCost = Number(metrics.cost || 0)
  const units = metrics.units_processed || 1
  const costPerUnit = Number(metrics.cost_per_unit || (totalCost / units))
  const unitLabel = UNIT_LABELS[agentId] || 'item'
  const unitLabelPlural = units === 1 ? unitLabel : unitLabel + 's'
  const statusText = `${units} ${unitLabelPlural} processed`
  return (
    <div className="rounded-lg bg-gradient-to-r from-emerald-50 to-blue-50 border border-emerald-200 px-3 py-3 text-xs animate-fade-in">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <IconCheck />
          <span className="font-semibold text-emerald-800">Run Complete</span>
        </div>
        <span className="text-rpmx-steel">{statusText}</span>
      </div>
      <div className="mt-2 flex items-baseline gap-4">
        <div>
          <span className="text-rpmx-steel">Cost per {unitLabel}: </span>
          <b className="text-base text-rpmx-ink">${costPerUnit < 0.01 ? costPerUnit.toFixed(4) : costPerUnit.toFixed(2)}</b>
        </div>
        <div className="text-rpmx-steel">
          Total: <b className="text-rpmx-ink">${totalCost < 0.01 ? totalCost.toFixed(4) : totalCost.toFixed(2)}</b>
        </div>
      </div>
    </div>
  )
}

function ErrorEvent({ event }) {
  return (
    <div className="flex items-start gap-2 border-l-[3px] border-red-400 bg-red-50 rounded-lg px-3 py-2 text-xs animate-fade-in">
      <IconAlert />
      <p className="text-red-700">{event.payload?.message || 'An error occurred'}</p>
    </div>
  )
}

function ThinkingIndicator() {
  return (
    <div className="flex items-center gap-2 px-3 py-2 text-xs text-rpmx-steel animate-fade-in">
      <span className="flex gap-1">
        <span className="h-1.5 w-1.5 rounded-full bg-rpmx-signal animate-pulse3" />
        <span className="h-1.5 w-1.5 rounded-full bg-rpmx-signal animate-pulse3" style={{ animationDelay: '160ms' }} />
        <span className="h-1.5 w-1.5 rounded-full bg-rpmx-signal animate-pulse3" style={{ animationDelay: '320ms' }} />
      </span>
      <span className="italic">Agent is thinking...</span>
    </div>
  )
}

/* ── Financial Chat quick-action pills ── */
const QUICK_ACTIONS = [
  { label: 'P&L Report', message: 'Pull me a P&L for the Excavation division for January 2026' },
  { label: 'Job Costing', message: 'Break down job costs for Excavation in Q4 2025' },
  { label: 'Fuel Spend', message: 'How much did we spend on fuel across all divisions last year?' },
  { label: 'Quarter Comparison', message: 'Compare Q4 2025 to Q3 2025 company-wide' },
]

/* ── Financial Chat event renderers ── */
function UserMessageBubble({ text }) {
  return (
    <div className="flex justify-end animate-slide-in">
      <div className="max-w-[85%] rounded-2xl rounded-br-md bg-rpmx-signal/10 border border-rpmx-signal/20 px-4 py-2.5 text-sm text-rpmx-ink">
        {text}
      </div>
    </div>
  )
}

function AgentMessageBubble({ text, msgType }) {
  const isQuestion = msgType === 'clarification'
  return (
    <div className="flex justify-start animate-slide-in">
      <div className={`max-w-[85%] rounded-2xl rounded-bl-md px-4 py-2.5 text-sm ${
        isQuestion
          ? 'bg-amber-50 border border-amber-200 text-amber-900'
          : 'bg-white border border-rpmx-slate/50 text-rpmx-ink'
      }`}>
        {isQuestion && (
          <div className="flex items-center gap-1.5 mb-1.5 text-[10px] font-semibold uppercase tracking-wide text-amber-600">
            <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Clarification needed
          </div>
        )}
        <p className="whitespace-pre-wrap leading-relaxed">{text}</p>
      </div>
    </div>
  )
}

function CodeBlockBubble({ language, code }) {
  return (
    <div className="animate-slide-in">
      <div className="rounded-xl overflow-hidden border border-rpmx-slate/50">
        <div className="flex items-center gap-2 bg-[#1e1e2e] px-3 py-1.5">
          <span className="h-2 w-2 rounded-full bg-emerald-400" />
          <span className="text-[10px] font-mono text-emerald-400 uppercase tracking-wider">{language}</span>
        </div>
        <pre className="bg-[#1e1e2e] px-4 py-3 text-xs font-mono text-emerald-300 overflow-x-auto leading-relaxed whitespace-pre-wrap">{code}</pre>
      </div>
    </div>
  )
}

/* ── Invoice progress tracker (PO Match only) ── */
function InvoiceTracker({ activity, running, invoiceCount }) {
  const invoiceStates = useMemo(() => {
    // Dynamically detect invoices from activity stream instead of hardcoding
    const seen = []
    const states = {}

    let currentInvoice = null
    for (const ev of activity) {
      if (ev.type === 'reasoning') {
        const match = ev.payload?.text?.match(/Processing\s+(INV-[A-Z0-9-]+)/i)
        if (match) {
          currentInvoice = match[1]
          if (!states[currentInvoice]) {
            seen.push(currentInvoice)
            states[currentInvoice] = 'pending'
          }
        }
      }
      if (ev.type === 'tool_result' && ev.payload?.tool === 'complete_invoice') {
        const status = ev.payload?.result?.status
        if (currentInvoice && states[currentInvoice] !== undefined) {
          states[currentInvoice] = status === 'matched' ? 'matched' : 'exception'
        }
      }
    }
    if (running && currentInvoice && states[currentInvoice] === 'pending') {
      states[currentInvoice] = 'working'
    }

    return seen.map((inv) => ({ id: inv, status: states[inv] }))
  }, [activity, running])

  if (invoiceStates.length === 0) return null

  return (
    <div className="flex items-center gap-1 overflow-x-auto py-1.5">
      {invoiceStates.map((inv, idx) => (
        <div key={inv.id} className="flex items-center">
          {idx > 0 && <div className={`h-px w-3 ${inv.status === 'pending' ? 'bg-rpmx-slate/50' : 'bg-rpmx-slate'}`} />}
          <div className="flex flex-col items-center gap-0.5 px-1">
            <div className={`flex h-5 w-5 items-center justify-center rounded-full text-[8px] font-bold ${
              inv.status === 'matched' ? 'bg-emerald-100 text-emerald-700' :
              inv.status === 'exception' ? 'bg-amber-100 text-amber-700' :
              inv.status === 'working' ? 'bg-rpmx-signal/20 text-rpmx-signal ring-2 ring-rpmx-signal/40 animate-pulse' :
              'bg-rpmx-slate/30 text-rpmx-steel'
            }`}>
              {inv.status === 'matched' ? '\u2713' : inv.status === 'exception' ? '!' : inv.status === 'working' ? '\u25CF' : '\u25CB'}
            </div>
            <span className="text-[8px] text-rpmx-steel whitespace-nowrap">{inv.id.replace('INV-', '')}</span>
          </div>
        </div>
      ))}
    </div>
  )
}

/* ── Main component ── */
export default function AgentWorkspace() {
  const { agentId } = useParams()
  const navigate = useNavigate()
  const wsRef = useRef(null)
  const activityScrollRef = useRef(null)

  const [agent, setAgent] = useState(null)
  const [activity, setActivity] = useState([])
  const [reviewItems, setReviewItems] = useState([])
  const [expandedReviewId, setExpandedReviewId] = useState(null)
  const [communications, setCommunications] = useState([])
  const [skills, setSkills] = useState('')
  const [sessionId, setSessionId] = useState('')
  const [running, setRunning] = useState(false)
  const [currentInvoicePath, setCurrentInvoicePath] = useState('')
  const [activeInvoice, setActiveInvoice] = useState('')
  const [activeVendor, setActiveVendor] = useState('')
  const [activeAmount, setActiveAmount] = useState(null)
  const [latestOutput, setLatestOutput] = useState(null)
  const [tab, setTab] = useState('work')
  const [chatInput, setChatInput] = useState('')
  const [chatLog, setChatLog] = useState([])
  const [pendingSuggestion, setPendingSuggestion] = useState('')
  const [error, setError] = useState('')

  // Financial chat state
  const [conversationId, setConversationId] = useState(null)
  const [chatMessages, setChatMessages] = useState([]) // [{role, content, events?[]}]
  const [reports, setReports] = useState([])
  const chatScrollRef = useRef(null)
  const isFinancial = agentId === 'financial_reporting'

  // Agent chat state (Phase 3: chat about last run for all agents)
  const [agentConvoId, setAgentConvoId] = useState(null)
  const [agentChatMsgs, setAgentChatMsgs] = useState([])
  const [agentChatInput, setAgentChatInput] = useState('')
  const [agentChatLoading, setAgentChatLoading] = useState(false)
  const agentChatRef = useRef(null)

  async function loadAgent() {
    const data = await apiGet(`/api/agents/${agentId}`)
    setAgent(data)
    setSkills(data.skills || '')
    if (data.latest_output) setLatestOutput(data.latest_output)
  }

  async function loadReviewQueue() {
    const data = await apiGet(`/api/agents/${agentId}/review-queue`)
    setReviewItems(data)
  }

  async function loadComms() {
    const data = await apiGet('/api/communications')
    setCommunications(data.filter((entry) => entry.agent_id === agentId))
  }

  useEffect(() => {
    let mounted = true
    async function bootstrap() {
      try {
        await Promise.all([loadAgent(), loadReviewQueue(), loadComms()])
        if (mounted) setError('')
      } catch (err) {
        if (mounted) setError(err.message)
      }
    }
    bootstrap()
    // Reset chat/training state on agent change
    setAgentChatMsgs([]); setAgentConvoId(null); setAgentChatInput('')
    setChatLog([]); setPendingSuggestion(''); setTab('work')
    return () => {
      mounted = false
      if (wsRef.current) { wsRef.current.close(); wsRef.current = null }
    }
  }, [agentId])

  useEffect(() => {
    const node = activityScrollRef.current
    if (!node) return
    node.scrollTop = node.scrollHeight
  }, [activity])

  useEffect(() => {
    const node = chatScrollRef.current
    if (!node) return
    node.scrollTop = node.scrollHeight
  }, [chatMessages, activity])

  useEffect(() => {
    const node = agentChatRef.current
    if (!node) return
    node.scrollTop = node.scrollHeight
  }, [agentChatMsgs])

  useEffect(() => {
    if (!sessionId) return
    const socket = new WebSocket(wsUrl(`/ws/agent/${sessionId}`))
    wsRef.current = socket

    socket.onmessage = (evt) => {
      const event = JSON.parse(evt.data)
      setActivity((prev) => [...prev, event])

      if (event.type === 'reasoning') {
        const text = String(event.payload?.text || '')
        const invoiceMatch = text.match(/Processing\s+(INV-[A-Z0-9-]+)/i)
        if (invoiceMatch) setActiveInvoice(invoiceMatch[1])
      }

      if (event.type === 'tool_call' && event.payload?.tool === 'read_invoice') {
        setCurrentInvoicePath(event.payload.args?.file_path || '')
      }

      if (event.type === 'tool_result' && event.payload?.tool === 'read_invoice') {
        const result = event.payload?.result || {}
        if (result.vendor) setActiveVendor(result.vendor)
        if (result.total) setActiveAmount(result.total)
      }

      if (event.type === 'communication_sent') {
        setCommunications((prev) => [{
          id: `live-${Date.now()}`, agent_id: agentId,
          recipient: event.payload.recipient, subject: event.payload.subject,
          body: event.payload.body, created_at: event.timestamp,
        }, ...prev])
      }

      // Financial chat events
      if (event.type === 'agent_message') {
        setChatMessages((prev) => [...prev, {
          role: 'assistant',
          content: event.payload?.text || '',
          msgType: event.payload?.message_type || 'response',
        }])
      }

      if (event.type === 'report_generated') {
        setReports((prev) => [...prev, event.payload])
      }

      if (event.type === 'complete') {
        setRunning(false)
        setLatestOutput(event.payload?.output || null)
        void Promise.all([loadAgent(), loadReviewQueue()])
      }

      if (event.type === 'error') {
        setRunning(false)
      }
    }

    socket.onclose = () => { wsRef.current = null }
    return () => { socket.close() }
  }, [sessionId, agentId])

  async function runAgent() {
    setError('')
    setActivity([])
    setCommunications([])
    setActiveInvoice('')
    setActiveVendor('')
    setActiveAmount(null)
    try {
      setRunning(true)
      const data = await apiPost(`/api/agents/${agentId}/run`)
      setSessionId(data.session_id)
    } catch (err) {
      setRunning(false)
      setError(err.message)
    }
  }

  async function sendQuery(message) {
    if (!message.trim()) return
    setError('')
    // Add user message to chat
    setChatMessages((prev) => [...prev, { role: 'user', content: message.trim() }])
    // Clear activity for new query stream
    setActivity([])
    setChatInput('')
    try {
      setRunning(true)
      const data = await apiPost('/api/agents/financial_reporting/query', {
        message: message.trim(),
        conversation_id: conversationId,
      })
      setSessionId(data.session_id)
      if (data.conversation_id) setConversationId(data.conversation_id)
    } catch (err) {
      setRunning(false)
      setError(err.message)
    }
  }

  async function sendTraining(apply = false) {
    if (!chatInput.trim()) return
    const message = chatInput.trim()
    setChatLog((prev) => [...prev, { role: 'user', text: message }])
    setChatInput('')
    try {
      const response = await apiPost(`/api/agents/${agentId}/chat`, { message, apply })
      setChatLog((prev) => [...prev, { role: 'agent', text: response.response }])
      if (response.suggested_instruction) setPendingSuggestion(response.suggested_instruction)
      if (response.skills) { setSkills(response.skills) } else {
        const skillsData = await apiGet(`/api/agents/${agentId}/skills`)
        setSkills(skillsData.skills)
      }
    } catch (err) { setError(err.message) }
  }

  async function applySuggestion() {
    if (!pendingSuggestion) return
    try {
      const result = await apiPost(`/api/agents/${agentId}/chat`, { message: pendingSuggestion, apply: true })
      if (result.skills) setSkills(result.skills)
      setChatLog((prev) => [...prev, { role: 'agent', text: 'Training rule applied to skills.md.' }])
    } catch (err) { setError(err.message) }
  }

  async function sendAgentChat() {
    if (!agentChatInput.trim() || agentChatLoading) return
    const message = agentChatInput.trim()
    setAgentChatMsgs((prev) => [...prev, { role: 'user', content: message }])
    setAgentChatInput('')
    setAgentChatLoading(true)
    try {
      const data = await apiPost(`/api/agents/${agentId}/ask`, {
        message,
        conversation_id: agentConvoId,
      })
      setAgentChatMsgs((prev) => [...prev, { role: 'assistant', content: data.response }])
      if (data.conversation_id) setAgentConvoId(data.conversation_id)
    } catch (err) {
      setAgentChatMsgs((prev) => [...prev, { role: 'assistant', content: `Error: ${err.message}` }])
    } finally {
      setAgentChatLoading(false)
    }
  }

  async function actReviewItem(itemId, action) {
    try {
      await apiPost(`/api/review-queue/${itemId}/action`, { action })
      await loadReviewQueue()
    } catch (err) { setError(err.message) }
  }

  // Live-compute progress from activity stream so counter updates during processing
  const queueProgress = useMemo(() => {
    // After run completes, use final output
    if (!running && latestOutput?.queue_progress) return latestOutput.queue_progress
    // During PO Match processing, derive from activity events
    if (agentId === 'po_match' && activity.length > 0) {
      let matched = 0, exceptions = 0, totalSeen = 0
      for (const ev of activity) {
        if (ev.type === 'reasoning') {
          const m = ev.payload?.text?.match(/Processing\s+INV-[A-Z0-9-]+/i)
          if (m) totalSeen++
        }
        if (ev.type === 'tool_result' && ev.payload?.tool === 'complete_invoice') {
          const status = ev.payload?.result?.status
          if (status === 'matched') matched++
          else exceptions++
        }
      }
      let total = totalSeen
      for (const ev of activity) {
        if (ev.type === 'reasoning') {
          const countMatch = ev.payload?.text?.match(/\d+\s+of\s+(\d+)\)/i)
          if (countMatch) { total = parseInt(countMatch[1], 10); break }
        }
      }
      if (matched + exceptions > 0 || running) {
        return { matched, exceptions, total: total || totalSeen || 4 }
      }
    }
    // During AR Follow-Up processing, count complete_account events
    if (agentId === 'ar_followup' && activity.length > 0) {
      let completed = 0, emailsSent = 0, skippedCount = 0, total = 5
      for (const ev of activity) {
        if (ev.type === 'tool_result' && ev.payload?.tool === 'complete_account') completed++
        if (ev.type === 'communication') emailsSent++
        if (ev.type === 'tool_result' && ev.payload?.tool === 'determine_action') {
          const act = ev.payload?.result?.action || ''
          if (act === 'skip_retainage' || act === 'no_action_within_terms') skippedCount++
        }
        if (ev.type === 'reasoning') {
          const countMatch = ev.payload?.text?.match(/\d+\s+of\s+(\d+):/i)
          if (countMatch) total = parseInt(countMatch[1], 10)
        }
      }
      if (completed > 0 || running) {
        return { total, completed, emails_sent: emailsSent, skipped: skippedCount }
      }
    }
    return latestOutput?.queue_progress || null
  }, [activity, running, latestOutput, agentId])
  const recentActivity = useMemo(() => activity.slice(-80), [activity])
  const groupedActivity = useMemo(() => groupEvents(recentActivity), [recentActivity])
  const openReviewCount = reviewItems.filter((item) => item.status === 'open').length
  const displayStatus = running ? 'working' : (agent?.status || 'idle')

  return (
    <div className="flex h-screen flex-col bg-rpmx-canvas text-rpmx-ink overflow-hidden">
      {/* ── Compact header bar ── */}
      <div className="flex items-center justify-between gap-3 border-b border-rpmx-slate/50 bg-white px-4 py-2.5 sm:px-7">
        <div className="flex items-center gap-4">
          <button onClick={() => navigate('/')} className="text-sm text-rpmx-steel hover:text-rpmx-ink transition-colors">
            &larr; Back
          </button>
          <div className="h-5 w-px bg-rpmx-slate/60" />
          <h1 className="text-base font-semibold">{agent?.name || agentId}</h1>
          <div className="flex items-center gap-1.5">
            <span className={`relative flex h-2.5 w-2.5`}>
              <span className={`inline-flex h-full w-full rounded-full ${displayStatus === 'working' ? 'bg-rpmx-mint animate-ping opacity-75' : ''}`} />
              <span className={`absolute inline-flex h-full w-full rounded-full ${
                displayStatus === 'working' ? 'bg-rpmx-mint' :
                displayStatus === 'error' ? 'bg-rpmx-danger' :
                'bg-sky-400'
              }`} />
            </span>
            <span className={`text-xs font-medium ${displayStatus === 'working' ? 'text-rpmx-mint' : 'text-rpmx-steel'}`}>
              {displayStatus}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-3 text-xs text-rpmx-steel">
          {openReviewCount > 0 && (
            <span className="rounded-full bg-rpmx-amber/15 px-2 py-0.5 text-rpmx-amber font-semibold">
              {openReviewCount} review
            </span>
          )}
          <button
            onClick={() => apiPost('/api/demo/reset').then(() => { setActivity([]); setLatestOutput(null); setActiveInvoice(''); setActiveVendor(''); setActiveAmount(null); setCurrentInvoicePath(''); setExpandedReviewId(null); return Promise.all([loadAgent(), loadReviewQueue(), loadComms()]) })}
            className="rounded-lg border border-rpmx-slate bg-white px-2.5 py-1.5 hover:bg-rpmx-canvas transition-colors"
          >
            Reset
          </button>
          {!isFinancial && (
            <button
              onClick={runAgent}
              disabled={running}
              className="rounded-lg bg-rpmx-signal px-4 py-1.5 font-semibold text-white hover:brightness-95 disabled:cursor-not-allowed disabled:opacity-60 transition-all"
            >
              {running ? 'Running...' : 'Run Agent'}
            </button>
          )}
        </div>
      </div>

      {error && <div className="mx-4 mt-2 rounded-lg bg-red-50 px-4 py-2 text-xs text-red-700 sm:mx-7">{error}</div>}

      {/* ── Invoice progress tracker (PO Match) ── */}
      {agentId === 'po_match' && activity.length > 0 && (
        <div className="border-b border-rpmx-slate/30 bg-white px-4 sm:px-7">
          <InvoiceTracker activity={activity} running={running} />
        </div>
      )}

      {/* ── Main grid ── */}
      <div className="flex-1 grid gap-3 p-3 sm:p-4 lg:grid-cols-[38%_62%] overflow-hidden">
        {/* ── Left panel: Chat (financial) or Activity Stream (others) ── */}
        {isFinancial ? (
          <section className={`flex flex-col rounded-2xl bg-white shadow-sm overflow-hidden transition-all duration-700 ${
            running ? 'border-2 border-rpmx-signal/30 animate-glow-pulse' : 'border border-rpmx-slate/70'
          }`}>
            {/* Chat messages area */}
            <div ref={chatScrollRef} className="flex-1 space-y-3 overflow-auto p-4">
              {/* Welcome state */}
              {chatMessages.length === 0 && !running && (
                <div className="flex flex-col items-center justify-center py-8 animate-fade-in">
                  <div className="flex h-12 w-12 items-center justify-center rounded-full bg-gradient-to-br from-rpmx-signal/20 to-amber-100 mb-3">
                    <svg className="h-6 w-6 text-rpmx-signal" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
                    </svg>
                  </div>
                  <h3 className="text-sm font-semibold text-rpmx-ink">Financial Reporting Agent</h3>
                  <p className="mt-1 text-xs text-rpmx-steel text-center max-w-xs">
                    Ask me about P&L reports, job costing, expense analysis, or comparisons across divisions and periods.
                  </p>
                  <div className="mt-5 flex flex-wrap justify-center gap-2">
                    {QUICK_ACTIONS.map((qa) => (
                      <button
                        key={qa.label}
                        onClick={() => sendQuery(qa.message)}
                        className="rounded-full border border-rpmx-signal/30 bg-rpmx-signal/5 px-3.5 py-1.5 text-xs font-medium text-rpmx-signal hover:bg-rpmx-signal/10 hover:border-rpmx-signal/50 transition-all"
                      >
                        {qa.label}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Render chat messages interleaved with activity events */}
              {chatMessages.map((msg, msgIdx) => {
                if (msg.role === 'user') {
                  return (
                    <div key={`msg-${msgIdx}`} className="space-y-2">
                      <UserMessageBubble text={msg.content} />
                      {/* Render narrative events between this user message and the next chat message */}
                      {msgIdx === chatMessages.length - 1 || chatMessages[msgIdx + 1]?.role === 'user' ? (
                        <div className="space-y-1.5 pl-1">
                          {groupedActivity.map((item) => {
                            if (item.kind === 'tool_pair') return <ToolPairEvent key={item.key} call={item.call} result={item.result} />
                            const ev = item.event
                            if (ev.type === 'reasoning') return <ReasoningEvent key={item.key} event={ev} />
                            if (ev.type === 'tool_call') return <ToolCallEvent key={item.key} event={ev} />
                            if (ev.type === 'tool_result') return <ToolResultEvent key={item.key} event={ev} />
                            if (ev.type === 'code_block') return <CodeBlockBubble key={item.key} language={ev.payload?.language || 'sql'} code={ev.payload?.code || ''} />
                            if (ev.type === 'complete') return <CompleteEvent key={item.key} event={ev} agentId={agentId} />
                            if (ev.type === 'error') return <ErrorEvent key={item.key} event={ev} />
                            return null
                          })}
                          {running && <ThinkingIndicator />}
                        </div>
                      ) : null}
                    </div>
                  )
                }
                // Assistant messages
                return <AgentMessageBubble key={`msg-${msgIdx}`} text={msg.content} msgType={msg.msgType} />
              })}
            </div>

            {/* Chat input */}
            <div className="border-t border-rpmx-slate/40 bg-rpmx-canvas/50 px-3 py-3">
              {chatMessages.length > 0 && !running && (
                <div className="flex flex-wrap gap-1.5 mb-2">
                  {QUICK_ACTIONS.map((qa) => (
                    <button
                      key={qa.label}
                      onClick={() => sendQuery(qa.message)}
                      className="rounded-full border border-rpmx-slate/50 bg-white px-2.5 py-1 text-[10px] text-rpmx-steel hover:border-rpmx-signal/40 hover:text-rpmx-signal transition-all"
                    >
                      {qa.label}
                    </button>
                  ))}
                </div>
              )}
              <div className="flex gap-2">
                <input
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && !running && sendQuery(chatInput)}
                  placeholder="Ask about financials..."
                  disabled={running}
                  className="w-full rounded-xl border border-rpmx-slate bg-white px-4 py-2.5 text-sm focus:border-rpmx-signal focus:outline-none focus:ring-1 focus:ring-rpmx-signal/30 disabled:opacity-60"
                />
                <button
                  onClick={() => sendQuery(chatInput)}
                  disabled={running || !chatInput.trim()}
                  className="rounded-xl bg-rpmx-signal px-4 py-2.5 text-sm font-semibold text-white hover:brightness-95 disabled:cursor-not-allowed disabled:opacity-60 transition-all"
                >
                  {running ? (
                    <span className="flex items-center gap-1.5">
                      <span className="h-1.5 w-1.5 rounded-full bg-white animate-pulse" />
                      Working
                    </span>
                  ) : 'Ask'}
                </button>
              </div>
            </div>
          </section>
        ) : (
          <section className={`flex flex-col rounded-2xl bg-white shadow-sm overflow-hidden transition-all duration-700 ${
            running ? 'border-2 border-rpmx-signal/30 animate-glow-pulse' : 'border border-rpmx-slate/70'
          }`}>
            {queueProgress && (
              <div className="flex items-center justify-between border-b border-rpmx-slate/30 px-3 py-1.5 text-[10px] text-rpmx-steel">
                {agentId === 'ar_followup' ? (
                  <>
                    <span>Emails: {queueProgress.emails_sent ?? 0} | Skipped: {queueProgress.skipped ?? 0}</span>
                    <span className="font-mono">{queueProgress.completed ?? (queueProgress.actions_taken ?? 0) + (queueProgress.skipped ?? 0)} / {queueProgress.total}</span>
                  </>
                ) : (
                  <>
                    <span>Matched: {queueProgress.matched} | Exceptions: {queueProgress.exceptions}</span>
                    <span className="font-mono">{(queueProgress.matched ?? 0) + (queueProgress.exceptions ?? 0)} / {queueProgress.total}</span>
                  </>
                )}
              </div>
            )}

            <div ref={activityScrollRef} className="flex-1 space-y-1.5 overflow-auto p-3">
              {recentActivity.length === 0 && (
                <p className="py-8 text-center text-sm text-rpmx-steel">Run the agent to watch it work in real time.</p>
              )}
              {groupedActivity.map((item) => {
                if (item.kind === 'tool_pair') return <ToolPairEvent key={item.key} call={item.call} result={item.result} />
                const ev = item.event
                if (ev.type === 'reasoning') return <ReasoningEvent key={item.key} event={ev} />
                if (ev.type === 'tool_call') return <ToolCallEvent key={item.key} event={ev} />
                if (ev.type === 'tool_result') return <ToolResultEvent key={item.key} event={ev} />
                if (ev.type === 'status_change') return <StatusChangeEvent key={item.key} event={ev} />
                if (ev.type === 'communication_sent') return <CommunicationEvent key={item.key} event={ev} />
                if (ev.type === 'complete') return <CompleteEvent key={item.key} event={ev} agentId={agentId} />
                if (ev.type === 'error') return <ErrorEvent key={item.key} event={ev} />
                return null
              })}
              {running && <ThinkingIndicator />}
            </div>
          </section>
        )}

        {/* ── Work panel ── */}
        <section className="flex flex-col rounded-2xl border border-rpmx-slate/70 bg-white shadow-sm overflow-hidden">
          {/* Tabs */}
          <div className="flex border-b border-rpmx-slate/40">
            {(isFinancial ? FINANCIAL_TABS : TABS).map((name) => {
              const tabKey = name === 'history' ? 'review' : name
              return (
                <button
                  key={name}
                  onClick={() => setTab(tabKey)}
                  className={`px-4 py-2 text-xs font-semibold uppercase tracking-wider transition-colors ${
                    tab === tabKey
                      ? 'border-b-2 border-rpmx-signal text-rpmx-ink'
                      : 'text-rpmx-steel hover:text-rpmx-ink hover:bg-rpmx-canvas/50'
                  }`}
                >
                  {name}
                  {name === 'review' && openReviewCount > 0 && (
                    <span className="ml-1.5 inline-flex h-4 w-4 items-center justify-center rounded-full bg-rpmx-amber text-[9px] font-bold text-white">
                      {openReviewCount}
                    </span>
                  )}
                  {name === 'work' && isFinancial && reports.length > 0 && (
                    <span className="ml-1.5 inline-flex h-4 w-4 items-center justify-center rounded-full bg-rpmx-signal text-[9px] font-bold text-white">
                      {reports.length}
                    </span>
                  )}
                </button>
              )
            })}
          </div>

          <div className="flex-1 overflow-auto p-4">
            {tab === 'work' && (
              <ArtifactRenderer
                agentId={agentId}
                output={latestOutput || agent?.latest_output || {}}
                currentInvoicePath={currentInvoicePath}
                communications={communications}
                activeInvoice={activeInvoice}
                activeVendor={activeVendor}
                activeAmount={activeAmount}
                running={running}
                reports={reports}
              />
            )}

            {tab === 'review' && (
              isFinancial ? (
                <div className="space-y-2">
                  {reports.length === 0 && <p className="text-sm text-rpmx-steel">No reports generated yet. Ask a question to create your first report.</p>}
                  {reports.map((report, idx) => {
                    const REPORT_BADGE = {
                      p_and_l: { label: 'P&L', color: 'bg-emerald-100 text-emerald-700' },
                      comparison: { label: 'Comparison', color: 'bg-blue-100 text-blue-700' },
                      expense_analysis: { label: 'Expense', color: 'bg-amber-100 text-amber-700' },
                      job_costing: { label: 'Job Costing', color: 'bg-purple-100 text-purple-700' },
                      custom_query: { label: 'Custom', color: 'bg-indigo-100 text-indigo-700' },
                    }
                    const badge = REPORT_BADGE[report.report_type] || { label: report.report_type || 'Report', color: 'bg-gray-100 text-gray-700' }
                    return (
                      <article key={idx} className="rounded-xl border border-rpmx-slate/70 bg-rpmx-canvas p-3 animate-slide-in">
                        <div className="flex items-center justify-between">
                          <p className="text-sm font-semibold">{report.report_title || 'Financial Report'}</p>
                          <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${badge.color}`}>{badge.label}</span>
                        </div>
                        {report.narrative && <p className="mt-1.5 text-xs text-rpmx-steel line-clamp-2">{report.narrative}</p>}
                      </article>
                    )
                  })}
                </div>
              ) : (
                <div className="space-y-2">
                  {reviewItems.length === 0 && <p className="text-sm text-rpmx-steel">No review items.</p>}
                  {reviewItems.map((item) => {
                    const isExp = expandedReviewId === item.id
                    const ctx = item.context || {}
                    const inv = ctx.invoice || {}
                    const invData = ctx.invoice_data || {}
                    const selPo = ctx.selected_po
                    const dupes = ctx.duplicates || []
                    const proj = ctx.project
                    const steps = ctx.step_history || []
                    const vAmt = ctx.variance_amount
                    const vPct = ctx.variance_pct
                    const poMatches = ctx.po_matches || []
                    const hasCtx = !!ctx.invoice

                    const reasonBadge = (
                      <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                        item.reason_code === 'price_variance' ? 'bg-amber-100 text-amber-800' :
                        item.reason_code === 'duplicate_payment_risk' ? 'bg-red-100 text-red-800' :
                        'bg-blue-100 text-blue-800'
                      }`}>{item.reason_code?.replace(/_/g, ' ')}</span>
                    )

                    const actionBtns = item.status === 'open' && (
                      <div className="flex gap-1.5 text-xs" onClick={(e) => e.stopPropagation()}>
                        <button onClick={() => actReviewItem(item.id, 'approve')} className="rounded-lg bg-rpmx-mint px-3 py-1.5 font-semibold text-white hover:brightness-95">Approve</button>
                        <button onClick={() => actReviewItem(item.id, 'reject')} className="rounded-lg bg-rpmx-danger px-3 py-1.5 font-semibold text-white hover:brightness-95">Reject</button>
                        <button onClick={() => actReviewItem(item.id, 'escalate')} className="rounded-lg bg-rpmx-amber px-3 py-1.5 font-semibold text-white hover:brightness-95">Escalate</button>
                      </div>
                    )

                    const fmtDollars = (v) => Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

                    return (
                      <div key={item.id} className="rounded-xl border border-rpmx-slate/70 bg-rpmx-canvas overflow-hidden animate-slide-in">
                        {/* ── Collapsed header ── */}
                        <div
                          className="flex items-center justify-between p-3 cursor-pointer hover:bg-white/40 transition-colors"
                          onClick={() => setExpandedReviewId(isExp ? null : item.id)}
                        >
                          <div className="flex items-center gap-2 flex-1 min-w-0">
                            <p className="text-sm font-semibold truncate">{item.item_ref}</p>
                            {reasonBadge}
                            {item.status !== 'open' && (
                              <span className="rounded-full bg-rpmx-slate/20 px-2 py-0.5 text-[10px] font-semibold text-rpmx-steel">{item.action || item.status}</span>
                            )}
                          </div>
                          <div className="flex items-center gap-2">
                            {!isExp && actionBtns}
                            <svg
                              className={`h-4 w-4 text-rpmx-steel shrink-0 transition-transform duration-200 ${isExp ? 'rotate-180' : ''}`}
                              fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
                            >
                              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                            </svg>
                          </div>
                        </div>

                        {/* ── Details text (always visible) ── */}
                        {!isExp && <div className="px-3 pb-2.5 -mt-1"><p className="text-xs text-rpmx-steel">{item.details}</p></div>}

                        {/* ── Expanded detail panel ── */}
                        {isExp && (
                          <div className="border-t border-rpmx-slate/50 bg-white px-4 py-3 space-y-3.5 text-xs">
                            {/* Agent summary */}
                            <p className="text-sm text-rpmx-ink">{item.details}</p>

                            {hasCtx ? (
                              <>
                                {/* Invoice Details */}
                                <div>
                                  <p className="text-[10px] font-semibold uppercase tracking-wide text-rpmx-steel mb-1.5">Invoice Details</p>
                                  <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                                    <p><span className="text-rpmx-steel">Invoice:</span> <span className="font-medium">{inv.invoice_number}</span></p>
                                    <p><span className="text-rpmx-steel">Vendor:</span> <span className="font-medium">{invData.vendor || inv.vendor}</span></p>
                                    <p><span className="text-rpmx-steel">Amount:</span> <span className="font-medium">${fmtDollars(inv.amount)}</span></p>
                                    <p><span className="text-rpmx-steel">Date:</span> <span className="font-medium">{invData.invoice_date || 'N/A'}</span></p>
                                    {(invData.po_reference || inv.po_reference) && (
                                      <p><span className="text-rpmx-steel">PO Ref:</span> <span className="font-medium">{invData.po_reference || inv.po_reference}</span></p>
                                    )}
                                  </div>
                                </div>

                                {/* Matched PO */}
                                {selPo && (
                                  <div>
                                    <p className="text-[10px] font-semibold uppercase tracking-wide text-rpmx-steel mb-1.5">Matched Purchase Order</p>
                                    <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                                      <p><span className="text-rpmx-steel">PO:</span> <span className="font-medium">{selPo.po_number}</span></p>
                                      <p><span className="text-rpmx-steel">PO Amount:</span> <span className="font-medium">${fmtDollars(selPo.amount)}</span></p>
                                      <p><span className="text-rpmx-steel">Job:</span> <span className="font-medium">{selPo.job_id}</span></p>
                                      <p><span className="text-rpmx-steel">GL Code:</span> <span className="font-medium">{selPo.gl_code}</span></p>
                                      {selPo.confidence != null && (
                                        <p><span className="text-rpmx-steel">Match Confidence:</span> <span className="font-medium">{(selPo.confidence * 100).toFixed(0)}%</span></p>
                                      )}
                                    </div>
                                  </div>
                                )}

                                {/* Variance */}
                                {vAmt != null && (
                                  <div>
                                    <p className="text-[10px] font-semibold uppercase tracking-wide text-rpmx-steel mb-1.5">Variance</p>
                                    <div className="flex items-center gap-3">
                                      <span className={`text-sm font-semibold ${Math.abs(vAmt) > 500 ? 'text-rpmx-danger' : 'text-rpmx-ink'}`}>
                                        {vAmt >= 0 ? '+' : ''}${fmtDollars(vAmt)}
                                      </span>
                                      {vPct != null && (
                                        <span className={`font-semibold ${Math.abs(vPct) > 10 ? 'text-rpmx-danger' : 'text-rpmx-steel'}`}>
                                          ({vPct >= 0 ? '+' : ''}{vPct}%)
                                        </span>
                                      )}
                                    </div>
                                  </div>
                                )}

                                {/* No PO matches */}
                                {!selPo && poMatches.length === 0 && (
                                  <div>
                                    <p className="text-[10px] font-semibold uppercase tracking-wide text-rpmx-steel mb-1.5">PO Search</p>
                                    <p className="text-rpmx-danger font-medium">No matching purchase orders found</p>
                                  </div>
                                )}

                                {/* Other PO candidates */}
                                {poMatches.length > 1 && (
                                  <div>
                                    <p className="text-[10px] font-semibold uppercase tracking-wide text-rpmx-steel mb-1.5">Other PO Candidates</p>
                                    <div className="space-y-0.5">
                                      {poMatches.filter(po => po.po_number !== selPo?.po_number).map((po, i) => (
                                        <p key={i} className="text-rpmx-steel">
                                          {po.po_number} &mdash; ${fmtDollars(po.amount)} ({po.vendor}) &mdash; {(po.confidence * 100).toFixed(0)}% match
                                        </p>
                                      ))}
                                    </div>
                                  </div>
                                )}

                                {/* Duplicate risk */}
                                {dupes.length > 0 && (
                                  <div>
                                    <p className="text-[10px] font-semibold uppercase tracking-wide text-red-600 mb-1.5">Duplicate Payment Risk</p>
                                    {dupes.map((dup, i) => (
                                      <p key={i} className="text-red-700 font-medium">
                                        {dup.invoice_number || dup} {dup.status ? `(${dup.status})` : ''}
                                      </p>
                                    ))}
                                  </div>
                                )}

                                {/* Project */}
                                {proj && (
                                  <div>
                                    <p className="text-[10px] font-semibold uppercase tracking-wide text-rpmx-steel mb-1.5">Project</p>
                                    <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                                      <p><span className="text-rpmx-steel">Name:</span> <span className="font-medium">{proj.name}</span></p>
                                      <p><span className="text-rpmx-steel">ID:</span> <span className="font-medium">{proj.id}</span></p>
                                      {proj.pm_name && <p><span className="text-rpmx-steel">PM:</span> <span className="font-medium">{proj.pm_name}</span></p>}
                                      {proj.pm_email && <p><span className="text-rpmx-steel">Email:</span> <span className="font-medium">{proj.pm_email}</span></p>}
                                    </div>
                                  </div>
                                )}

                                {/* Agent reasoning / step history */}
                                {steps.length > 0 && (
                                  <div>
                                    <p className="text-[10px] font-semibold uppercase tracking-wide text-rpmx-steel mb-1.5">Agent Reasoning</p>
                                    <div className="space-y-0.5 max-h-36 overflow-auto">
                                      {steps.map((s, i) => (
                                        <p key={i} className="text-rpmx-steel">
                                          <span className="font-mono text-rpmx-ink font-medium">{s.step}.</span>{' '}
                                          <span className="font-medium text-rpmx-ink">{s.action?.replace(/_/g, ' ')}</span>{' '}
                                          &mdash; {s.reason}
                                        </p>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </>
                            ) : (
                              <p className="text-rpmx-steel italic">Detailed context not available for this item.</p>
                            )}

                            {/* Bottom action buttons */}
                            {item.status === 'open' && (
                              <div className="flex gap-2 pt-2 border-t border-rpmx-slate/30">
                                <button onClick={() => actReviewItem(item.id, 'approve')} className="rounded-lg bg-rpmx-mint px-4 py-2 font-semibold text-white hover:brightness-95">Approve</button>
                                <button onClick={() => actReviewItem(item.id, 'reject')} className="rounded-lg bg-rpmx-danger px-4 py-2 font-semibold text-white hover:brightness-95">Reject</button>
                                <button onClick={() => actReviewItem(item.id, 'escalate')} className="rounded-lg bg-rpmx-amber px-4 py-2 font-semibold text-white hover:brightness-95">Escalate</button>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              )
            )}

            {/* ── CHAT tab: conversation with agent about its work ── */}
            {tab === 'chat' && (
              <div className="flex h-full flex-col" style={{ minHeight: '50vh' }}>
                <div ref={agentChatRef} className="flex-1 space-y-3 overflow-auto p-1">
                  {agentChatMsgs.length === 0 && (
                    <div className="flex flex-col items-center justify-center py-10">
                      <div className="rounded-full bg-rpmx-signal/10 p-3 mb-3">
                        <svg className="h-6 w-6 text-rpmx-signal" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
                        </svg>
                      </div>
                      <h3 className="text-sm font-semibold text-rpmx-ink">Ask {agent?.name || 'Agent'}</h3>
                      <p className="mt-1 text-xs text-rpmx-steel text-center max-w-xs">
                        Ask questions about this agent&apos;s last run, decisions, and work output.
                      </p>
                      <div className="mt-4 flex flex-wrap justify-center gap-2">
                        {(CHAT_PROMPTS[agentId] || []).map((prompt) => (
                          <button
                            key={prompt}
                            onClick={() => { setAgentChatInput(prompt) }}
                            className="rounded-full border border-rpmx-signal/30 bg-rpmx-signal/5 px-3 py-1.5 text-xs text-rpmx-signal hover:bg-rpmx-signal/10 transition-colors"
                          >
                            {prompt}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                  {agentChatMsgs.map((msg, idx) => (
                    msg.role === 'user' ? (
                      <div key={idx} className="flex justify-end">
                        <div className="max-w-[80%] rounded-2xl rounded-tr-sm bg-rpmx-signal/10 border border-rpmx-signal/20 px-4 py-2.5 text-sm text-rpmx-ink">
                          {msg.content}
                        </div>
                      </div>
                    ) : (
                      <div key={idx} className="flex justify-start">
                        <div className="max-w-[85%] rounded-2xl rounded-tl-sm bg-white border border-rpmx-slate/50 px-4 py-2.5 text-sm text-rpmx-ink shadow-sm whitespace-pre-wrap">
                          {msg.content}
                        </div>
                      </div>
                    )
                  ))}
                  {agentChatLoading && <ThinkingIndicator />}
                </div>
                <div className="border-t border-rpmx-slate/40 px-1 pt-3 mt-2">
                  <div className="flex gap-2">
                    <input
                      value={agentChatInput}
                      onChange={(e) => setAgentChatInput(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && sendAgentChat()}
                      placeholder={`Ask ${agent?.name || 'agent'} about its work...`}
                      disabled={agentChatLoading}
                      className="w-full rounded-xl border border-rpmx-slate bg-white px-4 py-2.5 text-sm focus:border-rpmx-signal focus:outline-none focus:ring-1 focus:ring-rpmx-signal/30 disabled:opacity-60"
                    />
                    <button
                      onClick={sendAgentChat}
                      disabled={agentChatLoading || !agentChatInput.trim()}
                      className="rounded-xl bg-rpmx-signal px-4 py-2.5 text-sm font-semibold text-white hover:brightness-95 disabled:opacity-50 transition-all"
                    >
                      Ask
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* ── TRAINING tab: coach agent + edit skills ── */}
            {tab === 'training' && (
              <div className="flex flex-col" style={{ minHeight: '50vh' }}>
                <div className="grid gap-4 lg:grid-cols-2 flex-1">
                  {/* Left: Coaching chat */}
                  <div className="flex flex-col">
                    <h4 className="text-[10px] font-semibold uppercase tracking-wider text-rpmx-steel mb-2">Coach this Agent</h4>
                    <div className="flex-1 space-y-2 overflow-auto rounded-xl border border-rpmx-slate/70 bg-rpmx-canvas p-3 mb-2" style={{ maxHeight: '40vh' }}>
                      {chatLog.length === 0 && (
                        <div className="py-4 text-center">
                          <p className="text-xs text-rpmx-steel">Teach new behavior in plain language.</p>
                          <p className="mt-1 text-[10px] text-rpmx-steel/60">
                            Example: &quot;When you find a price variance over $1,000, send an email to the project manager.&quot;
                          </p>
                        </div>
                      )}
                      {chatLog.map((msg, idx) => (
                        <div key={idx} className={`rounded-lg px-3 py-2 text-sm ${msg.role === 'user' ? 'bg-white border border-rpmx-slate/30' : 'bg-[#fdf4ef] border border-orange-100'}`}>
                          <p className="text-[9px] font-semibold uppercase tracking-wider text-rpmx-steel">{msg.role === 'user' ? 'You' : 'Agent'}</p>
                          <p className="mt-0.5 text-xs">{msg.text}</p>
                        </div>
                      ))}
                    </div>
                    {pendingSuggestion && (
                      <div className="mb-2 rounded-xl border-2 border-rpmx-signal/40 bg-rpmx-signal/5 p-3">
                        <p className="text-[9px] font-semibold uppercase tracking-wider text-rpmx-signal">Pending Training Rule</p>
                        <p className="mt-1 text-xs text-rpmx-ink">{pendingSuggestion}</p>
                        <div className="mt-2 flex gap-2">
                          <button onClick={applySuggestion} className="rounded-lg bg-rpmx-signal px-3 py-1.5 text-xs font-semibold text-white hover:brightness-95 transition-all">Apply to Skills</button>
                          <button onClick={() => setPendingSuggestion('')} className="rounded-lg border border-rpmx-slate bg-white px-3 py-1.5 text-xs hover:bg-rpmx-canvas">Discard</button>
                        </div>
                      </div>
                    )}
                    <div className="flex gap-2">
                      <input
                        value={chatInput}
                        onChange={(e) => setChatInput(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && sendTraining(false)}
                        placeholder="Teach a new procedure..."
                        className="w-full rounded-xl border border-rpmx-slate bg-white px-4 py-2.5 text-sm focus:border-rpmx-signal focus:outline-none focus:ring-1 focus:ring-rpmx-signal/30"
                      />
                      <button onClick={() => sendTraining(false)} className="rounded-xl bg-rpmx-signal px-4 py-2.5 text-sm font-semibold text-white hover:brightness-95 transition-all">Send</button>
                    </div>
                  </div>
                  {/* Right: Skills editor */}
                  <div className="flex flex-col">
                    <div className="flex items-center justify-between mb-2">
                      <h4 className="text-[10px] font-semibold uppercase tracking-wider text-rpmx-steel">Skills File</h4>
                      <button
                        onClick={async () => {
                          const data = await apiPut(`/api/agents/${agentId}/skills`, { content: skills })
                          setSkills(data.skills)
                        }}
                        className="rounded-lg border border-rpmx-slate bg-white px-3 py-1 text-xs hover:bg-rpmx-canvas"
                      >
                        Save Skills
                      </button>
                    </div>
                    <textarea
                      value={skills}
                      onChange={(e) => setSkills(e.target.value)}
                      className="flex-1 min-h-[40vh] w-full rounded-xl border border-rpmx-slate bg-white p-3 font-mono text-[11px] leading-relaxed focus:border-rpmx-signal focus:outline-none resize-none"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* ── PROFILE tab: agent identity, tools, skills ── */}
            {tab === 'profile' && (
              <div className="space-y-4 overflow-auto" style={{ maxHeight: '70vh' }}>
                {/* Identity card */}
                <div className="rounded-xl border border-rpmx-slate/70 bg-gradient-to-r from-indigo-50/50 to-blue-50/50 p-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <h3 className="text-sm font-semibold text-rpmx-ink">{agent?.name}</h3>
                      <p className="mt-0.5 text-xs text-rpmx-steel">{agent?.department}</p>
                    </div>
                    <span className="rounded-full bg-indigo-100 px-2.5 py-1 text-[10px] font-semibold text-indigo-700">{agent?.workspace_type}</span>
                  </div>
                  <p className="mt-2 text-xs text-rpmx-ink/80">{agent?.agent_description || 'No description available.'}</p>
                </div>

                {/* Connected Tools */}
                <div>
                  <h4 className="text-[10px] font-semibold uppercase tracking-wider text-rpmx-steel mb-2">
                    Connected Tools ({agent?.tools?.length || 0})
                  </h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {(agent?.tools || []).map((tool) => (
                      <div key={tool} className="rounded-lg border border-rpmx-slate/50 bg-white px-3 py-2 hover:border-rpmx-signal/30 transition-colors">
                        <div className="flex items-center gap-2">
                          <svg className="h-3.5 w-3.5 text-rpmx-signal flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M11.42 15.17l-5.384 3.164A1 1 0 015 17.482V6.518a1 1 0 011.036-.852L11.42 8.83m0 6.34l5.964 3.508A1 1 0 0018.5 17.834V6.166a1 1 0 00-1.116-.852L11.42 8.83m0 6.34V8.83" />
                          </svg>
                          <span className="text-xs font-semibold text-rpmx-ink">{TOOL_LABELS[tool] || tool.replace(/_/g, ' ')}</span>
                        </div>
                        <p className="mt-0.5 text-[10px] text-rpmx-steel leading-snug">{TOOL_DESCRIPTIONS[tool] || ''}</p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Skills summary */}
                <div>
                  <h4 className="text-[10px] font-semibold uppercase tracking-wider text-rpmx-steel mb-2">Skills & Procedures</h4>
                  <div className="rounded-xl border border-rpmx-slate/70 bg-rpmx-canvas p-4 text-xs space-y-3">
                    {(skills || '').split(/\n##\s+/).map((section, idx) => {
                      if (idx === 0) {
                        const lines = section.split('\n')
                        const title = lines[0]?.replace(/^#\s*/, '') || 'Overview'
                        const body = lines.slice(1).join('\n').trim()
                        return (
                          <div key={idx}>
                            <h5 className="font-semibold text-rpmx-ink">{title}</h5>
                            {body && <p className="mt-1 text-rpmx-steel whitespace-pre-wrap leading-relaxed">{body}</p>}
                          </div>
                        )
                      }
                      const lines = section.split('\n')
                      const heading = lines[0]?.trim()
                      const body = lines.slice(1).join('\n').trim()
                      return (
                        <div key={idx} className="pt-2 border-t border-rpmx-slate/30">
                          <h5 className="font-semibold text-rpmx-ink">{heading}</h5>
                          {body && <p className="mt-1 text-rpmx-steel whitespace-pre-wrap leading-relaxed">{body}</p>}
                        </div>
                      )
                    })}
                  </div>
                </div>
              </div>
            )}

            {tab === 'comms' && (
              <div className="space-y-2">
                {isFinancial && (
                  <>
                    <div className="rounded-xl border border-rpmx-slate/70 bg-gradient-to-r from-indigo-50 to-blue-50 p-3 mb-3">
                      <h3 className="text-xs font-semibold uppercase tracking-wide text-indigo-700 flex items-center gap-2">
                        <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        Scheduled Reports
                      </h3>
                      <div className="mt-2 space-y-2">
                        <div className="flex items-center justify-between rounded-lg bg-white/80 border border-indigo-100 px-3 py-2 text-xs">
                          <div>
                            <p className="font-semibold text-rpmx-ink">Weekly P&L Summary</p>
                            <p className="text-rpmx-steel">All divisions, company-wide</p>
                          </div>
                          <span className="rounded-full bg-indigo-100 px-2 py-0.5 text-[10px] font-semibold text-indigo-700">Every Monday</span>
                        </div>
                        <div className="flex items-center justify-between rounded-lg bg-white/80 border border-indigo-100 px-3 py-2 text-xs">
                          <div>
                            <p className="font-semibold text-rpmx-ink">Monthly Division Comparison</p>
                            <p className="text-rpmx-steel">Division-by-division, month-over-month</p>
                          </div>
                          <span className="rounded-full bg-indigo-100 px-2 py-0.5 text-[10px] font-semibold text-indigo-700">1st of month</span>
                        </div>
                        <div className="flex items-center justify-between rounded-lg bg-white/80 border border-indigo-100 px-3 py-2 text-xs">
                          <div>
                            <p className="font-semibold text-rpmx-ink">Quarterly Board Report</p>
                            <p className="text-rpmx-steel">Executive summary with YoY comparison</p>
                          </div>
                          <span className="rounded-full bg-indigo-100 px-2 py-0.5 text-[10px] font-semibold text-indigo-700">Quarterly</span>
                        </div>
                      </div>
                    </div>
                    <h3 className="text-xs font-semibold uppercase tracking-wide text-rpmx-steel">Recent Deliveries</h3>
                  </>
                )}
                {communications.length === 0 && <p className="text-sm text-rpmx-steel">{isFinancial ? 'No report deliveries yet.' : 'No communications logged yet.'}</p>}
                {communications.map((entry) => (
                  <article key={entry.id} className="rounded-xl border border-rpmx-slate/70 bg-rpmx-canvas p-3">
                    <p className="text-[10px] font-semibold uppercase tracking-wide text-rpmx-steel">To: {entry.recipient}</p>
                    <h3 className="mt-1 text-sm font-semibold">{entry.subject}</h3>
                    <p className="mt-2 text-sm text-rpmx-ink">{entry.body}</p>
                  </article>
                ))}
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  )
}
