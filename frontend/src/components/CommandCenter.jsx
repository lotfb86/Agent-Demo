import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiGet } from '../api'

/* ─────────────────────────────────────────
   DEPARTMENT GROUPS
───────────────────────────────────────── */
const GROUPS = {
  Financial:       ['Accounts Payable', 'Accounts Receivable', 'General Accounting', 'Estimating'],
  Operations:      ['Procurement', 'Scheduling', 'Project Management', 'Fleet & Equipment', 'Customer Service'],
  'People & Safety': ['Safety', 'Human Resources'],
}

const GROUP_ORDER = ['Financial', 'Operations', 'People & Safety']

/* ─────────────────────────────────────────
   DEPARTMENT ICONS (Heroicons outline 20px)
───────────────────────────────────────── */
function DeptIcon({ department }) {
  const paths = {
    'Accounts Payable': 'M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z',
    'Accounts Receivable': 'M2.25 18.75a60.07 60.07 0 0115.797 2.101c.727.198 1.453-.342 1.453-1.096V18.75M3.75 4.5v.75A.75.75 0 013 6h-.75m0 0v-.375c0-.621.504-1.125 1.125-1.125H20.25M2.25 6v9m18-10.5v.75c0 .414.336.75.75.75h.75m-1.5-1.5h.375c.621 0 1.125.504 1.125 1.125v9.75c0 .621-.504 1.125-1.125 1.125h-.375m1.5-1.5H21a.75.75 0 00-.75.75v.75m0 0H3.75m0 0h-.375a1.125 1.125 0 01-1.125-1.125V15m1.5 1.5v-.75A.75.75 0 003 15h-.75M15 10.5a3 3 0 11-6 0 3 3 0 016 0zm3 0h.008v.008H18V10.5zm-12 0h.008v.008H6V10.5z',
    'General Accounting': 'M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z',
    'Estimating': 'M15.75 15.75V18m-7.5-6.75h.008v.008H8.25v-.008zm0 2.25h.008v.008H8.25V13.5zm0 2.25h.008v.008H8.25v-.008zm0 2.25h.008v.008H8.25V18zm2.498-6.75h.007v.008h-.007v-.008zm0 2.25h.007v.008h-.007V13.5zm0 2.25h.007v.008h-.007v-.008zm0 2.25h.007v.008h-.007V18zm2.504-6.75h.008v.008h-.008v-.008zm0 2.25h.008v.008h-.008V13.5zm0 2.25h.008v.008h-.008v-.008zm0 2.25h.008v.008h-.008V18zm2.498-6.75h.008v.008h-.008v-.008zm0 2.25h.008v.008h-.008V13.5zM8.25 6h7.5v2.25h-7.5V6zM12 2.25c-1.892 0-3.758.11-5.593.322C5.307 2.7 4.5 3.65 4.5 4.757V19.5a2.25 2.25 0 002.25 2.25h10.5a2.25 2.25 0 002.25-2.25V4.757c0-1.108-.806-2.057-1.907-2.185A48.507 48.507 0 0012 2.25z',
    'Customer Service': 'M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75',
    'Fleet & Equipment': 'M8.25 18.75a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m3 0h6m-9 0H3.375a1.125 1.125 0 01-1.125-1.125V14.25m17.25 4.5a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m3 0h1.125c.621 0 1.129-.504 1.09-1.124a17.902 17.902 0 00-3.213-9.193 2.056 2.056 0 00-1.58-.86H14.25M16.5 18.75h-2.25m0-11.177v-.958c0-.568-.422-1.048-.987-1.106a48.554 48.554 0 00-10.026 0 1.106 1.106 0 00-.987 1.106v7.635m12-6.677v6.677m0 4.5v-4.5m0 0h-12',
    'Project Management': 'M6 6.878V6a2.25 2.25 0 012.25-2.25h7.5A2.25 2.25 0 0118 6v.878m-12 0c.235-.083.487-.128.75-.128h10.5c.263 0 .515.045.75.128m-12 0A2.25 2.25 0 004.5 9v.878m13.5-3A2.25 2.25 0 0119.5 9v.878m0 0a2.246 2.246 0 00-.75-.128H5.25c-.263 0-.515.045-.75.128m15 0A2.25 2.25 0 0121 12v6a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 18v-6c0-1.007.662-1.86 1.574-2.147',
    'Procurement': 'M2.25 3h1.386c.51 0 .955.343 1.087.835l.383 1.437M7.5 14.25a3 3 0 00-3 3h15.75m-12.75-3h11.218c1.121-2.3 2.1-4.684 2.924-7.138a60.114 60.114 0 00-16.536-1.84M7.5 14.25L5.106 5.272M6 20.25a.75.75 0 11-1.5 0 .75.75 0 011.5 0zm12.75 0a.75.75 0 11-1.5 0 .75.75 0 011.5 0z',
    'Scheduling': 'M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5m-9-6h.008v.008H12v-.008zM12 15h.008v.008H12V15zm0 2.25h.008v.008H12v-.008zM9.75 15h.008v.008H9.75V15zm0 2.25h.008v.008H9.75v-.008zM7.5 15h.008v.008H7.5V15zm0 2.25h.008v.008H7.5v-.008zm6.75-4.5h.008v.008h-.008v-.008zm0 2.25h.008v.008h-.008V15zm0 2.25h.008v.008h-.008v-.008zM16.5 12.75h.008v.008h-.008v-.008zm0 2.25h.008v.008h-.008V15z',
    'Safety': 'M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z',
    'Human Resources': 'M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z',
  }

  const defaultPath = 'M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z M15 12a3 3 0 11-6 0 3 3 0 016 0z'

  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d={paths[department] || defaultPath} />
    </svg>
  )
}

