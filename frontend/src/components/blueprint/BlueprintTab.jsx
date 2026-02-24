import { useState, useMemo } from 'react'
import { FLOW_CONFIGS } from './flowConfigs'
import { NODE_STYLES } from './blueprintConstants'
import BlueprintRenderer from './BlueprintRenderer'
import BlueprintNodeDetail from './BlueprintNodeDetail'

/* ── Legend item ── */
function LegendItem({ type, label }) {
  const s = NODE_STYLES[type]
  return (
    <div className="flex items-center gap-1.5">
      <div
        className="w-3 h-3 rounded-sm"
        style={{
          backgroundColor: s.fill === 'url(#aiGradient)' ? '#fff5f0' : s.fill,
          border: `1.5px ${s.strokeDash ? 'dashed' : 'solid'} ${s.stroke}`,
        }}
      />
      <span className="text-[11px] text-rpmx-steel">{label}</span>
    </div>
  )
}

/* ── Main tab ── */
export default function BlueprintTab({ agentId }) {
  const [selectedNodeId, setSelectedNodeId] = useState(null)

  const config = FLOW_CONFIGS[agentId]

  const selectedNode = useMemo(() => {
    if (!config || !selectedNodeId) return null
    return config.nodes.find(n => n.id === selectedNodeId) || null
  }, [config, selectedNodeId])

  if (!config) {
    return (
      <div className="flex items-center justify-center h-64 text-rpmx-steel text-sm">
        Blueprint not available for this agent.
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="mb-3">
        <div className="flex items-center gap-2 mb-1">
          <h3 className="text-base font-semibold text-rpmx-ink">{config.title}</h3>
          <span className="text-[10px] font-semibold text-rpmx-steel bg-rpmx-canvas px-2 py-0.5 rounded-full">
            {config.subtitle}
          </span>
        </div>
        <p className="text-xs text-rpmx-steel leading-relaxed">{config.description}</p>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-x-4 gap-y-1 mb-3 pb-3 border-b border-rpmx-wash">
        <LegendItem type="source" label="Data Source" />
        <LegendItem type="process" label="Process Step" />
        <LegendItem type="ai_decision" label="AI Decision" />
        <LegendItem type="human" label="Human Review" />
        <LegendItem type="output" label="Output" />
        <div className="flex items-center gap-1.5">
          <div className="w-6 h-0 border-t-[1.5px] border-rpmx-slate" />
          <span className="text-[11px] text-rpmx-steel">Flow</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-6 h-0 border-t-[1.5px] border-dashed border-rpmx-amber" />
          <span className="text-[11px] text-rpmx-steel">Exception</span>
        </div>
      </div>

      {/* Diagram */}
      <div className="flex-1 min-h-0 overflow-auto rounded-lg border border-rpmx-wash bg-white">
        <BlueprintRenderer
          config={config}
          selectedNodeId={selectedNodeId}
          onNodeClick={(id) => setSelectedNodeId(prev => prev === id ? null : id)}
        />
      </div>

      {/* Detail panel */}
      <BlueprintNodeDetail node={selectedNode} />

      {/* Hint */}
      {!selectedNode && (
        <p className="text-[11px] text-rpmx-muted text-center mt-2 italic">
          Click any step in the diagram to see details
        </p>
      )}
    </div>
  )
}
