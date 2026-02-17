import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiGet } from '../api'

const GROUPS = {
  Financial: ['Accounts Payable', 'Accounts Receivable', 'General Accounting', 'Estimating'],
  Operations: ['Procurement', 'Scheduling', 'Project Management', 'Fleet & Equipment', 'Customer Service'],
  'People & Safety': ['Safety', 'Human Resources'],
}

function statusColor(agent) {
  if (agent.status === 'error') return 'bg-rpmx-danger'
  if (agent.status === 'working') return 'bg-rpmx-mint'
  if (agent.review_count > 0) return 'bg-rpmx-amber'
  return 'bg-sky-400'
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
      <div className="mx-auto max-w-7xl px-6 py-8 sm:px-10 lg:py-10">
        <header className="mb-8 rounded-3xl border border-rpmx-slate/80 bg-gradient-to-r from-white via-[#fef8f4] to-[#eef7ff] p-6 shadow-glow animate-rise">
          <div className="flex items-start justify-between">
            <div>
              <p className="font-mono text-xs uppercase tracking-[0.18em] text-rpmx-steel">RPMX Construction</p>
              <h1 className="mt-2 text-3xl font-semibold tracking-tight">Command Center</h1>
            </div>
            <div className="flex gap-3">
              <div className="rounded-xl border border-rpmx-slate/50 bg-white/80 px-4 py-2.5 text-center min-w-[90px]">
                <p className={`text-2xl font-bold ${activeAgents > 0 ? 'text-rpmx-mint' : 'text-rpmx-ink'}`}>{activeAgents}</p>
                <p className="text-[10px] font-medium uppercase tracking-wide text-rpmx-steel">Active</p>
              </div>
              <div className="rounded-xl border border-rpmx-slate/50 bg-white/80 px-4 py-2.5 text-center min-w-[90px]">
                <p className={`text-2xl font-bold ${reviewCount > 0 ? 'text-rpmx-amber' : 'text-rpmx-ink'}`}>{reviewCount}</p>
                <p className="text-[10px] font-medium uppercase tracking-wide text-rpmx-steel">Review</p>
              </div>
              <div className="rounded-xl border border-rpmx-slate/50 bg-white/80 px-4 py-2.5 text-center min-w-[90px]">
                <p className="text-2xl font-bold text-rpmx-ink">{tasksToday}</p>
                <p className="text-[10px] font-medium uppercase tracking-wide text-rpmx-steel">Completed</p>
              </div>
            </div>
          </div>
        </header>

        {loading && <p className="text-rpmx-steel">Loading agent workforce...</p>}
        {error && <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}

        <div className="space-y-8">
          {Object.keys(grouped)
            .sort()
            .map((groupName) => (
              <section key={groupName}>
                <h2 className="mb-3 text-sm font-semibold uppercase tracking-widest text-rpmx-steel">
                  {groupName}
                </h2>
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                  {grouped[groupName]
                    .sort((a, b) => a.name.localeCompare(b.name))
                    .map((agent) => {
                      const isWorking = agent.status === 'working'
                      return (
                        <button
                          key={agent.id}
                          onClick={() => navigate(`/agent/${agent.id}`)}
                          className={`group rounded-2xl border bg-rpmx-panel p-4 text-left shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:shadow-glow ${
                            isWorking
                              ? 'border-l-4 border-l-rpmx-mint border-rpmx-slate/60'
                              : 'border-rpmx-slate/80 hover:border-rpmx-signal/40'
                          }`}
                        >
                          <div className="flex items-start justify-between gap-4">
                            <div>
                              <p className="text-base font-semibold text-rpmx-ink">{agent.name}</p>
                              <p className="mt-1 text-xs uppercase tracking-wide text-rpmx-steel">
                                {agent.department}
                              </p>
                            </div>
                            <span className="relative mt-1 flex h-3 w-3">
                              {isWorking && (
                                <span className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-75 ${statusColor(agent)}`} />
                              )}
                              <span className={`relative inline-flex h-3 w-3 rounded-full ${statusColor(agent)}`} />
                            </span>
                          </div>

                          <p className="mt-3 text-sm text-rpmx-steel">
                            {agent.current_activity}
                            {isWorking && <span className="ml-1 animate-pulse">...</span>}
                          </p>
                          <div className="mt-4 flex items-center justify-between text-xs text-rpmx-steel">
                            <span>{agent.review_count > 0 ? (
                              <span className="rounded-full bg-rpmx-amber/15 px-2 py-0.5 font-semibold text-rpmx-amber">{agent.review_count} in review</span>
                            ) : agent.last_run_at ? (
                              <span className="text-[10px]">Last run: {new Date(agent.last_run_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                            ) : (
                              <span className="text-[10px] text-rpmx-steel/60">Not yet run</span>
                            )}</span>
                            <span className="font-mono">${Number(agent.cost_today || 0).toFixed(2)} today</span>
                          </div>
                        </button>
                      )
                    })}
                </div>
              </section>
            ))}
        </div>
      </div>
    </div>
  )
}