/* ─────────────────────────────────────────
   STATUS HELPERS
───────────────────────────────────────── */
function getStatusConfig(agent) {
  if (agent.status === 'error') {
    return { badge: 'badge-red', dot: 'bg-red-500', label: 'Error', pulse: false }
  }
  if (agent.status === 'working') {
    return { badge: 'badge-blue', dot: 'bg-blue-500', label: 'Active', pulse: true }
  }
  if (agent.review_count > 0) {
    return { badge: 'badge-amber', dot: 'bg-amber-500', label: 'Review', pulse: false }
  }
  return { badge: 'badge-slate', dot: 'bg-slate-300', label: 'Ready', pulse: false }
}

function departmentGroup(dept) {
  return (
    Object.entries(GROUPS).find(([, depts]) => depts.includes(dept))?.[0] || 'Other'
  )
}

/* ─────────────────────────────────────────
   SKELETON CARD
───────────────────────────────────────── */
function SkeletonCard() {
  return (
    <div className="card p-5 space-y-4">
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-3">
          <div className="skeleton h-9 w-9 rounded-lg" />
          <div className="space-y-2 flex-1">
            <div className="skeleton h-4 w-32 rounded" />
            <div className="skeleton h-3 w-24 rounded" />
          </div>
        </div>
        <div className="skeleton h-6 w-16 rounded-full" />
      </div>
      <div className="space-y-2">
        <div className="skeleton h-3 w-full rounded" />
        <div className="skeleton h-3 w-3/4 rounded" />
      </div>
      <div className="border-t border-rpmx-wash pt-3 flex justify-between">
        <div className="skeleton h-3 w-24 rounded" />
        <div className="skeleton h-3 w-12 rounded" />
      </div>
    </div>
  )
}

/* ─────────────────────────────────────────
   KPI METRIC
───────────────────────────────────────── */
function KpiCard({ value, label, dotColor, pulse }) {
  return (
    <div className="card flex items-center gap-3 px-5 py-4 min-w-[120px]">
      <div className={`h-2.5 w-2.5 rounded-full flex-shrink-0 ${dotColor} ${pulse ? 'animate-pulse' : ''}`} />
      <div>
        <p className="text-xl font-bold text-rpmx-ink leading-none">{value}</p>
        <p className="text-xs text-rpmx-steel mt-0.5">{label}</p>
      </div>
    </div>
  )
}

