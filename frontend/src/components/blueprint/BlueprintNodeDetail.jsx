import { NODE_STYLES } from './blueprintConstants'
import { BlueprintIcon } from './blueprintIcons'

const TYPE_BADGES = {
  source:      { label: 'Data Source',  bg: 'bg-gray-100',       text: 'text-gray-600' },
  process:     { label: 'Process Step', bg: 'bg-gray-100',       text: 'text-gray-700' },
  ai_decision: { label: 'AI Decision',  bg: 'bg-orange-50',      text: 'text-orange-600' },
  human:       { label: 'Human Review', bg: 'bg-amber-50',       text: 'text-amber-600' },
  output:      { label: 'Output',       bg: 'bg-green-50',       text: 'text-green-600' },
}

export default function BlueprintNodeDetail({ node }) {
  if (!node) return null

  const badge = TYPE_BADGES[node.type] || TYPE_BADGES.process
  const style = NODE_STYLES[node.type] || NODE_STYLES.process

  return (
    <div className="animate-fade-in border border-rpmx-slate/40 rounded-xl bg-white p-4 mt-3">
      <div className="flex items-start gap-3">
        {/* Icon */}
        <div
          className="flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center"
          style={{ backgroundColor: style.fill === 'url(#aiGradient)' ? '#fff5f0' : style.fill, border: `1.5px solid ${style.stroke}` }}
        >
          <BlueprintIcon name={node.icon} color={style.iconColor} />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h4 className="text-sm font-semibold text-rpmx-ink">{node.label}</h4>
            <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${badge.bg} ${badge.text}`}>
              {badge.label}
            </span>
          </div>
          <p className="text-xs text-rpmx-steel leading-relaxed">{node.description}</p>

          {/* Tools */}
          {node.tools && node.tools.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {node.tools.map(t => (
                <span
                  key={t}
                  className="text-[10px] font-mono bg-rpmx-canvas text-rpmx-steel px-2 py-0.5 rounded"
                >
                  {t}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
