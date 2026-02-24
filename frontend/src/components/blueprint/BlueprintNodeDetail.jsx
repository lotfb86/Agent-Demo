import { NODE_STYLES } from './blueprintConstants'
import { BlueprintIcon } from './blueprintIcons'

const TYPE_BADGES = {
  source:      { label: 'Data Source',  cls: 'badge badge-slate' },
  process:     { label: 'Process Step', cls: 'badge badge-slate' },
  ai_decision: { label: 'AI Decision',  cls: 'badge badge-blue'  },
  human:       { label: 'Human Review', cls: 'badge badge-amber' },
  output:      { label: 'Output',       cls: 'badge badge-green' },
}

export default function BlueprintNodeDetail({ node }) {
  if (!node) return null

  const badge = TYPE_BADGES[node.type] || TYPE_BADGES.process
  const style = NODE_STYLES[node.type] || NODE_STYLES.process

  return (
    <div className="card p-4 mt-3 animate-fade-in">
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
            <span className={badge.cls}>
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
