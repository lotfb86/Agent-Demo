import { Fragment, useEffect, useMemo, useState } from 'react'
import { assetUrl } from '../api'
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'

const CREW_COLORS = {
  crew_a: 'bg-emerald-500 border-emerald-600',
  crew_b: 'bg-blue-500 border-blue-600',
  crew_c: 'bg-amber-500 border-amber-600',
}

function renderJson(value) {
  return <pre className="whitespace-pre-wrap text-xs text-rpmx-ink">{JSON.stringify(value, null, 2)}</pre>
}

function compact(value) {
  if (typeof value === 'string') return value
  return JSON.stringify(value, null, 2)
}

function PoMatchArtifact({ output, currentInvoicePath, activeInvoice, activeVendor, activeAmount, running }) {
  const processed = output?.processed || []
  const matched = processed.filter((i) => i.status === 'matched').length
  const exceptions = processed.filter((i) => i.status !== 'matched').length
  const isDone = !running && processed.length > 0

  return (
    <div className="grid h-full gap-3 xl:grid-cols-[55%_45%]">
      <div className="flex flex-col overflow-hidden">
        {/* Invoice metadata header */}
        {(activeInvoice || currentInvoicePath) && (
          <div className={`mb-2 flex items-center justify-between rounded-lg px-3 py-2 text-xs transition-all duration-300 ${
            running ? 'ring-2 ring-rpmx-signal/25 bg-orange-50/60' : 'ring-1 ring-rpmx-slate/15 bg-rpmx-canvas'
          }`}>
            <div className="flex items-center gap-3">
              {activeInvoice && <span className="font-semibold text-rpmx-ink">{activeInvoice}</span>}
              {activeVendor && <span className="text-rpmx-steel">{activeVendor}</span>}
            </div>
            <div className="flex items-center gap-2">
              {activeAmount && <span className="font-mono font-semibold text-rpmx-ink">${Number(activeAmount).toLocaleString()}</span>}
              {running && (
                <span className="rounded-full bg-rpmx-signal/15 px-2 py-0.5 text-[10px] font-semibold text-rpmx-signal">
                  Processing
                </span>
              )}
            </div>
          </div>
        )}
        <div className={`flex-1 overflow-hidden rounded-xl border bg-white transition-all duration-500 ${
          running ? 'ring-2 ring-rpmx-signal/25 shadow-elevated' : 'ring-1 ring-rpmx-slate/15'
        }`}>
          {currentInvoicePath ? (
            <iframe title="Invoice PDF" src={assetUrl(currentInvoicePath)} className="h-full w-full" />
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-rpmx-steel">Run PO Match to load invoice PDF.</div>
          )}
        </div>
      </div>
      <div className="flex flex-col overflow-hidden rounded-xl ring-1 ring-rpmx-slate/15 bg-rpmx-canvas">
        {/* Completion summary */}
        {isDone && (
          <div className="border-b border-rpmx-slate/25 bg-gradient-to-r from-emerald-50 to-blue-50 px-3 py-2.5">
            <div className="flex items-center gap-2 text-xs">
              <svg className="h-4 w-4 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="font-semibold text-emerald-800">Processing Complete</span>
            </div>
            <div className="mt-1.5 flex gap-4 text-[11px] text-rpmx-steel">
              <span className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-emerald-400" />
                {matched} matched
              </span>
              <span className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-amber-400" />
                {exceptions} exception{exceptions !== 1 ? 's' : ''}
              </span>
              <span>{processed.length} total</span>
            </div>
          </div>
        )}
        <div className="flex-1 overflow-auto p-3">
          <h3 className="text-sm font-semibold">Invoice Decisions</h3>
          <div className="mt-2 space-y-2">
            {processed.map((item) => {
              const isMatched = item.status === 'matched'
              return (
                <article key={item.invoice_number} className={`rounded-lg border-l-[3px] ring-1 ring-rpmx-slate/15 bg-white p-2.5 text-xs animate-slide-in shadow-sm ${
                  isMatched ? 'border-l-emerald-400' : 'border-l-amber-400'
                }`}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {isMatched ? (
                        <svg className="h-3.5 w-3.5 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                      ) : (
                        <svg className="h-3.5 w-3.5 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                        </svg>
                      )}
                      <p className="font-semibold text-rpmx-ink">{item.invoice_number}</p>
                    </div>
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                      isMatched ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
                    }`}>
                      {item.status}
                    </span>
                  </div>
                  <p className="mt-1 text-rpmx-steel">{item.reason || item.match_method || 'matched'}</p>
                  {item.po_number && <p className="mt-0.5 text-rpmx-ink">PO: {item.po_number}</p>}
                  {item.gl_code && <p className="mt-0.5 text-rpmx-ink">GL: {item.gl_code}</p>}
                  {item.details && <p className="mt-1 text-rpmx-steel">{item.details}</p>}
                </article>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}

/* ── Financial Report chart colors (RPMX palette) ── */
const CHART_COLORS = ['#ff6f3c', '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899']

function fmtCurrency(v) {
  if (v == null) return '—'
  const n = Number(v)
  const sign = n < 0 ? '-' : ''
  const abs = Math.abs(n)
  if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(1)}M`
  if (abs >= 1_000) return `${sign}$${(abs / 1_000).toFixed(0)}K`
  return `${sign}$${abs.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
}
function fmtCurrencyFull(v) {
  if (v == null) return '—'
  const n = Number(v)
  const sign = n < 0 ? '-' : ''
  return `${sign}$${Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
}
function fmtPercent(v) { return v != null ? `${Number(v).toFixed(1)}%` : '—' }
function fmtNumber(v) { return v != null ? Number(v).toLocaleString() : '—' }
function fmtDays(v) { return v != null ? `${Number(v).toFixed(0)} days` : '—' }
function fmtValue(v, format) {
  if (format === 'currency') return fmtCurrency(v)
  if (format === 'percent') return fmtPercent(v)
  if (format === 'days') return fmtDays(v)
  return fmtNumber(v)
}
function fmtTableCell(v, format) {
  if (format === 'currency') return fmtCurrencyFull(v)
  if (format === 'percent') return fmtPercent(v)
  if (format === 'days') return fmtDays(v)
  if (format === 'text') return String(v ?? '')
  if (typeof v === 'number') return fmtCurrencyFull(v)
  return String(v ?? '')
}

/* "Lower is better" metrics — down arrow should be green, up arrow red */
const LOWER_IS_BETTER = new Set(['dso', 'overhead', 'overhead ratio', 'overhead_ratio', 'days sales outstanding', 'ar aging', 'cost', 'expenses'])

function isLowerBetter(label) {
  const l = (label || '').toLowerCase()
  for (const term of LOWER_IS_BETTER) { if (l.includes(term)) return true }
  return false
}

function KpiGrid({ metrics = [] }) {
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
      {metrics.map((m, i) => {
        const trend = m.trend === 'up' ? '↑' : m.trend === 'down' ? '↓' : ''
        const inverted = isLowerBetter(m.label)
        /* For "lower is better" metrics, swap the colors: down=green, up=red */
        let trendColor = 'text-rpmx-steel'
        if (m.trend === 'up') trendColor = inverted ? 'text-rose-600' : 'text-emerald-600'
        if (m.trend === 'down') trendColor = inverted ? 'text-emerald-600' : 'text-rose-600'
        return (
          <div key={i} className="rounded-lg bg-rpmx-canvas/60 p-2.5 ring-1 ring-rpmx-slate/10">
            <p className="text-[10px] font-medium uppercase tracking-wider text-rpmx-steel">{m.label}</p>
            <p className="mt-1 text-lg font-semibold text-rpmx-ink font-mono">
              {fmtValue(m.value, m.format)}
            </p>
            {(trend || m.target != null) && (
              <p className={`mt-0.5 text-[10px] ${trendColor}`}>
                {trend && <span className="font-semibold">{trend}</span>}
                {m.target != null && <span className="ml-1 text-rpmx-muted">target: {fmtValue(m.target, m.format)}</span>}
              </p>
            )}
          </div>
        )
      })}
    </div>
  )
}

function FinancialTable({ section }) {
  const { title, columns = [], rows = [], highlight_rows = [], footer } = section
  return (
    <div>
      {title && <p className="mb-2 text-xs font-semibold text-rpmx-ink">{title}</p>}
      <div className="overflow-x-auto rounded-lg ring-1 ring-rpmx-slate/10">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-rpmx-canvas/60">
              {columns.map((col, ci) => (
                <th key={ci} className={`py-2 px-3 font-semibold text-rpmx-steel uppercase tracking-wider text-[10px] ${ci === 0 ? 'text-left' : 'text-right'}`}>
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, ri) => {
              const isHighlight = highlight_rows.includes(ri)
              return (
                <tr key={ri} className={`border-t border-rpmx-slate/10 ${isHighlight ? 'bg-rpmx-canvas/50 font-semibold' : ''}`}>
                  {columns.map((col, ci) => {
                    const val = row[col.key]
                    const isNeg = typeof val === 'number' && val < 0
                    const isVariance = col.key?.includes('variance') || col.label?.toLowerCase()?.includes('variance')
                    const negColor = isNeg ? (isVariance ? 'text-rose-600' : 'text-rpmx-ink') : 'text-rpmx-ink'
                    return (
                      <td key={ci} className={`py-1.5 px-3 ${ci === 0 ? 'text-left text-rpmx-ink' : `text-right font-mono ${negColor}`}`}>
                        {fmtTableCell(val, col.format)}
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {footer && <p className="mt-1.5 text-[10px] text-rpmx-muted italic">{footer}</p>}
    </div>
  )
}

function FinancialChart({ section }) {
  const { chart_type, title, data = {}, format = 'currency' } = section
  const labels = data.labels || []
  const datasets = data.datasets || []

  const chartData = labels.map((label, i) => {
    const point = { name: label }
    datasets.forEach((ds) => { point[ds.label] = ds.values?.[i] ?? 0 })
    return point
  })

  const tooltipFmt = (v) => {
    if (format === 'currency') return fmtCurrency(v)
    if (format === 'percent') return fmtPercent(v)
    return fmtNumber(v)
  }

  const chartHeight = chart_type === 'pie' ? 'h-56' : 'h-56'

  return (
    <div>
      {title && <p className="mb-2 text-xs font-semibold text-rpmx-ink">{title}</p>}
      <div className={`${chartHeight} w-full`}>
        <ResponsiveContainer width="100%" height="100%">
          {chart_type === 'line' ? (
            <LineChart data={chartData} margin={{ top: 8, right: 16, bottom: 4, left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.15)" />
              <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#64748b' }} />
              <YAxis tick={{ fontSize: 10, fill: '#64748b' }} tickFormatter={tooltipFmt} width={65} />
              <Tooltip formatter={tooltipFmt} contentStyle={{ fontSize: 11, borderRadius: 8, border: '1px solid rgba(148,163,184,0.2)' }} />
              {datasets.length > 1 && <Legend wrapperStyle={{ fontSize: 10 }} />}
              {datasets.map((ds, di) => (
                <Line key={di} type="monotone" dataKey={ds.label} stroke={CHART_COLORS[di % CHART_COLORS.length]}
                  strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 5 }} />
              ))}
            </LineChart>
          ) : chart_type === 'pie' ? (
            <PieChart>
              <Pie data={chartData.map((d) => ({ name: d.name, value: d[datasets[0]?.label] || 0 }))}
                cx="50%" cy="50%" outerRadius={85} innerRadius={42}
                dataKey="value"
                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                labelLine={{ stroke: '#94a3b8', strokeWidth: 1 }}
                style={{ fontSize: 9 }}
              >
                {labels.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
              </Pie>
              <Tooltip formatter={tooltipFmt} contentStyle={{ fontSize: 11, borderRadius: 8, border: '1px solid rgba(148,163,184,0.2)' }} />
            </PieChart>
          ) : (
            /* bar or stacked_bar */
            <BarChart data={chartData} margin={{ top: 8, right: 16, bottom: 4, left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.15)" />
              <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#64748b' }} angle={labels.length > 6 ? -35 : 0} textAnchor={labels.length > 6 ? 'end' : 'middle'} height={labels.length > 6 ? 50 : 30} />
              <YAxis tick={{ fontSize: 10, fill: '#64748b' }} tickFormatter={tooltipFmt} width={65} />
              <Tooltip formatter={tooltipFmt} contentStyle={{ fontSize: 11, borderRadius: 8, border: '1px solid rgba(148,163,184,0.2)' }} />
              {datasets.length > 1 && <Legend wrapperStyle={{ fontSize: 10 }} />}
              {datasets.map((ds, di) => (
                <Bar key={di} dataKey={ds.label} fill={CHART_COLORS[di % CHART_COLORS.length]}
                  stackId={chart_type === 'stacked_bar' ? 'stack' : undefined}
                  radius={chart_type === 'stacked_bar' ? 0 : [3, 3, 0, 0]} />
              ))}
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  )
}

function NarrativeBlock({ section }) {
  return (
    <div className="rounded-lg bg-[#fffbf7] p-3 ring-1 ring-amber-200/40">
      {section.title && <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wide text-rpmx-steel">{section.title}</p>}
      <p className="text-xs text-rpmx-ink leading-relaxed whitespace-pre-wrap">{section.content}</p>
    </div>
  )
}

function ReportSection({ section }) {
  if (!section || !section.type) return null
  if (section.type === 'kpi_grid') return <KpiGrid metrics={section.metrics} />
  if (section.type === 'table') return <FinancialTable section={section} />
  if (section.type === 'chart') return <FinancialChart section={section} />
  if (section.type === 'narrative') return <NarrativeBlock section={section} />
  return null
}

/* ── Legacy flat key-value renderer for backward compat ── */
function LegacyDataTable({ data }) {
  return (
    <div className="p-4">
      <table className="w-full text-xs">
        <thead><tr className="border-b border-rpmx-slate/25">
          <th className="py-2 text-left font-semibold text-rpmx-steel uppercase tracking-wider">Line Item</th>
          <th className="py-2 text-right font-semibold text-rpmx-steel uppercase tracking-wider">Amount</th>
        </tr></thead>
        <tbody>
          {Object.entries(data).map(([key, value]) => {
            const isTotal = /total|net|gross|profit/i.test(key)
            const isPercent = /percent|margin_pct|rate/i.test(key)
            const amount = typeof value === 'number'
              ? isPercent ? `${value.toFixed(1)}%` : fmtCurrencyFull(value)
              : String(value)
            return (
              <tr key={key} className={`border-b border-rpmx-slate/20 ${isTotal ? 'bg-rpmx-canvas/50' : ''}`}>
                <td className={`py-2 ${isTotal ? 'font-semibold text-rpmx-ink' : 'text-rpmx-ink'}`}>
                  {key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                </td>
                <td className={`py-2 text-right font-mono ${isTotal ? 'font-semibold text-rpmx-ink' : 'text-rpmx-ink'}`}>{amount}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function FinancialReportArtifact({ output, reports }) {
  const [expandedIdx, setExpandedIdx] = useState(null)
  const allReports = reports || []

  // Auto-expand the latest report when it arrives
  useEffect(() => {
    if (allReports.length > 0) setExpandedIdx(allReports.length - 1)
  }, [allReports.length])

  const REPORT_BADGE = {
    p_and_l: { label: 'P&L', color: 'bg-emerald-100 text-emerald-700' },
    comparison: { label: 'Comparison', color: 'bg-blue-100 text-blue-700' },
    expense_analysis: { label: 'Expense', color: 'bg-amber-100 text-amber-700' },
    job_costing: { label: 'Job Costing', color: 'bg-purple-100 text-purple-700' },
    ar_analysis: { label: 'AR Aging', color: 'bg-rose-100 text-rose-700' },
    backlog: { label: 'Backlog', color: 'bg-cyan-100 text-cyan-700' },
    cash_flow: { label: 'Cash Flow', color: 'bg-teal-100 text-teal-700' },
    margin_analysis: { label: 'Margins', color: 'bg-orange-100 text-orange-700' },
    budget_variance: { label: 'Budget', color: 'bg-lime-100 text-lime-700' },
    kpi_dashboard: { label: 'Dashboard', color: 'bg-indigo-100 text-indigo-700' },
    custom_query: { label: 'Custom', color: 'bg-gray-100 text-gray-700' },
  }

  // ── Expanded report document ──
  if (expandedIdx !== null && allReports[expandedIdx]) {
    const report = allReports[expandedIdx]
    const badge = REPORT_BADGE[report.report_type] || { label: 'Report', color: 'bg-gray-100 text-gray-700' }
    const sections = report.sections || []
    const hasLegacyData = !sections.length && report.data && Object.keys(report.data).length > 0

    return (
      <div className="h-[62vh] overflow-auto activity-scroll">
        {/* Back button (only show if more than one report) */}
        {allReports.length > 1 && (
          <button
            onClick={() => setExpandedIdx(null)}
            className="mb-3 flex items-center gap-1.5 text-xs font-medium text-rpmx-signal hover:text-rpmx-ink transition-colors"
          >
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
            All reports ({allReports.length})
          </button>
        )}

        <div className="rounded-xl ring-1 ring-rpmx-slate/15 bg-white overflow-hidden">
          {/* Report header */}
          <div className="bg-gradient-to-r from-rpmx-canvas to-white border-b border-rpmx-slate/25 px-4 py-3">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-semibold text-rpmx-ink">{report.report_title || 'Financial Report'}</h3>
                {report.period_label && <p className="text-[10px] text-rpmx-steel mt-0.5">{report.division_name || 'Company-Wide'} — {report.period_label}</p>}
              </div>
              <span className={`rounded-full px-2.5 py-0.5 text-[10px] font-semibold ${badge.color}`}>{badge.label}</span>
            </div>
          </div>

          {/* Section-based content */}
          {sections.length > 0 ? (
            <div className="p-4 space-y-4">
              {sections.map((sec, si) => <ReportSection key={si} section={sec} />)}
            </div>
          ) : hasLegacyData ? (
            <LegacyDataTable data={report.data} />
          ) : null}

          {/* Standalone narrative (for old format) */}
          {report.narrative && !sections.length && (
            <div className="border-t border-rpmx-slate/25 bg-[#fffbf7] px-4 py-3">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-rpmx-steel mb-1.5">Executive Summary</p>
              <p className="text-sm text-rpmx-ink leading-relaxed whitespace-pre-wrap">{report.narrative}</p>
            </div>
          )}
        </div>
      </div>
    )
  }

  // ── Thumbnail gallery (collapsed view) ──
  return (
    <div className="h-[62vh] overflow-auto activity-scroll">
      {allReports.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-rpmx-canvas mb-3">
            <svg className="h-7 w-7 text-rpmx-steel" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
            </svg>
          </div>
          <p className="text-sm text-rpmx-steel">Ask a question in the chat to generate your first report.</p>
        </div>
      ) : (
        <div className="space-y-2">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-rpmx-steel mb-1">{allReports.length} report{allReports.length > 1 ? 's' : ''} generated</p>
          {allReports.map((report, idx) => {
            const badge = REPORT_BADGE[report.report_type] || { label: 'Report', color: 'bg-gray-100 text-gray-700' }
            const narrativeSec = (report.sections || []).find(s => s.type === 'narrative')
            const excerpt = narrativeSec?.content || report.narrative || ''
            return (
              <button
                key={idx}
                onClick={() => setExpandedIdx(idx)}
                className="w-full text-left rounded-xl ring-1 ring-rpmx-slate/15 bg-white p-3 hover:ring-rpmx-signal/30 hover:shadow-sm transition-all animate-slide-in group"
              >
                <div className="flex items-center justify-between">
                  <p className="text-sm font-semibold text-rpmx-ink group-hover:text-rpmx-signal transition-colors">{report.report_title || 'Financial Report'}</p>
                  <div className="flex items-center gap-2">
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${badge.color}`}>{badge.label}</span>
                    <svg className="h-3.5 w-3.5 text-rpmx-steel group-hover:text-rpmx-signal transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                    </svg>
                  </div>
                </div>
                {excerpt && <p className="mt-1 text-xs text-rpmx-steel line-clamp-2">{excerpt}</p>}
                {report.period_label && <p className="mt-0.5 text-[10px] text-rpmx-muted">{report.division_name || 'Company-Wide'} — {report.period_label}</p>}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}

function ScheduleMapArtifact({ output }) {
  const [dispatchData, setDispatchData] = useState(null)
  const CREW_LINE_COLORS = { crew_a: '#10b981', crew_b: '#3b82f6', crew_c: '#f59e0b' }
  const CREW_LABELS = { crew_a: 'Crew A', crew_b: 'Crew B', crew_c: 'Crew C' }

  useEffect(() => {
    let mounted = true
    async function load() {
      try {
        const response = await fetch(assetUrl('data/json/dispatch_jobs.json'))
        const json = await response.json()
        if (mounted) setDispatchData(json)
      } catch {
        if (mounted) setDispatchData(null)
      }
    }
    load()
    return () => { mounted = false }
  }, [])

  const { mapPins, routeLines, bounds } = useMemo(() => {
    if (!dispatchData || !output?.assignments) return { mapPins: [], routeLines: [], bounds: null }
    const jobs = dispatchData.jobs || []
    const yard = dispatchData.yard
    if (jobs.length === 0) return { mapPins: [], routeLines: [], bounds: null }

    // Include yard in bounds calculation
    const allPoints = yard ? [yard, ...jobs] : jobs
    const lats = allPoints.map((p) => p.lat)
    const lngs = allPoints.map((p) => p.lng)
    const minLat = Math.min(...lats) - 0.01
    const maxLat = Math.max(...lats) + 0.01
    const minLng = Math.min(...lngs) - 0.01
    const maxLng = Math.max(...lngs) + 0.01

    const toPos = (lat, lng) => ({
      left: ((lng - minLng) / (maxLng - minLng || 1)) * 100,
      top: (1 - (lat - minLat) / (maxLat - minLat || 1)) * 100,
    })

    const crewByJob = {}
    Object.entries(output.assignments || {}).forEach(([crewId, ids]) => {
      ;(ids || []).forEach((jobId) => { crewByJob[jobId] = crewId })
    })

    const jobMap = {}
    jobs.forEach((j) => { jobMap[j.id] = j })

    const pins = jobs.map((job) => ({ ...job, crewId: crewByJob[job.id] || 'unassigned', ...toPos(job.lat, job.lng) }))

    // Build route lines per crew (YARD → job1 → job2 → ... → YARD)
    const lines = []
    const yardPos = yard ? toPos(yard.lat, yard.lng) : null
    Object.entries(output.assignments || {}).forEach(([crewId, jobIds]) => {
      if (!jobIds || jobIds.length === 0 || !yardPos) return
      const color = CREW_LINE_COLORS[crewId] || '#94a3b8'
      const waypoints = [yardPos]
      for (const jid of jobIds) {
        const j = jobMap[jid]
        if (j) waypoints.push(toPos(j.lat, j.lng))
      }
      waypoints.push(yardPos)
      for (let i = 0; i < waypoints.length - 1; i++) {
        lines.push({ crewId, color, x1: waypoints[i].left, y1: waypoints[i].top, x2: waypoints[i + 1].left, y2: waypoints[i + 1].top })
      }
    })

    return { mapPins: pins, routeLines: lines, bounds: { minLat, maxLat, minLng, maxLng, yardPos } }
  }, [dispatchData, output])

  const saved = output?.unoptimized_drive_minutes && output?.optimized_drive_minutes
    ? output.unoptimized_drive_minutes - output.optimized_drive_minutes : null

  return (
    <div className="grid gap-3 xl:grid-cols-[62%_38%]">
      <div className="relative h-[62vh] overflow-hidden rounded-xl ring-1 ring-rpmx-slate/15 bg-gradient-to-br from-[#f5f7fb] via-[#edf6f3] to-[#fff6ed]">
        {/* Route lines SVG overlay */}
        <svg className="absolute inset-0 h-full w-full pointer-events-none" style={{ zIndex: 1 }}>
          {routeLines.map((line, i) => (
            <line key={i} x1={`${line.x1}%`} y1={`${line.y1}%`} x2={`${line.x2}%`} y2={`${line.y2}%`}
              stroke={line.color} strokeWidth="2" strokeOpacity="0.5" strokeDasharray="6 3" />
          ))}
        </svg>
        {/* Yard pin */}
        {bounds?.yardPos && (
          <div className="absolute -translate-x-1/2 -translate-y-1/2 rounded-lg border-2 border-rpmx-ink bg-white px-2 py-1 text-[10px] font-bold text-rpmx-ink shadow-sm"
            style={{ left: `${bounds.yardPos.left}%`, top: `${bounds.yardPos.top}%`, zIndex: 3 }} title="RPMX Dispatch Yard">
            🏗️ YARD
          </div>
        )}
        {/* Job pins */}
        {mapPins.map((pin) => (
          <div key={pin.id}
            className={`absolute -translate-x-1/2 -translate-y-1/2 rounded-full border-2 px-2 py-1 text-[10px] font-semibold text-white shadow-sm ${CREW_COLORS[pin.crewId] || 'bg-slate-500 border-slate-600'}`}
            style={{ left: `${pin.left}%`, top: `${pin.top}%`, zIndex: 2 }} title={`${pin.id} • ${pin.name}`}>
            {pin.id.replace('JOB-', '')}
          </div>
        ))}
        {/* Crew legend */}
        <div className="absolute top-2 right-2 flex flex-col gap-1 rounded-lg bg-white/95 px-2.5 py-2 shadow-sm ring-1 ring-rpmx-slate/10" style={{ zIndex: 4 }}>
          <span className="text-[10px] font-semibold text-rpmx-steel mb-0.5">CREWS</span>
          {Object.entries(CREW_LABELS).map(([id, label]) => (
            <div key={id} className="flex items-center gap-1.5">
              <span className={`h-2.5 w-2.5 rounded-full ${CREW_COLORS[id]?.split(' ')[0] || 'bg-slate-400'}`} />
              <span className="text-[10px] text-rpmx-ink">{label}</span>
            </div>
          ))}
        </div>
        <div className="absolute bottom-2 left-2 rounded bg-white/90 px-2 py-1 text-xs text-rpmx-steel">Raleigh-Durham Metro Area</div>
      </div>
      <div className="h-[62vh] flex flex-col overflow-hidden rounded-xl ring-1 ring-rpmx-slate/15 bg-rpmx-canvas">
        {/* Drive time savings banner */}
        <div className="border-b border-rpmx-slate/25 bg-gradient-to-r from-emerald-50 to-blue-50 px-3 py-2.5">
          <div className="flex items-center gap-2 text-xs">
            <svg className="h-4 w-4 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
            </svg>
            <span className="font-semibold text-emerald-800">Route Optimization</span>
          </div>
          <div className="mt-1.5 flex items-center gap-3 text-[11px]">
            <span className="text-rpmx-steel">Before: <b className="text-rpmx-ink">{output?.unoptimized_drive_minutes ?? '—'} min</b></span>
            <span className="text-rpmx-steel">→</span>
            <span className="text-rpmx-steel">After: <b className="text-emerald-700">{output?.optimized_drive_minutes ?? '—'} min</b></span>
            {saved > 0 && (
              <span className="rounded-full bg-emerald-100 px-2 py-0.5 font-semibold text-emerald-700">
                {saved} min saved ({output?.improvement_percent}%)
              </span>
            )}
          </div>
        </div>
        <div className="flex-1 overflow-auto p-3">
          <h3 className="text-sm font-semibold">Crew Routes</h3>
          <div className="mt-2 space-y-2">
            {Object.entries(output?.assignments || {}).map(([crewId, jobs]) => {
              const color = CREW_LINE_COLORS[crewId] || '#94a3b8'
              return (
                <article key={crewId} className="rounded-lg ring-1 ring-rpmx-slate/12 bg-white p-2.5 text-xs" style={{ borderLeftWidth: 3, borderLeftColor: color }}>
                  <div className="flex items-center justify-between">
                    <p className="font-semibold text-rpmx-ink">{CREW_LABELS[crewId] || crewId}</p>
                    <span className="text-[10px] text-rpmx-steel">{(jobs || []).length} stops</span>
                  </div>
                  <div className="mt-1.5 flex flex-wrap items-center gap-1 text-[11px]">
                    <span className="rounded bg-gray-100 px-1.5 py-0.5 font-medium text-rpmx-steel">YARD</span>
                    {(jobs || []).map((jobId, i) => (
                      <Fragment key={jobId}>
                        <span className="text-rpmx-steel">→</span>
                        <span className="rounded px-1.5 py-0.5 font-medium" style={{ backgroundColor: `${color}15`, color }}>{jobId}</span>
                      </Fragment>
                    ))}
                    <span className="text-rpmx-steel">→</span>
                    <span className="rounded bg-gray-100 px-1.5 py-0.5 font-medium text-rpmx-steel">YARD</span>
                  </div>
                </article>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}

function VendorComplianceArtifact({ output, communications }) {
  const findings = output?.findings || []
  const cs = output?.compliance_summary
  const ACTION_STYLES = {
    renewal_email: { label: 'Renewal Email', color: 'bg-blue-100 text-blue-700', border: 'border-l-blue-400', icon: '✉' },
    urgent_hold_task: { label: 'Urgent Hold', color: 'bg-red-100 text-red-700', border: 'border-l-red-400', icon: '⚠' },
    w9_email: { label: 'W-9 Request', color: 'bg-amber-100 text-amber-700', border: 'border-l-amber-400', icon: '📋' },
    contract_task: { label: 'Contract Task', color: 'bg-purple-100 text-purple-700', border: 'border-l-purple-400', icon: '📄' },
  }
  return (
    <div className="space-y-3">
      {/* ── Compliance Summary Bar ── */}
      {cs && (
        <div className="rounded-xl ring-1 ring-rpmx-slate/15 bg-white p-3">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold text-rpmx-ink">Vendor Compliance Overview</h3>
            <span className="text-xs text-rpmx-steel">{cs.total_vendors} vendors audited</span>
          </div>
          <div className="grid grid-cols-4 gap-2">
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-2 text-center">
              <p className="text-xl font-bold text-emerald-700">{cs.compliant}</p>
              <p className="text-[10px] text-rpmx-steel">Compliant</p>
            </div>
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-2 text-center">
              <p className="text-xl font-bold text-amber-700">{cs.expiring}</p>
              <p className="text-[10px] text-rpmx-steel">Expiring Soon</p>
            </div>
            <div className="rounded-lg border border-red-200 bg-red-50 p-2 text-center">
              <p className="text-xl font-bold text-red-700">{cs.non_compliant}</p>
              <p className="text-[10px] text-rpmx-steel">Non-Compliant</p>
            </div>
            <div className="rounded-lg ring-1 ring-rpmx-slate/10 bg-gray-50 p-2 text-center">
              <p className="text-xl font-bold text-rpmx-ink">{cs.issues_found}</p>
              <p className="text-[10px] text-rpmx-steel">Issues Found</p>
            </div>
          </div>
          {/* Compliance bar */}
          {cs.total_vendors > 0 && (
            <div className="mt-2 flex h-2 rounded-full overflow-hidden bg-gray-100">
              <div className="bg-emerald-500" style={{ width: `${(cs.compliant / cs.total_vendors * 100).toFixed(1)}%` }} />
              <div className="bg-amber-400" style={{ width: `${(cs.expiring / cs.total_vendors * 100).toFixed(1)}%` }} />
              <div className="bg-red-500" style={{ width: `${(cs.non_compliant / cs.total_vendors * 100).toFixed(1)}%` }} />
            </div>
          )}
        </div>
      )}

      <div className="grid gap-3 xl:grid-cols-[55%_45%]">
        <div className="flex flex-col overflow-hidden rounded-xl ring-1 ring-rpmx-slate/15 bg-rpmx-canvas">
          <div className="border-b border-rpmx-slate/25 bg-white px-3 py-2">
            <h3 className="text-sm font-semibold">Compliance Findings</h3>
            {findings.length > 0 && <p className="text-[10px] text-rpmx-steel mt-0.5">{findings.length} vendor issues identified</p>}
          </div>
          <div className="flex-1 overflow-auto p-3 space-y-2">
            {findings.map((item, idx) => {
              const style = ACTION_STYLES[item.action_type] || ACTION_STYLES.contract_task
              return (
                <article key={idx} className={`rounded-lg border-l-[3px] ring-1 ring-rpmx-slate/12 bg-white p-2.5 text-xs animate-slide-in ${style.border}`}>
                  <div className="flex items-center justify-between">
                    <p className="font-semibold text-rpmx-ink">{style.icon} {item.vendor}</p>
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${style.color}`}>{style.label}</span>
                  </div>
                  <p className="mt-1 font-medium text-rpmx-ink">{item.issue}</p>
                  <p className="mt-0.5 text-rpmx-steel">{item.reason}</p>
                  {item.task_title && <p className="mt-1 text-rpmx-ink">Task: {item.task_title}</p>}
                </article>
              )
            })}
          </div>
        </div>
        <div className="flex flex-col overflow-hidden rounded-xl ring-1 ring-rpmx-slate/15 bg-rpmx-canvas">
          <div className="border-b border-rpmx-slate/25 bg-white px-3 py-2">
            <h3 className="text-sm font-semibold">Communications & Tasks</h3>
          </div>
          <div className="flex-1 overflow-auto p-3 space-y-2">
            {(communications || []).length === 0 && <p className="text-sm text-rpmx-steel">No communications sent yet.</p>}
            {(communications || []).map((entry) => (
              <article key={entry.id} className="rounded-lg border-l-[3px] border-l-fuchsia-400 ring-1 ring-rpmx-slate/12 bg-white p-2.5 text-xs animate-slide-in">
                <p className="font-semibold text-fuchsia-800">{entry.subject}</p>
                <p className="text-rpmx-steel">To: {entry.recipient}</p>
                <p className="mt-1 text-rpmx-ink">{entry.body}</p>
              </article>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function fmtBudget(v) {
  if (v == null || isNaN(v)) return '$0'
  const n = Number(v)
  if (n >= 1000000) return '$' + (n / 1000000).toFixed(1) + 'M'
  if (n >= 1000) return '$' + (n / 1000).toFixed(0) + 'K'
  return '$' + n.toLocaleString()
}

/* ── Progress Tracking: Sub-Components ── */

function ProgressKpiBar({ kpi }) {
  const cards = [
    { label: 'Contract Value', value: fmtCurrency(kpi.total_contract_value), sub: `${kpi.total_projects} projects` },
    { label: 'Cost to Date', value: fmtCurrency(kpi.total_cost_to_date), sub: `of ${fmtCurrency(kpi.total_estimated_cost)} est.` },
    { label: 'Est. at Completion', value: fmtCurrency(kpi.total_eac), sub: `Margin ${fmtPercent(kpi.portfolio_margin_pct)}` },
    { label: 'Completion', value: fmtPercent(kpi.portfolio_pct_complete), sub: `${kpi.on_track_count ?? 0} on track · ${(kpi.at_risk_count ?? 0) + (kpi.behind_count ?? 0)} flagged`, flagged: ((kpi.at_risk_count ?? 0) + (kpi.behind_count ?? 0)) > 0 },
  ]
  return (
    <div className="grid grid-cols-2 gap-2 p-3 sm:grid-cols-4">
      {cards.map((c, i) => (
        <div key={i} className={`rounded-lg p-2.5 text-center ring-1 ${c.flagged ? 'ring-amber-200 bg-amber-50' : 'ring-rpmx-slate/15 bg-white'}`}>
          <p className="text-[10px] uppercase tracking-wide text-rpmx-steel">{c.label}</p>
          <p className={`text-lg font-bold ${c.flagged ? 'text-amber-700' : 'text-rpmx-ink'}`}>{c.value}</p>
          <p className="text-[9px] text-rpmx-steel mt-0.5">{c.sub}</p>
        </div>
      ))}
    </div>
  )
}

function CostCodeVarianceChart({ costCodes = [] }) {
  const data = costCodes
    .filter(cc => cc.pct_complete > 0)
    .map(cc => {
      const shortCode = cc.code.replace(/^\d+-/, '')
      return { name: shortCode, Budgeted: cc.earned_value, Actual: cc.actual }
    })
  if (!data.length) return null
  return (
    <div className="h-44 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.15)" />
          <XAxis dataKey="name" tick={{ fontSize: 8, fill: '#64748b' }} angle={-30} textAnchor="end" height={45} />
          <YAxis tick={{ fontSize: 9, fill: '#64748b' }} tickFormatter={fmtCurrency} width={50} />
          <Tooltip formatter={(v) => fmtCurrencyFull(v)} contentStyle={{ fontSize: 10, borderRadius: 6, border: '1px solid rgba(148,163,184,0.2)' }} />
          <Legend wrapperStyle={{ fontSize: 9 }} />
          <Bar dataKey="Budgeted" fill="#3b82f6" radius={[2, 2, 0, 0]} />
          <Bar dataKey="Actual" fill="#ff6f3c" radius={[2, 2, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

function LaborTrendChart({ monthlyLabor = [] }) {
  const data = monthlyLabor.map(m => ({
    name: m.month?.replace('2025-', '').replace('2026-', 'Jan '),
    Hours: m.hours,
    Crew: m.crew_size,
  }))
  if (!data.length) return null
  return (
    <div className="h-36 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.15)" />
          <XAxis dataKey="name" tick={{ fontSize: 9, fill: '#64748b' }} />
          <YAxis tick={{ fontSize: 9, fill: '#64748b' }} width={40} />
          <Tooltip contentStyle={{ fontSize: 10, borderRadius: 6, border: '1px solid rgba(148,163,184,0.2)' }} />
          <Legend wrapperStyle={{ fontSize: 9 }} />
          <Line type="monotone" dataKey="Hours" stroke="#3b82f6" strokeWidth={2} dot={{ r: 2.5 }} />
          <Line type="monotone" dataKey="Crew" stroke="#10b981" strokeWidth={2} dot={{ r: 2.5 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

function EarnedValueCard({ ev }) {
  if (!ev) return null
  const cpiColor = ev.cpi >= 1.0 ? 'text-emerald-600' : ev.cpi >= 0.9 ? 'text-amber-600' : 'text-red-600'
  const cpiBg = ev.cpi >= 1.0 ? 'bg-emerald-50 ring-emerald-200' : ev.cpi >= 0.9 ? 'bg-amber-50 ring-amber-200' : 'bg-red-50 ring-red-200'
  const marginColor = ev.projected_margin_pct >= 5 ? 'text-emerald-600' : ev.projected_margin_pct >= 0 ? 'text-amber-600' : 'text-red-600'
  return (
    <div className="grid grid-cols-3 gap-1.5">
      <div className={`rounded-lg p-2 text-center ring-1 ${cpiBg}`}>
        <p className="text-[9px] font-medium uppercase text-rpmx-steel">CPI</p>
        <p className={`text-base font-bold font-mono ${cpiColor}`}>{ev.cpi.toFixed(2)}</p>
        <p className="text-[8px] text-rpmx-steel">{ev.cpi >= 1.0 ? 'Under budget' : 'Over budget'}</p>
      </div>
      <div className="rounded-lg bg-white p-2 text-center ring-1 ring-rpmx-slate/12">
        <p className="text-[9px] font-medium uppercase text-rpmx-steel">EAC</p>
        <p className="text-base font-bold font-mono text-rpmx-ink">{fmtCurrency(ev.eac)}</p>
        <p className="text-[8px] text-rpmx-steel">Est. at completion</p>
      </div>
      <div className="rounded-lg bg-white p-2 text-center ring-1 ring-rpmx-slate/12">
        <p className="text-[9px] font-medium uppercase text-rpmx-steel">Proj. Margin</p>
        <p className={`text-base font-bold font-mono ${marginColor}`}>{fmtPercent(ev.projected_margin_pct)}</p>
        <p className="text-[8px] text-rpmx-steel">{fmtCurrency(ev.projected_margin)}</p>
      </div>
    </div>
  )
}

function LaborMetricsCard({ labor }) {
  if (!labor) return null
  const piColor = labor.productivity_index >= 1.0 ? 'text-emerald-600' : labor.productivity_index >= 0.9 ? 'text-amber-600' : 'text-red-600'
  const otColor = labor.overtime_pct > 10 ? 'text-red-600' : labor.overtime_pct > 5 ? 'text-amber-600' : 'text-rpmx-ink'
  return (
    <div className="grid grid-cols-4 gap-1.5">
      <div className="rounded-lg bg-white p-2 text-center ring-1 ring-rpmx-slate/12">
        <p className="text-[8px] font-medium uppercase text-rpmx-steel">Productivity</p>
        <p className={`text-sm font-bold font-mono ${piColor}`}>{labor.productivity_index.toFixed(2)}</p>
      </div>
      <div className="rounded-lg bg-white p-2 text-center ring-1 ring-rpmx-slate/12">
        <p className="text-[8px] font-medium uppercase text-rpmx-steel">Hours</p>
        <p className="text-sm font-bold font-mono text-rpmx-ink">{(labor.actual_hours || 0).toLocaleString()}</p>
        <p className="text-[8px] text-rpmx-steel">of {(labor.estimated_hours || 0).toLocaleString()}</p>
      </div>
      <div className="rounded-lg bg-white p-2 text-center ring-1 ring-rpmx-slate/12">
        <p className="text-[8px] font-medium uppercase text-rpmx-steel">Rate Var.</p>
        <p className={`text-sm font-bold font-mono ${labor.rate_variance > 0 ? 'text-red-600' : 'text-emerald-600'}`}>
          {labor.rate_variance > 0 ? '+' : ''}{fmtCurrencyFull(labor.rate_impact_dollars)}
        </p>
      </div>
      <div className="rounded-lg bg-white p-2 text-center ring-1 ring-rpmx-slate/12">
        <p className="text-[8px] font-medium uppercase text-rpmx-steel">OT %</p>
        <p className={`text-sm font-bold font-mono ${otColor}`}>{fmtPercent(labor.overtime_pct)}</p>
      </div>
    </div>
  )
}

function MilestoneTimeline({ milestones = [] }) {
  return (
    <div className="space-y-1">
      {milestones.map((ms, i) => {
        const delta = ms.days_delta
        const deltaLabel = delta != null ? (delta > 0 ? `+${delta}d late` : delta < 0 ? `${Math.abs(delta)}d early` : 'On time') : null
        const deltaColor = delta != null ? (delta > 5 ? 'text-red-600' : delta > 0 ? 'text-amber-600' : 'text-emerald-600') : ''
        return (
          <div key={i} className="flex items-center gap-2 text-[10px]">
            <div className="flex items-center justify-center w-4">
              {ms.status === 'complete' ? (
                <svg className="h-3.5 w-3.5 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              ) : ms.status === 'in_progress' ? (
                <span className="h-3 w-3 rounded-full border-2 border-blue-400 bg-blue-100 flex items-center justify-center">
                  <span className="h-1.5 w-1.5 rounded-full bg-blue-500 animate-pulse" />
                </span>
              ) : (
                <span className="h-3 w-3 rounded-full border-2 border-gray-300" />
              )}
            </div>
            <div className="flex-1 flex items-center justify-between">
              <span className={ms.status === 'complete' ? 'text-rpmx-steel' : 'text-rpmx-ink font-medium'}>{ms.name}</span>
              <div className="flex items-center gap-2">
                <span className="text-rpmx-steel text-[9px]">{ms.planned}</span>
                {deltaLabel && <span className={`text-[9px] font-semibold ${deltaColor}`}>{deltaLabel}</span>}
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function AssumptionCheck({ assumptions = [] }) {
  const broken = assumptions.filter(a => a.status === 'broken')
  if (!broken.length) return <p className="text-[10px] text-emerald-600 font-medium">✓ All proposal assumptions holding</p>
  return (
    <div className="space-y-1">
      {broken.map((a, i) => (
        <div key={i} className="flex items-start gap-1.5 text-[10px]">
          <span className="text-red-500 mt-0.5 shrink-0">✗</span>
          <div>
            <span className="text-rpmx-ink font-medium">{a.assumption}</span>
            {a.reason && <span className="text-red-600 ml-1">— {a.reason}</span>}
          </div>
        </div>
      ))}
    </div>
  )
}

function ReasoningChainPanel({ chain = [], color = 'blue' }) {
  const [expanded, setExpanded] = useState(false)
  if (!chain || chain.length === 0) return null
  const preview = chain.slice(0, 3)
  const rest = chain.slice(3)
  const colorMap = {
    red: { bg: 'bg-red-50/70', ring: 'ring-red-200/50', icon: 'text-red-400', step: 'text-red-900', head: 'text-red-700', line: 'bg-red-300', dot: 'bg-red-400' },
    amber: { bg: 'bg-amber-50/70', ring: 'ring-amber-200/50', icon: 'text-amber-500', step: 'text-amber-900', head: 'text-amber-700', line: 'bg-amber-300', dot: 'bg-amber-400' },
    green: { bg: 'bg-emerald-50/70', ring: 'ring-emerald-200/50', icon: 'text-emerald-500', step: 'text-emerald-900', head: 'text-emerald-700', line: 'bg-emerald-300', dot: 'bg-emerald-400' },
  }
  const c = colorMap[color] || colorMap.green
  const displaySteps = expanded ? chain : preview
  return (
    <div className={`rounded-lg ${c.bg} ring-1 ${c.ring} p-3`}>
      <div className="flex items-center gap-2 mb-2">
        <svg className={`h-3.5 w-3.5 ${c.icon}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
        </svg>
        <p className={`text-[10px] font-bold uppercase tracking-wide ${c.head}`}>Agent Reasoning Chain</p>
        <span className="text-[9px] text-rpmx-steel ml-auto">{chain.length} steps</span>
      </div>
      <div className="relative pl-4">
        {/* Vertical line */}
        <div className={`absolute left-[5px] top-1 bottom-1 w-px ${c.line}`} />
        {displaySteps.map((step, idx) => (
          <div key={idx} className="relative flex items-start gap-2.5 pb-2 last:pb-0">
            <div className={`absolute left-[-13px] top-[5px] h-2 w-2 rounded-full ${c.dot} ring-2 ring-white`} />
            <div className="flex-1">
              <p className={`text-[10px] ${c.step} leading-relaxed`}>
                <span className="font-mono text-[9px] opacity-60 mr-1.5">{idx + 1}.</span>
                {step}
              </p>
            </div>
          </div>
        ))}
      </div>
      {rest.length > 0 && (
        <button
          onClick={() => setExpanded(!expanded)}
          className={`mt-2 text-[9px] font-semibold ${c.head} hover:underline`}
        >
          {expanded ? 'Show less' : `Show ${rest.length} more step${rest.length > 1 ? 's' : ''}...`}
        </button>
      )}
    </div>
  )
}

function ProgressTrackingArtifact({ output }) {
  const findings = output?.findings || []
  const kpi = output?.kpi_summary || {}
  const computedProjects = output?.computed_projects || []
  const [expandedId, setExpandedId] = useState(null)

  const STATUS_STYLES = {
    green: { dot: 'bg-emerald-500', row: 'hover:bg-emerald-50/40', badge: 'bg-emerald-100 text-emerald-700', border: 'border-l-emerald-400' },
    amber: { dot: 'bg-amber-500', row: 'hover:bg-amber-50/40', badge: 'bg-amber-100 text-amber-700', border: 'border-l-amber-400' },
    red: { dot: 'bg-red-500', row: 'hover:bg-red-50/40', badge: 'bg-red-100 text-red-700', border: 'border-l-red-400' },
  }

  // Merge LLM findings with computed project data
  const enriched = findings.map((f) => {
    const cp = computedProjects.find((p) => p.project_id === f.project_id) || {}
    return { ...f, ...cp, _finding_text: f }
  })

  return (
    <div className="h-[62vh] overflow-auto rounded-xl ring-1 ring-rpmx-slate/15 bg-rpmx-canvas">
      {/* Portfolio KPI Bar */}
      <ProgressKpiBar kpi={kpi} />

      {/* Project Cards */}
      <div className="mx-3 mb-3 space-y-2">
        {enriched.map((item) => {
          const color = item.status_color || (item.finding === 'on_track' ? 'green' : item.finding === 'at_risk' ? 'amber' : 'red')
          const styles = STATUS_STYLES[color] || STATUS_STYLES.green
          const isExpanded = expandedId === item.project_id
          const findingLabel = (item.finding || '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
          const f = item._finding_text || {}
          const ev = item.earned_value_analysis || {}
          const la = item.labor_analysis || {}

          return (
            <div key={item.project_id} className="rounded-lg ring-1 ring-rpmx-slate/15 bg-white overflow-hidden">
              {/* Project Header Row — always visible */}
              <div
                className={`flex items-center gap-3 px-3 py-2.5 cursor-pointer ${styles.row} ${isExpanded ? 'border-b border-rpmx-slate/10' : ''}`}
                onClick={() => setExpandedId(isExpanded ? null : item.project_id)}
              >
                <span className={`h-3 w-3 rounded-full shrink-0 ${styles.dot}`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-xs text-rpmx-ink truncate">{item.project_name}</span>
                    <span className={`rounded-full px-2 py-0.5 text-[9px] font-semibold shrink-0 ${styles.badge}`}>{findingLabel}</span>
                  </div>
                  <div className="flex gap-3 mt-0.5 text-[10px] text-rpmx-steel">
                    <span>{item.project_id}</span>
                    <span>PM: {item.project_manager}</span>
                    <span>{item.division}</span>
                  </div>
                </div>
                <div className="flex items-center gap-4 text-[10px] shrink-0">
                  <div className="text-center">
                    <p className="text-rpmx-steel">Contract</p>
                    <p className="font-bold text-rpmx-ink">{fmtCurrency(item.contract_value)}</p>
                  </div>
                  <div className="text-center">
                    <p className="text-rpmx-steel">Cost to Date</p>
                    <p className="font-bold text-rpmx-ink">{fmtCurrency(item.total_cost_to_date)}</p>
                  </div>
                  <div className="text-center">
                    <p className="text-rpmx-steel">Complete</p>
                    <p className="font-bold text-rpmx-ink">{item.percent_complete}%</p>
                  </div>
                  <div className="text-center">
                    <p className="text-rpmx-steel">CPI</p>
                    <p className={`font-bold font-mono ${ev.cpi >= 1.0 ? 'text-emerald-600' : ev.cpi >= 0.9 ? 'text-amber-600' : 'text-red-600'}`}>
                      {(ev.cpi || 0).toFixed(2)}
                    </p>
                  </div>
                  <svg className={`h-4 w-4 text-rpmx-steel transition-transform ${isExpanded ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                  </svg>
                </div>
              </div>

              {/* Expanded Detail Panel */}
              {isExpanded && (
                <div className="bg-rpmx-canvas/40 px-3 py-3 space-y-3">
                  {/* Row 0: Reasoning Chain — WHY the agent thinks this */}
                  <ReasoningChainPanel chain={f.reasoning_chain} color={color} />

                  {/* Row 1: Agent Analysis + Earned Value */}
                  <div className="grid gap-3 md:grid-cols-2">
                    {/* Agent Root Cause Analysis */}
                    <div className={`rounded-lg border-l-[3px] ${styles.border} p-3 ${color === 'red' ? 'bg-red-50/60' : color === 'amber' ? 'bg-amber-50/60' : 'bg-emerald-50/60'}`}>
                      <p className="text-[10px] font-bold uppercase text-rpmx-steel mb-1">Executive Summary</p>
                      <p className="text-[11px] text-rpmx-ink leading-relaxed font-medium">{f.executive_summary}</p>
                      <p className="text-[10px] text-rpmx-ink leading-relaxed mt-2">{f.root_cause_analysis}</p>
                      {f.recommendation && (
                        <div className="mt-2 pt-2 border-t border-current/10">
                          <p className="text-[10px] font-semibold text-rpmx-ink">→ {f.recommendation}</p>
                        </div>
                      )}
                      {/* Risk level badges */}
                      <div className="flex gap-2 mt-2">
                        {f.financial_risk_level && (
                          <span className={`rounded-full px-2 py-0.5 text-[8px] font-semibold ${
                            f.financial_risk_level === 'high' ? 'bg-red-100 text-red-700' :
                            f.financial_risk_level === 'medium' ? 'bg-amber-100 text-amber-700' :
                            'bg-emerald-100 text-emerald-700'
                          }`}>Financial: {f.financial_risk_level}</span>
                        )}
                        {f.schedule_risk_level && (
                          <span className={`rounded-full px-2 py-0.5 text-[8px] font-semibold ${
                            f.schedule_risk_level === 'high' ? 'bg-red-100 text-red-700' :
                            f.schedule_risk_level === 'medium' ? 'bg-amber-100 text-amber-700' :
                            'bg-emerald-100 text-emerald-700'
                          }`}>Schedule: {f.schedule_risk_level}</span>
                        )}
                      </div>
                    </div>
                    {/* Earned Value + Margin */}
                    <div className="space-y-2">
                      <p className="text-[10px] font-bold uppercase text-rpmx-steel">Earned Value Analysis</p>
                      <EarnedValueCard ev={ev} />
                      <div className="grid grid-cols-2 gap-1.5 text-[10px]">
                        <div className="rounded-lg bg-white p-2 ring-1 ring-rpmx-slate/12">
                          <span className="text-rpmx-steel">Est. to Complete:</span>
                          <span className="ml-1 font-bold font-mono text-rpmx-ink">{fmtCurrency(ev.etc)}</span>
                        </div>
                        <div className="rounded-lg bg-white p-2 ring-1 ring-rpmx-slate/12">
                          <span className="text-rpmx-steel">Target Margin:</span>
                          <span className="ml-1 font-bold font-mono text-rpmx-ink">{fmtPercent(item.target_margin_pct)}</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Row 2: Cost Code Variance + Labor */}
                  <div className="grid gap-3 md:grid-cols-2">
                    <div className="rounded-lg ring-1 ring-rpmx-slate/12 bg-white p-2.5">
                      <p className="text-[10px] font-bold uppercase text-rpmx-steel mb-1.5">Cost Code: Budgeted vs Actual</p>
                      <CostCodeVarianceChart costCodes={item.cost_code_analysis} />
                    </div>
                    <div className="rounded-lg ring-1 ring-rpmx-slate/12 bg-white p-2.5">
                      <p className="text-[10px] font-bold uppercase text-rpmx-steel mb-1.5">Labor Trend</p>
                      <LaborTrendChart monthlyLabor={la.monthly_labor} />
                    </div>
                  </div>

                  {/* Row 3: Labor Metrics + Insights */}
                  <div>
                    <p className="text-[10px] font-bold uppercase text-rpmx-steel mb-1.5">Labor Performance</p>
                    <LaborMetricsCard labor={la} />
                    {(f.labor_insight || f.proposal_vs_actual_insight) && (
                      <div className="grid gap-2 mt-2 md:grid-cols-2">
                        {f.proposal_vs_actual_insight && (
                          <div className="rounded-lg bg-blue-50/60 p-2 text-[10px]">
                            <p className="font-semibold text-blue-700 mb-0.5">Proposal vs Actual</p>
                            <p className="text-blue-900">{f.proposal_vs_actual_insight}</p>
                          </div>
                        )}
                        {f.labor_insight && (
                          <div className="rounded-lg bg-purple-50/60 p-2 text-[10px]">
                            <p className="font-semibold text-purple-700 mb-0.5">Labor Analysis</p>
                            <p className="text-purple-900">{f.labor_insight}</p>
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Row 4: Milestones + Assumptions + Change Orders */}
                  <div className="grid gap-3 md:grid-cols-3">
                    <div className="rounded-lg ring-1 ring-rpmx-slate/12 bg-white p-2.5">
                      <p className="text-[10px] font-bold uppercase text-rpmx-steel mb-1.5">
                        Schedule ({item.schedule_analysis?.completed_milestones}/{item.schedule_analysis?.total_milestones} milestones)
                      </p>
                      {item.schedule_analysis?.days_behind > 0 && (
                        <p className="text-[10px] text-red-600 font-semibold mb-1">{item.schedule_analysis.days_behind} days behind schedule</p>
                      )}
                      {item.schedule_analysis?.days_ahead > 0 && (
                        <p className="text-[10px] text-emerald-600 font-semibold mb-1">{item.schedule_analysis.days_ahead} days ahead of schedule</p>
                      )}
                      <MilestoneTimeline milestones={item.schedule_analysis?.milestones} />
                      {f.schedule_insight && (
                        <p className="mt-2 text-[9px] text-rpmx-steel italic border-t border-rpmx-slate/10 pt-1">{f.schedule_insight}</p>
                      )}
                    </div>

                    <div className="rounded-lg ring-1 ring-rpmx-slate/12 bg-white p-2.5">
                      <p className="text-[10px] font-bold uppercase text-rpmx-steel mb-1.5">Proposal Assumptions</p>
                      <AssumptionCheck assumptions={item.broken_assumptions} />
                    </div>

                    <div className="rounded-lg ring-1 ring-rpmx-slate/12 bg-white p-2.5">
                      <p className="text-[10px] font-bold uppercase text-rpmx-steel mb-1.5">
                        Change Orders ({item.change_order_summary?.total_count || 0})
                      </p>
                      {(item.change_order_summary?.items || []).map((co, i) => (
                        <div key={i} className="flex items-center justify-between text-[10px] py-0.5 border-b border-rpmx-slate/5 last:border-0">
                          <div className="flex-1 min-w-0">
                            <span className="text-rpmx-ink font-medium">{co.co_number}</span>
                            <span className="text-rpmx-steel ml-1 text-[9px]">{co.description}</span>
                          </div>
                          <div className="flex items-center gap-1.5 shrink-0 ml-2">
                            <span className="font-mono font-medium">{fmtCurrency(co.amount)}</span>
                            <span className={`rounded-full px-1.5 py-0 text-[8px] font-semibold ${co.status === 'approved' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                              {co.status}
                            </span>
                            {co.impact_days > 0 && <span className="text-[8px] text-rpmx-steel">+{co.impact_days}d</span>}
                          </div>
                        </div>
                      ))}
                      {item.change_order_summary?.approved_value > 0 && (
                        <p className="mt-1 text-[9px] text-rpmx-steel">
                          Approved: {fmtCurrency(item.change_order_summary.approved_value)}
                          {item.change_order_summary.pending_value > 0 && ` · Pending: ${fmtCurrency(item.change_order_summary.pending_value)}`}
                        </p>
                      )}
                    </div>
                  </div>

                  {/* Risk Flags */}
                  {item.risk_flags?.length > 0 && (
                    <div className="rounded-lg bg-red-50/50 ring-1 ring-red-200/40 p-2.5">
                      <p className="text-[10px] font-bold uppercase text-red-700 mb-1">Risk Flags ({item.risk_flags.length})</p>
                      <div className="grid gap-1 md:grid-cols-2">
                        {item.risk_flags.map((rf, i) => (
                          <div key={i} className="flex items-start gap-1.5 text-[10px]">
                            <span className="text-red-400 shrink-0 mt-0.5">⚠</span>
                            <span className="text-red-900">{rf}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function MaintenanceArtifact({ output }) {
  const issues = output?.issues || []
  const fs = output?.fleet_summary
  const SEVERITY_STYLES = {
    critical: { color: 'bg-red-100 text-red-700', border: 'border-l-red-400', icon: '🔴' },
    high: { color: 'bg-orange-100 text-orange-700', border: 'border-l-orange-400', icon: '🟠' },
    medium: { color: 'bg-amber-100 text-amber-700', border: 'border-l-amber-400', icon: '🟡' },
    low: { color: 'bg-emerald-100 text-emerald-700', border: 'border-l-emerald-400', icon: '🟢' },
  }
  return (
    <div className="space-y-3">
      {/* ── Fleet Summary Bar ── */}
      {fs && (
        <div className="rounded-xl ring-1 ring-rpmx-slate/15 bg-white p-3">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold text-rpmx-ink">Fleet Status Overview</h3>
            <span className="text-xs text-rpmx-steel">{fs.total_units} units scanned</span>
          </div>
          <div className="grid grid-cols-5 gap-2">
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-2 text-center">
              <p className="text-xl font-bold text-emerald-700">{fs.all_clear}</p>
              <p className="text-[10px] text-rpmx-steel">All Clear</p>
            </div>
            <div className="rounded-lg border border-red-200 bg-red-50 p-2 text-center">
              <p className="text-xl font-bold text-red-700">{fs.severity_counts?.critical || 0}</p>
              <p className="text-[10px] text-rpmx-steel">Critical</p>
            </div>
            <div className="rounded-lg border border-orange-200 bg-orange-50 p-2 text-center">
              <p className="text-xl font-bold text-orange-700">{fs.severity_counts?.high || 0}</p>
              <p className="text-[10px] text-rpmx-steel">High</p>
            </div>
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-2 text-center">
              <p className="text-xl font-bold text-amber-700">{fs.severity_counts?.medium || 0}</p>
              <p className="text-[10px] text-rpmx-steel">Medium</p>
            </div>
            <div className="rounded-lg ring-1 ring-rpmx-slate/10 bg-gray-50 p-2 text-center">
              <p className="text-xl font-bold text-rpmx-ink">{fs.issues_found}</p>
              <p className="text-[10px] text-rpmx-steel">Issues</p>
            </div>
          </div>
        </div>
      )}

      <div className="flex flex-col overflow-hidden rounded-xl ring-1 ring-rpmx-slate/15 bg-rpmx-canvas">
        <div className="border-b border-rpmx-slate/25 bg-white px-3 py-2">
          <h3 className="text-sm font-semibold">Equipment Maintenance Report</h3>
          {issues.length > 0 && <p className="text-[10px] text-rpmx-steel mt-0.5">{issues.length} maintenance issues identified</p>}
        </div>
        <div className="flex-1 overflow-auto p-3 space-y-2">
          {issues.map((item, idx) => {
            const sev = item.severity?.toLowerCase() || 'medium'
            const style = SEVERITY_STYLES[sev] || SEVERITY_STYLES.medium
            return (
              <article key={idx} className={`rounded-lg border-l-[3px] ring-1 ring-rpmx-slate/12 bg-white p-2.5 text-xs animate-slide-in ${style.border}`}>
                <div className="flex items-center justify-between">
                  <p className="font-semibold text-rpmx-ink">{style.icon} {item.unit}</p>
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${style.color}`}>{sev}</span>
                </div>
                <p className="mt-1 font-medium text-rpmx-ink">{item.issue}</p>
                <p className="mt-0.5 text-rpmx-steel">{item.action}</p>
                {item.create_task && item.task_priority && (
                  <div className="mt-1.5 flex items-center gap-1.5 rounded bg-rpmx-canvas px-2 py-1">
                    <svg className="h-3 w-3 text-rpmx-steel" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <span className="text-rpmx-ink">Task created ({item.task_priority} priority)</span>
                  </div>
                )}
              </article>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function TrainingComplianceArtifact({ output }) {
  const issues = output?.issues || []
  const ts = output?.training_summary
  const TYPE_STYLES = {
    expired: { color: 'bg-red-100 text-red-700', border: 'border-l-red-400', label: 'Expired' },
    expiring_soon: { color: 'bg-amber-100 text-amber-700', border: 'border-l-amber-400', label: 'Expiring Soon' },
    expiring_osha: { color: 'bg-amber-100 text-amber-700', border: 'border-l-amber-400', label: 'Expired' },
    missing: { color: 'bg-purple-100 text-purple-700', border: 'border-l-purple-400', label: 'Missing' },
    missing_cert: { color: 'bg-purple-100 text-purple-700', border: 'border-l-purple-400', label: 'Missing Cert' },
    missing_orientation: { color: 'bg-orange-100 text-orange-700', border: 'border-l-orange-400', label: 'Missing Orientation' },
    incomplete: { color: 'bg-orange-100 text-orange-700', border: 'border-l-orange-400', label: 'Incomplete' },
  }
  return (
    <div className="space-y-3">
      {/* ── Training Compliance Summary Bar ── */}
      {ts && (
        <div className="rounded-xl ring-1 ring-rpmx-slate/15 bg-white p-3">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold text-rpmx-ink">Training Compliance Overview</h3>
            <span className="text-xs text-rpmx-steel">{ts.total_employees} employees audited</span>
          </div>
          <div className="grid grid-cols-4 gap-2">
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-2 text-center">
              <p className="text-xl font-bold text-emerald-700">{ts.compliant}</p>
              <p className="text-[10px] text-rpmx-steel">Compliant</p>
            </div>
            <div className="rounded-lg border border-red-200 bg-red-50 p-2 text-center">
              <p className="text-xl font-bold text-red-700">{ts.non_compliant}</p>
              <p className="text-[10px] text-rpmx-steel">Non-Compliant</p>
            </div>
            <div className="rounded-lg ring-1 ring-rpmx-slate/10 bg-gray-50 p-2 text-center">
              <p className="text-xl font-bold text-rpmx-ink">{ts.issues_found}</p>
              <p className="text-[10px] text-rpmx-steel">Issues Found</p>
            </div>
            <div className="rounded-lg border border-blue-200 bg-blue-50 p-2 text-center">
              <p className="text-xl font-bold text-blue-700">{ts.total_employees > 0 ? Math.round(ts.compliant / ts.total_employees * 100) : 0}%</p>
              <p className="text-[10px] text-rpmx-steel">Compliance Rate</p>
            </div>
          </div>
          {/* Compliance bar */}
          {ts.total_employees > 0 && (
            <div className="mt-2 flex h-2 rounded-full overflow-hidden bg-gray-100">
              <div className="bg-emerald-500" style={{ width: `${(ts.compliant / ts.total_employees * 100).toFixed(1)}%` }} />
              <div className="bg-red-500" style={{ width: `${(ts.non_compliant / ts.total_employees * 100).toFixed(1)}%` }} />
            </div>
          )}
        </div>
      )}

      <div className="flex flex-col overflow-hidden rounded-xl ring-1 ring-rpmx-slate/15 bg-rpmx-canvas">
        <div className="border-b border-rpmx-slate/25 bg-white px-3 py-2">
          <h3 className="text-sm font-semibold">Training Compliance Report</h3>
          {issues.length > 0 && <p className="text-[10px] text-rpmx-steel mt-0.5">{issues.length} compliance issues found</p>}
        </div>
        <div className="flex-1 overflow-auto p-3 space-y-2">
          {issues.map((item, idx) => {
            const typeKey = item.issue_type?.toLowerCase()?.replace(/\s+/g, '_') || 'expired'
            const style = TYPE_STYLES[typeKey] || TYPE_STYLES.expired
            return (
              <article key={idx} className={`rounded-lg border-l-[3px] ring-1 ring-rpmx-slate/12 bg-white p-2.5 text-xs animate-slide-in ${style.border}`}>
                <div className="flex items-center justify-between">
                  <p className="font-semibold text-rpmx-ink">{item.name}</p>
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${style.color}`}>{style.label}</span>
                </div>
                <p className="mt-1 text-rpmx-steel">{item.detail}</p>
                {item.create_task && (
                  <div className="mt-1.5 flex items-center gap-1.5 rounded bg-rpmx-canvas px-2 py-1">
                    <svg className="h-3 w-3 text-rpmx-steel" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                    </svg>
                    <span className="text-rpmx-ink">Task: {item.task_priority || 'normal'} priority</span>
                  </div>
                )}
              </article>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function ChecklistArtifact({ output }) {
  const hire = output?.hire || {}
  const checklist = output?.checklist || {}
  const summary = output?.onboarding_summary
  const sections = [
    { key: 'documents', label: 'Documents', icon: '📄', color: 'blue' },
    { key: 'training', label: 'Training', icon: '🎓', color: 'amber' },
    { key: 'equipment', label: 'Equipment', icon: '🦺', color: 'emerald' },
  ]
  const STATUS_ICON = { complete: '✅', completed: '✅', done: '✅', issued: '✅', in_progress: '🔄', 'in progress': '🔄', scheduled: '🔄', pending_review: '🔄', pending: '⬜', required: '⬜', not_started: '⬜' }
  const getIcon = (s) => STATUS_ICON[String(s || '').toLowerCase()] || '⬜'
  const allItems = [...(checklist.documents||[]),...(checklist.training||[]),...(checklist.equipment||[])]
  const totalItems = summary?.total_items || allItems.length
  const completedItems = summary?.completed || allItems.filter(i => ['complete','completed','done','issued'].includes(String(i.status||'').toLowerCase())).length
  const pct = totalItems > 0 ? Math.round((completedItems / totalItems) * 100) : 0
  return (
    <div className="space-y-3">
      {/* Progress Bar */}
      <div className="rounded-xl ring-1 ring-rpmx-slate/15 bg-white p-3">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-semibold text-rpmx-ink">Onboarding Progress</h3>
          <span className="text-xs font-semibold text-rpmx-steel">{completedItems}/{totalItems} items complete</span>
        </div>
        <div className="h-2.5 rounded-full bg-gray-100 overflow-hidden">
          <div className="h-full rounded-full bg-gradient-to-r from-emerald-400 to-emerald-500 transition-all" style={{ width: `${pct}%` }} />
        </div>
        <p className="text-[10px] text-rpmx-steel mt-1">{pct}% complete</p>
      </div>
      {/* Horizontal Profile Card */}
      <div className="rounded-xl ring-1 ring-rpmx-slate/15 bg-white p-3">
        <div className="flex items-center gap-4">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 text-white text-lg font-bold">
            {(hire.name || 'N')[0]}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-bold text-rpmx-ink">{hire.name || 'New Hire'}</p>
            <p className="text-xs text-rpmx-steel">{hire.role} • {hire.division}</p>
          </div>
          <div className="text-right shrink-0">
            <p className="text-[10px] text-rpmx-steel uppercase tracking-wide">Start Date</p>
            <p className="text-xs font-semibold text-rpmx-ink">{hire.start_date}</p>
          </div>
          <div className="text-right shrink-0">
            <p className="text-[10px] text-rpmx-steel uppercase tracking-wide">Manager</p>
            <p className="text-xs font-semibold text-rpmx-ink">{hire.hiring_manager}</p>
          </div>
        </div>
      </div>
      {/* Three-Column Checklist */}
      <div className="grid gap-3 md:grid-cols-3">
        {sections.map(({ key, label, icon, color }) => {
          const items = checklist[key] || []
          const sectionDone = items.filter(i => ['complete','completed','done','issued'].includes(String(i.status||'').toLowerCase())).length
          const borderColor = color === 'blue' ? 'border-t-blue-400' : color === 'amber' ? 'border-t-amber-400' : 'border-t-emerald-400'
          return (
            <div key={key} className={`rounded-xl ring-1 ring-rpmx-slate/15 ${borderColor} border-t-[3px] bg-white p-3`}>
              <div className="flex items-center justify-between mb-2">
                <p className="text-xs font-bold uppercase tracking-wide text-rpmx-steel">{icon} {label}</p>
                <span className="text-[10px] text-rpmx-steel">{sectionDone}/{items.length}</span>
              </div>
              <div className="space-y-1.5">
                {items.map((item, idx) => (
                  <div key={idx} className="flex items-center gap-2 text-xs">
                    <span className="text-sm leading-none">{getIcon(item.status)}</span>
                    <span className={`${['complete','completed','done','issued'].includes(String(item.status||'').toLowerCase()) ? 'text-rpmx-steel line-through' : 'text-rpmx-ink'}`}>
                      {item.name || item.item}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function fmtEstimateMoney(v) {
  if (v == null || isNaN(v)) return '$0'
  const n = Number(v)
  if (n >= 1000) return '$' + n.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })
  return '$' + n.toFixed(2)
}

function CostEstimateArtifact({ output }) {
  const project = output?.project || {}
  const lineItems = output?.line_items || []
  const categorySubtotals = output?.category_subtotals || {}
  const markups = output?.markups || {}
  const directCost = output?.direct_cost_total || 0
  const grandTotal = output?.grand_total || 0
  const assumptions = output?.assumptions || []
  const exclusions = output?.exclusions || []
  const proposal = output?.proposal || {}

  // Group line items by category
  const grouped = {}
  lineItems.forEach((li) => {
    const cat = li.category || 'Other'
    if (!grouped[cat]) grouped[cat] = []
    grouped[cat].push(li)
  })
  const categoryOrder = Object.keys(grouped)

  return (
    <div className="h-[62vh] overflow-auto rounded-xl ring-1 ring-rpmx-slate/15 bg-rpmx-canvas">
      {/* Proposal Header Banner */}
      <div className="bg-gradient-to-r from-blue-700 to-blue-900 px-4 py-3 text-white">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-blue-200">Construction Cost Proposal</p>
        <h3 className="text-base font-bold mt-0.5">{project.name || 'Cost Estimate'}</h3>
        <div className="flex items-center gap-4 mt-1.5 text-[11px] text-blue-100">
          <span>{project.client || 'N/A'}</span>
          <span className="text-blue-300">|</span>
          <span>{project.location || ''}</span>
          <span className="text-blue-300">|</span>
          <span>{project.project_id || ''}</span>
        </div>
        <div className="flex items-center gap-4 mt-1 text-[10px] text-blue-200">
          {project.estimator && <span>Estimator: {project.estimator}</span>}
          {project.bid_date && <><span className="text-blue-400">|</span><span>Bid Date: {project.bid_date}</span></>}
        </div>
      </div>

      {/* Scope Narrative */}
      {proposal.scope_narrative && (
        <div className="mx-3 mt-3 rounded-lg ring-1 ring-rpmx-slate/15 bg-white p-3">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-rpmx-steel mb-1.5">Scope of Work</p>
          <p className="text-xs text-rpmx-ink leading-relaxed whitespace-pre-line">{proposal.scope_narrative}</p>
        </div>
      )}

      {/* Scope Summary Bar */}
      <div className="mx-3 mt-3 flex items-center gap-3 rounded-lg bg-blue-50 border border-blue-200 px-3 py-2 text-[11px]">
        <span className="font-semibold text-blue-700">{lineItems.length} line items</span>
        <span className="text-blue-400">&bull;</span>
        <span className="text-blue-700">{categoryOrder.length} categories</span>
        <span className="text-blue-400">&bull;</span>
        <span className="font-semibold text-blue-800">Grand Total: {fmtEstimateMoney(grandTotal)}</span>
      </div>

      {/* Line Item Table */}
      <div className="mx-3 mt-3 rounded-lg ring-1 ring-rpmx-slate/15 bg-white overflow-hidden">
        <table className="w-full text-[11px]">
          <thead>
            <tr className="bg-gray-50 border-b border-rpmx-slate/25">
              <th className="text-left px-3 py-2 font-semibold text-rpmx-steel">Item</th>
              <th className="text-right px-2 py-2 font-semibold text-rpmx-steel w-16">Qty</th>
              <th className="text-center px-2 py-2 font-semibold text-rpmx-steel w-10">Unit</th>
              <th className="text-right px-2 py-2 font-semibold text-rpmx-steel w-20">Labor</th>
              <th className="text-right px-2 py-2 font-semibold text-rpmx-steel w-20">Material</th>
              <th className="text-right px-2 py-2 font-semibold text-rpmx-steel w-20">Equip</th>
              <th className="text-right px-3 py-2 font-semibold text-rpmx-steel w-24">Total</th>
            </tr>
          </thead>
          <tbody>
            {categoryOrder.map((cat) => (
              <Fragment key={cat}>
                {/* Category Header */}
                <tr className="bg-gray-50/60">
                  <td colSpan={7} className="px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider text-rpmx-steel border-t border-rpmx-slate/30">
                    {cat}
                  </td>
                </tr>
                {/* Line Items */}
                {grouped[cat].map((li, idx) => (
                  <tr key={idx} className="border-t border-rpmx-slate/20 hover:bg-blue-50/30">
                    <td className="px-3 py-1.5 text-rpmx-ink">{li.item}</td>
                    <td className="text-right px-2 py-1.5 text-rpmx-ink">{Number(li.quantity || 0).toLocaleString()}</td>
                    <td className="text-center px-2 py-1.5 text-rpmx-steel">{li.unit}</td>
                    <td className="text-right px-2 py-1.5 text-rpmx-ink">{fmtEstimateMoney(li.labor_cost)}</td>
                    <td className="text-right px-2 py-1.5 text-rpmx-ink">{Number(li.material_cost) === 0 ? '\u2014' : fmtEstimateMoney(li.material_cost)}</td>
                    <td className="text-right px-2 py-1.5 text-rpmx-ink">{Number(li.equipment_cost) === 0 ? '\u2014' : fmtEstimateMoney(li.equipment_cost)}</td>
                    <td className="text-right px-3 py-1.5 font-medium text-rpmx-ink">{fmtEstimateMoney(li.subtotal)}</td>
                  </tr>
                ))}
                {/* Category Subtotal */}
                <tr className="border-t border-rpmx-slate/30 bg-gray-50/40">
                  <td colSpan={6} className="px-3 py-1.5 text-right text-[10px] font-semibold text-rpmx-steel uppercase">{cat} Subtotal</td>
                  <td className="text-right px-3 py-1.5 font-bold text-rpmx-ink">{fmtEstimateMoney(categorySubtotals[cat])}</td>
                </tr>
              </Fragment>
            ))}
            {/* Direct Cost Total */}
            <tr className="border-t-2 border-rpmx-slate/30 bg-gray-100">
              <td colSpan={6} className="px-3 py-2 text-right font-bold text-rpmx-ink text-xs">Direct Cost Total</td>
              <td className="text-right px-3 py-2 font-bold text-rpmx-ink text-xs">{fmtEstimateMoney(directCost)}</td>
            </tr>
            {/* Markups */}
            <tr className="bg-amber-50/40">
              <td colSpan={7} className="px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider text-amber-700 border-t border-amber-200">
                Markups
              </td>
            </tr>
            {[
              ['Overhead (12%)', markups.overhead],
              ['Profit (10%)', markups.profit],
              ['Contingency (5%)', markups.contingency],
              ['Bond (1.5%)', markups.bond],
              ['Mobilization (3%)', markups.mobilization],
            ].map(([label, value]) => (
              value != null && (
                <tr key={label} className="border-t border-amber-100 bg-amber-50/20">
                  <td colSpan={6} className="px-3 py-1 text-right text-rpmx-steel text-[11px]">{label}</td>
                  <td className="text-right px-3 py-1 text-rpmx-ink text-[11px]">{fmtEstimateMoney(value)}</td>
                </tr>
              )
            ))}
            {/* Grand Total */}
            <tr className="border-t-2 border-blue-300 bg-blue-50">
              <td colSpan={6} className="px-3 py-2.5 text-right font-bold text-blue-900 text-sm">Grand Total</td>
              <td className="text-right px-3 py-2.5 font-bold text-blue-900 text-sm">{fmtEstimateMoney(grandTotal)}</td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* Assumptions & Exclusions */}
      <div className="mx-3 mt-3 grid gap-3 sm:grid-cols-2">
        <div className="rounded-lg ring-1 ring-rpmx-slate/15 bg-white p-3 text-xs">
          <p className="font-semibold text-rpmx-steel flex items-center gap-1.5">
            <svg className="h-3.5 w-3.5 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Assumptions
          </p>
          <ul className="mt-1.5 space-y-1 text-rpmx-ink">
            {assumptions.map((a, idx) => (
              <li key={idx} className="flex items-start gap-1.5">
                <span className="mt-1 h-1 w-1 rounded-full bg-emerald-400 shrink-0" />
                {a}
              </li>
            ))}
          </ul>
        </div>
        <div className="rounded-lg ring-1 ring-rpmx-slate/15 bg-white p-3 text-xs">
          <p className="font-semibold text-rpmx-steel flex items-center gap-1.5">
            <svg className="h-3.5 w-3.5 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
            </svg>
            Exclusions
          </p>
          <ul className="mt-1.5 space-y-1 text-rpmx-ink">
            {exclusions.map((e, idx) => (
              <li key={idx} className="flex items-start gap-1.5">
                <span className="mt-1 h-1 w-1 rounded-full bg-red-400 shrink-0" />
                {e}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Schedule & Validity */}
      {(proposal.schedule_statement || proposal.validity_statement) && (
        <div className="mx-3 mt-3 mb-3 rounded-lg ring-1 ring-rpmx-slate/15 bg-white p-3 text-xs text-rpmx-steel">
          {proposal.schedule_statement && (
            <p className="flex items-start gap-1.5">
              <svg className="h-3.5 w-3.5 text-blue-500 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              <span className="text-rpmx-ink">{proposal.schedule_statement}</span>
            </p>
          )}
          {proposal.validity_statement && (
            <p className="flex items-start gap-1.5 mt-1.5">
              <svg className="h-3.5 w-3.5 text-amber-500 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="text-rpmx-ink">{proposal.validity_statement}</span>
            </p>
          )}
        </div>
      )}
      {/* Bottom spacing when no schedule/validity */}
      {!proposal.schedule_statement && !proposal.validity_statement && <div className="h-3" />}
    </div>
  )
}

function ArFollowUpArtifact({ output, communications }) {
  const results = output?.results || []
  const aging = output?.aging_summary
  const ACTION_STYLES = {
    polite_reminder: { label: 'Polite Reminder', color: 'bg-blue-100 text-blue-700', border: 'border-l-blue-400' },
    firm_email_plus_internal_task: { label: 'Firm Email + Task', color: 'bg-amber-100 text-amber-700', border: 'border-l-amber-400' },
    escalated_to_collections: { label: 'Collections', color: 'bg-red-100 text-red-700', border: 'border-l-red-400' },
    skip_retainage: { label: 'Skip (Retainage)', color: 'bg-gray-100 text-gray-600', border: 'border-l-gray-400' },
    no_action_within_terms: { label: 'Within Terms', color: 'bg-emerald-100 text-emerald-700', border: 'border-l-emerald-400' },
  }
  const fmtAR = (v) => {
    if (v == null) return '--'
    if (v >= 1000) return '$' + Math.round(v).toLocaleString()
    return '$' + Number(v).toFixed(2)
  }
  return (
    <div className="space-y-3">
      {/* ── Aging Summary Bar ── */}
      {aging && (
        <div className="rounded-xl ring-1 ring-rpmx-slate/15 bg-white p-3">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold text-rpmx-ink">AR Aging Summary</h3>
            <span className="text-xs font-semibold text-rpmx-steel">{aging.total_accounts} accounts · {fmtAR(aging.total_outstanding)} outstanding</span>
          </div>
          <div className="grid grid-cols-4 gap-2">
            {[
              { label: 'Current (0–30)', key: 'current', bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200' },
              { label: '31–60 Days', key: '30_60', bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200' },
              { label: '61–90 Days', key: '61_90', bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200' },
              { label: 'Over 90', key: 'over_90', bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200' },
            ].map(b => (
              <div key={b.key} className={`rounded-lg border ${b.border} ${b.bg} p-2 text-center`}>
                <p className={`text-base font-bold ${b.text}`}>{fmtAR(aging.bucket_amounts?.[b.key])}</p>
                <p className="text-[10px] text-rpmx-steel mt-0.5">{aging.buckets?.[b.key] || 0} acct{(aging.buckets?.[b.key] || 0) !== 1 ? 's' : ''} · {b.label}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid gap-3 xl:grid-cols-[52%_48%]">
        {/* ── AR Action Plan ── */}
        <div className="flex flex-col overflow-hidden rounded-xl ring-1 ring-rpmx-slate/15 bg-rpmx-canvas">
          <div className="border-b border-rpmx-slate/25 bg-white px-3 py-2">
            <h3 className="text-sm font-semibold">AR Action Plan</h3>
            {results.length > 0 && <p className="text-[10px] text-rpmx-steel mt-0.5">{results.length} accounts reviewed</p>}
          </div>
          <div className="flex-1 overflow-auto p-3 space-y-2">
            {results.map((item) => {
              const style = ACTION_STYLES[item.action] || ACTION_STYLES.polite_reminder
              return (
                <article key={item.customer} className={`rounded-lg border-l-[3px] ring-1 ring-rpmx-slate/12 bg-white p-2.5 text-xs animate-slide-in ${style.border}`}>
                  <div className="flex items-center justify-between">
                    <p className="font-semibold text-rpmx-ink">{item.customer}</p>
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${style.color}`}>
                      {style.label}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 mt-1">
                    {item.amount != null && <span className="font-semibold text-rpmx-ink">{fmtAR(item.amount)}</span>}
                    {item.days_out != null && <span className="text-rpmx-steel">{item.days_out} days outstanding</span>}
                    {item.is_retainage && <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[9px] font-medium text-gray-600">Retainage</span>}
                  </div>
                  <p className="mt-1 text-rpmx-steel">{item.reason}</p>
                </article>
              )
            })}
          </div>
        </div>
        {/* ── Communications Sent ── */}
        <div className="flex flex-col overflow-hidden rounded-xl ring-1 ring-rpmx-slate/15 bg-rpmx-canvas">
          <div className="border-b border-rpmx-slate/25 bg-white px-3 py-2">
            <h3 className="text-sm font-semibold">Communications Sent</h3>
          </div>
          <div className="flex-1 overflow-auto p-3 space-y-2">
            {(communications || []).length === 0 && <p className="text-sm text-rpmx-steel">No communications sent yet.</p>}
            {(communications || []).map((entry) => (
              <article key={entry.id} className="rounded-lg border-l-[3px] border-l-fuchsia-400 ring-1 ring-rpmx-slate/12 bg-white p-2.5 text-xs animate-slide-in">
                <p className="font-semibold text-fuchsia-800">{entry.subject}</p>
                <p className="text-rpmx-steel">To: {entry.recipient}</p>
                <p className="mt-1 text-rpmx-ink">{entry.body}</p>
              </article>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function InquiryRouterArtifact({ output }) {
  const routes = output?.routes || []
  const inbox = output?.inbox_summary
  const PRIORITY_COLORS = {
    high: 'bg-red-100 text-red-700',
    medium: 'bg-amber-100 text-amber-700',
    low: 'bg-emerald-100 text-emerald-700',
  }
  const DEPT_COLORS = {
    'Accounts Receivable': { bg: 'bg-amber-50', border: 'border-l-amber-400', badge: 'bg-amber-100 text-amber-700' },
    'AR': { bg: 'bg-amber-50', border: 'border-l-amber-400', badge: 'bg-amber-100 text-amber-700' },
    'Billing': { bg: 'bg-amber-50', border: 'border-l-amber-400', badge: 'bg-amber-100 text-amber-700' },
    'Estimating': { bg: 'bg-blue-50', border: 'border-l-blue-400', badge: 'bg-blue-100 text-blue-700' },
    'Dispatch': { bg: 'bg-emerald-50', border: 'border-l-emerald-400', badge: 'bg-emerald-100 text-emerald-700' },
    'Operations': { bg: 'bg-emerald-50', border: 'border-l-emerald-400', badge: 'bg-emerald-100 text-emerald-700' },
    'Management': { bg: 'bg-purple-50', border: 'border-l-purple-400', badge: 'bg-purple-100 text-purple-700' },
  }
  const DEFAULT_DEPT = { bg: 'bg-gray-50', border: 'border-l-gray-400', badge: 'bg-gray-100 text-gray-700' }
  const getDeptStyle = (dept) => DEPT_COLORS[dept] || DEFAULT_DEPT
  return (
    <div className="space-y-3">
      {/* Inbox Summary Bar */}
      {inbox && (
        <div className="rounded-xl ring-1 ring-rpmx-slate/15 bg-white p-3">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold text-rpmx-ink">📬 Inbox Summary</h3>
            <span className="text-[10px] text-rpmx-steel">{inbox.total_emails} emails processed</span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <div className="rounded-lg bg-gray-50 p-2 text-center">
              <p className="text-lg font-bold text-rpmx-ink">{inbox.total_emails}</p>
              <p className="text-[10px] text-rpmx-steel">Total Emails</p>
            </div>
            <div className={`rounded-lg p-2 text-center ${inbox.urgent > 0 ? 'bg-red-50' : 'bg-gray-50'}`}>
              <p className={`text-lg font-bold ${inbox.urgent > 0 ? 'text-red-600' : 'text-rpmx-ink'}`}>{inbox.urgent}</p>
              <p className="text-[10px] text-rpmx-steel">Urgent</p>
            </div>
            {Object.entries(inbox.departments || {}).map(([dept, count]) => {
              const style = getDeptStyle(dept)
              return (
                <div key={dept} className={`rounded-lg ${style.bg} p-2 text-center`}>
                  <p className="text-lg font-bold text-rpmx-ink">{count}</p>
                  <p className="text-[10px] text-rpmx-steel">{dept}</p>
                </div>
              )
            })}
          </div>
        </div>
      )}
      {/* Email Cards */}
      <div className="rounded-xl ring-1 ring-rpmx-slate/15 bg-rpmx-canvas overflow-hidden">
        <div className="border-b border-rpmx-slate/25 bg-white px-3 py-2">
          <h3 className="text-sm font-semibold">Routing Decisions</h3>
        </div>
        <div className="p-3 space-y-2">
          {routes.map((route, idx) => {
            const deptStyle = getDeptStyle(route.route)
            return (
              <article key={idx} className={`rounded-lg border-l-[3px] ${deptStyle.border} ring-1 ring-rpmx-slate/12 bg-white p-2.5 text-xs animate-slide-in`}>
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold text-rpmx-ink">{route.subject}</p>
                    <p className="mt-0.5 text-rpmx-steel">From: {route.from}</p>
                  </div>
                  <div className="flex flex-col items-end gap-1 shrink-0">
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${deptStyle.badge}`}>
                      {route.route}
                    </span>
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${PRIORITY_COLORS[route.priority] || PRIORITY_COLORS.medium}`}>
                      {route.priority}
                    </span>
                  </div>
                </div>
                {route.description && <p className="mt-1.5 text-rpmx-steel border-t border-rpmx-slate/30 pt-1.5">{route.description}</p>}
              </article>
            )
          })}
        </div>
      </div>
    </div>
  )
}

export default function ArtifactRenderer({ agentId, output, currentInvoicePath, communications, activeInvoice, activeVendor, activeAmount, running, reports }) {
  if (agentId === 'po_match') {
    return <PoMatchArtifact output={output} currentInvoicePath={currentInvoicePath} activeInvoice={activeInvoice} activeVendor={activeVendor} activeAmount={activeAmount} running={running} />
  }
  if (agentId === 'financial_reporting') {
    return <FinancialReportArtifact output={output} reports={reports} />
  }
  if (agentId === 'schedule_optimizer') {
    return <ScheduleMapArtifact output={output} />
  }
  if (agentId === 'onboarding') {
    return <ChecklistArtifact output={output} />
  }
  if (agentId === 'cost_estimator') {
    return <CostEstimateArtifact output={output} />
  }
  if (agentId === 'ar_followup') {
    return <ArFollowUpArtifact output={output} communications={communications} />
  }
  if (agentId === 'inquiry_router') {
    return <InquiryRouterArtifact output={output} />
  }
  if (agentId === 'vendor_compliance') {
    return <VendorComplianceArtifact output={output} communications={communications} />
  }
  if (agentId === 'progress_tracking') {
    return <ProgressTrackingArtifact output={output} />
  }
  if (agentId === 'maintenance_scheduler') {
    return <MaintenanceArtifact output={output} />
  }
  if (agentId === 'training_compliance') {
    return <TrainingComplianceArtifact output={output} />
  }

  return (
    <div className="h-[62vh] overflow-auto rounded-xl ring-1 ring-rpmx-slate/15 bg-rpmx-canvas p-3">
      <h3 className="text-sm font-semibold">Work Artifact</h3>
      {renderJson(output || {})}
    </div>
  )
}