/* ─────────────────────────────────────────
   AGENT CARD
───────────────────────────────────────── */
function AgentCard({ agent, onClick }) {
  const status = getStatusConfig(agent)
  const isWorking = agent.status === 'working'

  return (
    <button
      onClick={onClick}
      className={`card card-interactive group relative w-full text-left ${
        isWorking ? 'ring-2 ring-blue-400/30' : ''
      }`}
    >
      {/* Top accent stripe for active agents */}
      {isWorking && (
        <div className="absolute inset-x-0 top-0 h-0.5 rounded-t-lg bg-gradient-to-r from-blue-500 to-blue-400" />
      )}

      <div className="p-5">
        {/* Header row */}
        <div className="flex items-start justify-between gap-3 mb-4">
          <div className="flex items-start gap-3 min-w-0">
            <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-rpmx-deep text-rpmx-steel group-hover:bg-blue-50 group-hover:text-rpmx-signal transition-colors duration-150">
              <DeptIcon department={agent.department} />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-rpmx-ink leading-tight truncate">{agent.name}</p>
              <p className="text-xs text-rpmx-muted mt-0.5">{agent.department}</p>
            </div>
          </div>

          {/* Status badge */}
          <span className={`${status.badge} flex-shrink-0`}>
            <span className={`h-1.5 w-1.5 rounded-full ${status.dot} ${status.pulse ? 'animate-pulse' : ''}`} />
            {status.label}
          </span>
        </div>

        {/* Activity */}
        <p className="text-xs text-rpmx-steel leading-relaxed line-clamp-2 min-h-[32px]">
          {agent.current_activity
            ? <>{agent.current_activity}{isWorking && <span className="opacity-60 ml-0.5">…</span>}</>
            : <span className="italic text-rpmx-muted">No recent activity</span>
          }
        </p>

        {/* Footer row */}
        <div className="mt-4 pt-3 border-t border-rpmx-wash flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 text-xs text-rpmx-muted">
            {agent.review_count > 0 ? (
              <span className="badge-amber">{agent.review_count} review{agent.review_count !== 1 ? 's' : ''}</span>
            ) : agent.last_run_at ? (
              `Last run ${new Date(agent.last_run_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
            ) : (
              <span className="italic">Not yet run</span>
            )}
          </div>
          <div className="flex items-center gap-3 text-xs text-rpmx-muted">
            {Number(agent.cost_today || 0) > 0 && (
              <span className="font-mono font-semibold text-rpmx-steel">${Number(agent.cost_today).toFixed(2)}</span>
            )}
            <span>{agent.tasks_completed_today || 0} done</span>
          </div>
        </div>
      </div>
    </button>
  )
}

/* ─────────────────────────────────────────
   SECTION HEADER
───────────────────────────────────────── */
function SectionHeader({ title, count }) {
  return (
    <div className="section-header">
      <div className="section-header-accent" />
      <h2 className="text-xs font-bold uppercase tracking-widest text-rpmx-ink">{title}</h2>
      <span className="ml-auto text-xs font-medium text-rpmx-muted bg-rpmx-deep px-2.5 py-1 rounded-full">
        {count} agent{count !== 1 ? 's' : ''}
      </span>
    </div>
  )
}

/* ─────────────────────────────────────────
   MAIN COMPONENT
───────────────────────────────────────── */
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
    return () => { mounted = false; clearInterval(timer) }
  }, [])

  const grouped = useMemo(() => {
    return agents.reduce((acc, agent) => {
      const group = departmentGroup(agent.department)
      if (!acc[group]) acc[group] = []
      acc[group].push(agent)
      return acc
    }, {})
  }, [agents])

  const activeCount  = agents.filter(a => a.status === 'working').length
  const reviewCount  = agents.reduce((sum, a) => sum + (a.review_count || 0), 0)
  const doneToday    = agents.reduce((sum, a) => sum + (a.tasks_completed_today || 0), 0)

  const orderedGroups = [...GROUP_ORDER, ...Object.keys(grouped).filter(g => !GROUP_ORDER.includes(g))]
    .filter(g => grouped[g]?.length)

  return (
    <div className="min-h-screen bg-rpmx-canvas">
      <div className="mx-auto max-w-7xl px-6 sm:px-8 py-10 sm:py-14">

        {/* ── Page Header ── */}
        <header className="mb-10 animate-fade-in">
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-6">

            {/* Left: Wordmark + Title */}
            <div>
              <div className="flex items-center gap-2 mb-3">
                <div className="flex h-7 w-7 items-center justify-center rounded-md bg-rpmx-signal">
                  <svg className="h-4 w-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
                  </svg>
                </div>
                <span className="text-xs font-bold uppercase tracking-[0.14em] text-rpmx-muted">RPMX</span>
              </div>
              <h1 className="text-[28px] font-bold tracking-tight text-rpmx-ink leading-tight">
                Command Center
              </h1>
              <p className="mt-1.5 text-sm text-rpmx-steel">
                Monitor and manage your AI workforce
              </p>
            </div>

            {/* Right: KPI Metrics */}
            <div className="flex items-center gap-3 flex-shrink-0 flex-wrap">
              <KpiCard
                value={activeCount}
                label="Active now"
                dotColor="bg-blue-500"
                pulse={activeCount > 0}
              />
              <KpiCard
                value={reviewCount}
                label="In review"
                dotColor={reviewCount > 0 ? 'bg-amber-500' : 'bg-slate-300'}
                pulse={false}
              />
              <KpiCard
                value={doneToday}
                label="Completed today"
                dotColor="bg-slate-300"
                pulse={false}
              />
            </div>
          </div>

          {/* Divider */}
          <div className="mt-8 h-px bg-gradient-to-r from-rpmx-wash via-rpmx-wash/40 to-transparent" />
        </header>

        {/* ── Loading State ── */}
        {loading && (
          <div className="space-y-10 animate-fade-in">
            {['Financial', 'Operations', 'People & Safety'].map(g => (
              <section key={g}>
                <div className="section-header">
                  <div className="section-header-accent" />
                  <div className="skeleton h-3 w-24 rounded" />
                </div>
                <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
                  {[1, 2, 3].map(i => <SkeletonCard key={i} />)}
                </div>
              </section>
            ))}
          </div>
        )}

        {/* ── Error State ── */}
        {error && !loading && (
          <div className="card border-red-200 bg-red-50 px-5 py-4 flex items-start gap-3">
            <div className="h-5 w-5 flex-shrink-0 text-red-500 mt-0.5">
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
              </svg>
            </div>
            <div>
              <p className="text-sm font-semibold text-red-800">Failed to load agents</p>
              <p className="text-xs text-red-600 mt-0.5">{error}</p>
            </div>
          </div>
        )}

        {/* ── Agent Groups ── */}
        {!loading && !error && (
          <div className="space-y-10">
            {orderedGroups.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state-icon">
                  <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
                  </svg>
                </div>
                <p className="text-sm font-semibold text-rpmx-ink">No agents found</p>
                <p className="text-xs text-rpmx-muted mt-1">Agents will appear here once configured.</p>
              </div>
            ) : (
              orderedGroups.map((groupName, idx) => (
                <section
                  key={groupName}
                  className="animate-fade-in"
                  style={{ animationDelay: `${idx * 60}ms` }}
                >
                  <SectionHeader title={groupName} count={grouped[groupName].length} />

                  <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
                    {[...grouped[groupName]]
                      .sort((a, b) => a.name.localeCompare(b.name))
                      .map(agent => (
                        <AgentCard
                          key={agent.id}
                          agent={agent}
                          onClick={() => navigate(`/agent/${agent.id}`)}
                        />
                      ))
                    }
                  </div>
                </section>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  )
}
