import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiGet } from '../api'

const GROUPS = {
  Financial: ['Accounts Payable', 'Accounts Receivable', 'General Accounting', 'Estimating'],
  Operations: ['Procurement', 'Scheduling', 'Project Management', 'Fleet & Equipment', 'Customer Service'],
  'People & Safety': ['Safety', 'Human Resources'],
}

/* ── Category-aware icon per department ── */
const DEPT_ICONS = {
  'Accounts Payable': (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
    </svg>
  ),
  'Accounts Receivable': (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18.75a60.07 60.07 0 0115.797 2.101c.727.198 1.453-.342 1.453-1.096V18.75M3.75 4.5v.75A.75.75 0 013 6h-.75m0 0v-.375c0-.621.504-1.125 1.125-1.125H20.25M2.25 6v9m18-10.5v.75c0 .414.336.75.75.75h.75m-1.5-1.5h.375c.621 0 1.125.504 1.125 1.125v9.75c0 .621-.504 1.125-1.125 1.125h-.375m1.5-1.5H21a.75.75 0 00-.75.75v.75m0 0H3.75m0 0h-.375a1.125 1.125 0 01-1.125-1.125V15m1.5 1.5v-.75A.75.75 0 003 15h-.75M15 10.5a3 3 0 11-6 0 3 3 0 016 0zm3 0h.008v.008H18V10.5zm-12 0h.008v.008H6V10.5z" />
    </svg>
  ),
  'General Accounting': (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
    </svg>
  ),
  'Estimating': (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 15.75V18m-7.5-6.75h.008v.008H8.25v-.008zm0 2.25h.008v.008H8.25V13.5zm0 2.25h.008v.008H8.25v-.008zm0 2.25h.008v.008H8.25V18zm2.498-6.75h.007v.008h-.007v-.008zm0 2.25h.007v.008h-.007V13.5zm0 2.25h.007v.008h-.007v-.008zm0 2.25h.007v.008h-.007V18zm2.504-6.75h.008v.008h-.008v-.008zm0 2.25h.008v.008h-.008V13.5zm0 2.25h.008v.008h-.008v-.008zm0 2.25h.008v.008h-.008V18zm2.498-6.75h.008v.008h-.008v-.008zm0 2.25h.008v.008h-.008V13.5zM8.25 6h7.5v2.25h-7.5V6zM12 2.25c-1.892 0-3.758.11-5.593.322C5.307 2.7 4.5 3.65 4.5 4.757V19.5a2.25 2.25 0 002.25 2.25h10.5a2.25 2.25 0 002.25-2.25V4.757c0-1.108-.806-2.057-1.907-2.185A48.507 48.507 0 0012 2.25z" />
    </svg>
  ),
  'Customer Service': (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
    </svg>
  ),
  'Fleet & Equipment': (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M11.42 15.17l-5.384 3.164A1 1 0 015 17.482V6.518a1 1 0 011.036-.852L11.42 8.83m0 6.34l5.964 3.508A1 1 0 0018.5 17.834V6.166a1 1 0 00-1.116-.852L11.42 8.83m0 6.34V8.83" />
    </svg>
  ),
  'Project Management': (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 6.878V6a2.25 2.25 0 012.25-2.25h7.5A2.25 2.25 0 0118 6v.878m-12 0c.235-.083.487-.128.75-.128h10.5c.263 0 .515.045.75.128m-12 0A2.25 2.25 0 004.5 9v.878m13.5-3A2.25 2.25 0 0119.5 9v.878m0 0a2.246 2.246 0 00-.75-.128H5.25c-.263 0-.515.045-.75.128m15 0A2.25 2.25 0 0121 12v6a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 18v-6c0-1.007.662-1.86 1.574-2.147" />
    </svg>
  ),
  'Safety': (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
    </svg>
  ),
  'Human Resources': (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
    </svg>
  ),
}

const GROUP_COLORS = {
  Financial: { accent: 'from-emerald-500 to-teal-600', bg: 'bg-emerald-50', text: 'text-emerald-700', icon: 'text-emerald-600', dot: 'bg-emerald-500' },
  Operations: { accent: 'from-blue-500 to-indigo-600', bg: 'bg-blue-50', text: 'text-blue-700', icon: 'text-blue-600', dot: 'bg-blue-500' },
  'People & Safety': { accent: 'from-violet-500 to-purple-600', bg: 'bg-violet-50', text: 'text-violet-700', icon: 'text-violet-600', dot: 'bg-violet-500' },
}

function statusColor(agent) {
  if (agent.status === 'error') return 'bg-red-500'
  if (agent.status === 'working') return 'bg-emerald-500'
  if (agent.review_count > 0) return 'bg-amber-500'
  return 'bg-slate-300'
}

function statusLabel(agent) {
  if (agent.status === 'working') return 'Active'
  if (agent.status === 'error') return 'Error'
  if (agent.review_count > 0) return `${agent.review_count} review`
  return 'Ready'
}

function departmentGroup(department) {
  return (
    Object.entries(GROUPS).find(([, departments]) => departments.includes(department))?.[0] ||
    'Other'
  )
}

export default function CommandCenter() {
  const navigate = useNavigate()
  const [agents, setAgents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let mounted = true

    async function load() {
      try {
        const data = await apiGet('/api/agents')
        if (mounted) {
          setAgents(data)
          setError('')
          setLoading(false)
        }
      } catch (err) {
        if (mounted) {
          setError(err.message)
          setLoading(false)
        }
      }
    }

    load()
    const timer = setInterval(load, 4000)
    return () => {
      mounted = false
      clearInterval(timer)
    }
  }, [])

  const grouped = useMemo(() => {
    return agents.reduce((acc, agent) => {
      const group = departmentGroup(agent.department)
      if (!acc[group]) acc[group] = []
      acc[group].push(agent)
      return acc
    }, {})
  }, [agents])

  const activeAgents = agents.filter((agent) => agent.status === 'working').length
  const reviewCount = agents.reduce((sum, agent) => sum + (agent.review_count || 0), 0)
  const tasksToday = agents.reduce((sum, agent) => sum + (agent.tasks_completed_today || 0), 0)

  return (
    <div className="min-h-screen bg-rpmx-canvas text-rpmx-ink">
      <div className="mx-auto max-w-7xl px-6 py-6 sm:px-10 lg:py-8">
        {/* ── Header ── */}
        <header className="mb-8 animate-rise">
          <div className="flex items-end justify-between">
            <div>
              <div className="flex items-center gap-2.5 mb-1">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-rpmx-signal to-orange-600 shadow-sm">
                  <svg className="h-4 w-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
                  </svg>
                </div>
                <span className="text-[11px] font-semibold uppercase tracking-[0.2em] text-rpmx-steel">RPMX Construction</span>
              </div>
              <h1 className="text-2xl font-bold tracking-tight text-rpmx-ink sm:text-3xl">Command Center</h1>
            </div>

            {/* ── KPI pills ── */}
            <div className="flex gap-2">
              <div className="flex items-center gap-2.5 rounded-xl border border-rpmx-slate/40 bg-white px-4 py-2 shadow-card">
                <div className={`h-2 w-2 rounded-full ${activeAgents > 0 ? 'bg-emerald-500 animate-pulse' : 'bg-slate-300'}`} />
                <div>
                  <p className={`text-lg font-bold leading-none ${activeAgents > 0 ? 'text-emerald-600' : 'text-rpmx-ink'}`}>{activeAgents}</p>
                  <p className="mt-0.5 text-[9px] font-medium uppercase tracking-wider text-rpmx-steel">Active</p>
                </div>
              </div>
              <div className="flex items-center gap-2.5 rounded-xl border border-rpmx-slate/40 bg-white px-4 py-2 shadow-card">
                <div className={`h-2 w-2 rounded-full ${reviewCount > 0 ? 'bg-amber-500' : 'bg-slate-300'}`} />
                <div>
                  <p className={`text-lg font-bold leading-none ${reviewCount > 0 ? 'text-amber-600' : 'text-rpmx-ink'}`}>{reviewCount}</p>
                  <p className="mt-0.5 text-[9px] font-medium uppercase tracking-wider text-rpmx-steel">Review</p>
                </div>
              </div>
              <div className="flex items-center gap-2.5 rounded-xl border border-rpmx-slate/40 bg-white px-4 py-2 shadow-card">
                <div className="h-2 w-2 rounded-full bg-blue-500" />
                <div>
                  <p className="text-lg font-bold leading-none text-rpmx-ink">{tasksToday}</p>
                  <p className="mt-0.5 text-[9px] font-medium uppercase tracking-wider text-rpmx-steel">Done Today</p>
                </div>
              </div>
            </div>
          </div>
          {/* Subtle divider */}
          <div className="mt-5 h-px bg-gradient-to-r from-rpmx-slate/50 via-rpmx-slate/20 to-transparent" />
        </header>

        {loading && (
          <div className="flex items-center gap-3 py-12 justify-center">
            <span className="flex gap-1">
              <span className="h-2 w-2 rounded-full bg-rpmx-signal animate-pulse3" />
              <span className="h-2 w-2 rounded-full bg-rpmx-signal animate-pulse3" style={{ animationDelay: '160ms' }} />
              <span className="h-2 w-2 rounded-full bg-rpmx-signal animate-pulse3" style={{ animationDelay: '320ms' }} />
            </span>
            <span className="text-sm text-rpmx-steel">Loading agent workforce...</span>
          </div>
        )}
        {error && <p className="rounded-xl bg-red-50 border border-red-200/60 px-4 py-3 text-sm text-red-700">{error}</p>}

        <div className="space-y-8">
          {Object.keys(grouped)
            .sort()
            .map((groupName) => {
              const colors = GROUP_COLORS[groupName] || GROUP_COLORS.Operations
              return (
                <section key={groupName} className="animate-rise" style={{ animationDelay: `${Object.keys(grouped).sort().indexOf(groupName) * 80}ms` }}>
                  <div className="flex items-center gap-3 mb-3">
                    <div className={`h-1 w-5 rounded-full bg-gradient-to-r ${colors.accent}`} />
                    <h2 className="text-xs font-bold uppercase tracking-[0.15em] text-rpmx-steel">
                      {groupName}
                    </h2>
                    <span className="text-[10px] text-rpmx-muted">{grouped[groupName].length} agents</span>
                  </div>
                  <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                    {grouped[groupName]
                      .sort((a, b) => a.name.localeCompare(b.name))
                      .map((agent) => {
                        const isWorking = agent.status === 'working'
                        const icon = DEPT_ICONS[agent.department]
                        return (
                          <button
                            key={agent.id}
                            onClick={() => navigate(`/agent/${agent.id}`)}
                            className={`group relative rounded-xl bg-white p-4 text-left transition-all duration-200 hover:-translate-y-0.5 hover:shadow-card-hover ${
                              isWorking
                                ? 'shadow-elevated ring-1 ring-emerald-200/60'
                                : 'shadow-card ring-1 ring-rpmx-slate/20 hover:ring-rpmx-slate/40'
                            }`}
                          >
                            {/* Working indicator bar */}
                            {isWorking && (
                              <div className="absolute inset-x-0 top-0 h-0.5 rounded-t-xl bg-gradient-to-r from-emerald-400 via-emerald-500 to-teal-400" />
                            )}

                            <div className="flex items-start justify-between gap-3">
                              <div className="flex items-start gap-3">
                                {/* Icon */}
                                <div className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${colors.bg} ${colors.icon}`}>
                                  {icon || (
                                    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                                      <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" />
                                      <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                    </svg>
                                  )}
                                </div>
                                <div className="min-w-0">
                                  <p className="text-sm font-semibold text-rpmx-ink leading-snug">{agent.name}</p>
                                  <p className="mt-0.5 text-[10px] font-medium uppercase tracking-wider text-rpmx-muted">
                                    {agent.department}
                                  </p>
                                </div>
                              </div>
                              {/* Status */}
                              <div className="flex items-center gap-1.5 shrink-0">
                                <span className="relative flex h-2 w-2">
                                  {isWorking && (
                                    <span className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-75 ${statusColor(agent)}`} />
                                  )}
                                  <span className={`relative inline-flex h-2 w-2 rounded-full ${statusColor(agent)}`} />
                                </span>
                                <span className={`text-[10px] font-semibold ${
                                  isWorking ? 'text-emerald-600' :
                                  agent.status === 'error' ? 'text-red-500' :
                                  agent.review_count > 0 ? 'text-amber-600' :
                                  'text-rpmx-muted'
                                }`}>{statusLabel(agent)}</span>
                              </div>
                            </div>

                            {/* Tools count */}
                            <p className="mt-2.5 text-[10px] text-rpmx-muted">{agent.tool_count || 0} tools connected</p>

                            {/* Activity / current status */}
                            <p className="mt-1 text-xs text-rpmx-steel leading-relaxed">
                              {agent.current_activity}
                              {isWorking && <span className="ml-1 animate-pulse">...</span>}
                            </p>

                            {/* Footer */}
                            <div className="mt-3 flex items-center justify-between border-t border-rpmx-slate/15 pt-2.5">
                              <span className="text-[10px] text-rpmx-muted">
                                {agent.review_count > 0 ? (
                                  <span className="rounded-full bg-amber-50 px-2 py-0.5 font-semibold text-amber-600 ring-1 ring-amber-200/40">{agent.review_count} in review</span>
                                ) : agent.last_run_at ? (
                                  `Last run: ${new Date(agent.last_run_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
                                ) : (
                                  <span className="italic">Not yet run</span>
                                )}
                              </span>
                              {Number(agent.cost_today || 0) > 0 ? (
                                <span className="text-[10px] font-mono font-medium text-rpmx-steel">${Number(agent.cost_today).toFixed(2)}</span>
                              ) : (
                                <svg className="h-3.5 w-3.5 text-rpmx-slate opacity-0 group-hover:opacity-100 transition-opacity" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                  <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                                </svg>
                              )}
                            </div>
                          </button>
                        )
                      })}
                  </div>
                </section>
              )
            })}
        </div>
      </div>
    </div>
  )
}
