import { useMemo } from 'react'
import { GRID, NODE, NODE_STYLES, EDGE_STYLES } from './blueprintConstants'
import { BlueprintIcon } from './blueprintIcons'

/* ── helpers ── */

function pos(col, row) {
  return {
    x: GRID.padX + col * GRID.cellW + GRID.cellW / 2,
    y: GRID.padY + row * GRID.cellH + GRID.cellH / 2,
  }
}

function edgePath(fromNode, toNode, nodes) {
  const a = pos(fromNode.col, fromNode.row)
  const b = pos(toNode.col, toNode.row)

  const hw = NODE.w / 2
  const hh = NODE.h / 2

  // Start from right edge of source, end at left edge of target
  let sx = a.x + hw + 4
  let sy = a.y
  let ex = b.x - hw - 4
  let ey = b.y

  // If target is directly below/above, use bottom/top edges
  if (fromNode.col === toNode.col) {
    sx = a.x
    ex = b.x
    if (toNode.row > fromNode.row) {
      sy = a.y + hh + 4
      ey = b.y - hh - 4
    } else {
      sy = a.y - hh - 4
      ey = b.y + hh + 4
    }
  }

  // Bezier control points for smooth curves
  const dx = (ex - sx) * 0.4
  const dy = (ey - sy) * 0.15
  return `M${sx},${sy} C${sx + dx},${sy + dy} ${ex - dx},${ey - dy} ${ex},${ey}`
}

/* ── SVG definitions ── */

function SvgDefs() {
  return (
    <defs>
      {/* Blueprint grid pattern */}
      <pattern id="bpGrid" width="20" height="20" patternUnits="userSpaceOnUse">
        <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#e8ecf1" strokeWidth="0.5" />
      </pattern>
      <pattern id="bpGridLg" width="100" height="100" patternUnits="userSpaceOnUse">
        <rect width="100" height="100" fill="url(#bpGrid)" />
        <path d="M 100 0 L 0 0 0 100" fill="none" stroke="#dde2e8" strokeWidth="0.8" />
      </pattern>

      {/* AI node gradient */}
      <linearGradient id="aiGradient" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stopColor="#ff6f3c" stopOpacity="0.07" />
        <stop offset="100%" stopColor="#f2a65a" stopOpacity="0.07" />
      </linearGradient>

      {/* Arrow markers */}
      <marker id="arrowNormal" viewBox="0 0 10 7" refX="9" refY="3.5"
        markerWidth="8" markerHeight="6" orient="auto-start-reverse">
        <path d="M 0 0 L 10 3.5 L 0 7 z" fill="#c8d0d8" />
      </marker>
      <marker id="arrowException" viewBox="0 0 10 7" refX="9" refY="3.5"
        markerWidth="8" markerHeight="6" orient="auto-start-reverse">
        <path d="M 0 0 L 10 3.5 L 0 7 z" fill="#f2a65a" />
      </marker>
      <marker id="arrowError" viewBox="0 0 10 7" refX="9" refY="3.5"
        markerWidth="8" markerHeight="6" orient="auto-start-reverse">
        <path d="M 0 0 L 10 3.5 L 0 7 z" fill="#d64545" />
      </marker>
    </defs>
  )
}

/* ── Edge component ── */

function Edge({ edge, nodesMap }) {
  const from = nodesMap[edge.from]
  const to = nodesMap[edge.to]
  if (!from || !to) return null

  const preset = EDGE_STYLES[edge.style] || EDGE_STYLES.normal
  const markerId = edge.style === 'error' ? 'arrowError'
    : edge.style === 'exception' ? 'arrowException'
    : 'arrowNormal'

  const d = edgePath(from, to, nodesMap)

  // Label midpoint
  const a = pos(from.col, from.row)
  const b = pos(to.col, to.row)
  const mx = (a.x + b.x) / 2
  const my = (a.y + b.y) / 2

  return (
    <g>
      <path
        d={d}
        fill="none"
        stroke={preset.stroke}
        strokeWidth={preset.strokeWidth}
        strokeDasharray={preset.dash || undefined}
        markerEnd={`url(#${markerId})`}
      />
      {edge.label && (
        <g transform={`translate(${mx}, ${my})`}>
          <rect
            x={-edge.label.length * 3.5 - 6}
            y={-9}
            width={edge.label.length * 7 + 12}
            height={18}
            rx={4}
            fill="white"
            stroke="#e8ecf1"
            strokeWidth="0.8"
          />
          <text
            textAnchor="middle"
            dominantBaseline="central"
            fill="#5d6b79"
            fontSize="10"
            fontFamily='"Space Grotesk", system-ui, sans-serif'
          >
            {edge.label}
          </text>
        </g>
      )}
    </g>
  )
}

/* ── Node component ── */

function NodeBox({ node, isSelected, onClick }) {
  const style = NODE_STYLES[node.type] || NODE_STYLES.process
  const { x, y } = pos(node.col, node.row)
  const hw = NODE.w / 2
  const hh = NODE.h / 2

  return (
    <g
      onClick={() => onClick(node.id)}
      style={{ cursor: 'pointer' }}
      className="blueprint-node"
    >
      {/* Glow ring on selected */}
      {isSelected && (
        <rect
          x={x - hw - 5} y={y - hh - 5}
          width={NODE.w + 10} height={NODE.h + 10}
          rx={NODE.rx + 3}
          fill="none"
          stroke="#ff6f3c"
          strokeWidth="2"
          opacity="0.5"
        >
          <animate attributeName="opacity" values="0.3;0.7;0.3" dur="2s" repeatCount="indefinite" />
        </rect>
      )}

      {/* Shadow */}
      <rect
        x={x - hw + 2} y={y - hh + 3}
        width={NODE.w} height={NODE.h}
        rx={NODE.rx}
        fill="rgba(0,0,0,0.04)"
      />

      {/* Main body */}
      <rect
        x={x - hw} y={y - hh}
        width={NODE.w} height={NODE.h}
        rx={NODE.rx}
        fill={style.fill}
        stroke={isSelected ? '#ff6f3c' : style.stroke}
        strokeWidth={isSelected ? 2.5 : style.strokeWidth}
        strokeDasharray={style.strokeDash || undefined}
      />

      {/* Icon */}
      <foreignObject x={x - hw + 12} y={y - 10} width={NODE.iconSize} height={NODE.iconSize}>
        <BlueprintIcon name={node.icon} color={style.iconColor} />
      </foreignObject>

      {/* Label */}
      <text
        x={x - hw + 40}
        y={y}
        dominantBaseline="central"
        fill="#1f2a36"
        fontSize="12"
        fontWeight="600"
        fontFamily='"Space Grotesk", system-ui, sans-serif'
      >
        {node.label}
      </text>

      {/* Type badge for AI nodes */}
      {node.type === 'ai_decision' && (
        <g>
          <rect
            x={x + hw - 28} y={y - hh - 8}
            width={24} height={16}
            rx={8}
            fill="#ff6f3c"
          />
          <text
            x={x + hw - 16} y={y - hh}
            textAnchor="middle"
            dominantBaseline="central"
            fill="white"
            fontSize="8"
            fontWeight="700"
            fontFamily='"Space Grotesk", system-ui, sans-serif'
          >
            AI
          </text>
        </g>
      )}

      {/* Type badge for Human nodes */}
      {node.type === 'human' && (
        <g>
          <rect
            x={x + hw - 50} y={y - hh - 8}
            width={46} height={16}
            rx={8}
            fill="#f2a65a"
          />
          <text
            x={x + hw - 27} y={y - hh}
            textAnchor="middle"
            dominantBaseline="central"
            fill="white"
            fontSize="8"
            fontWeight="700"
            fontFamily='"Space Grotesk", system-ui, sans-serif'
          >
            HUMAN
          </text>
        </g>
      )}

      {/* Hover effect - invisible larger hitbox */}
      <rect
        x={x - hw - 4} y={y - hh - 4}
        width={NODE.w + 8} height={NODE.h + 8}
        rx={NODE.rx + 2}
        fill="transparent"
      />
    </g>
  )
}

/* ── Loop indicator ── */

function LoopIndicator({ loop, nodesMap }) {
  if (!loop) return null
  const start = nodesMap[loop.startNode]
  const end = nodesMap[loop.endNode]
  if (!start || !end) return null

  const sp = pos(start.col, start.row)
  const ep = pos(end.col, end.row)
  const top = Math.min(sp.y, ep.y) - NODE.h / 2 - 28
  const left = sp.x - NODE.w / 2 - 8
  const right = ep.x + NODE.w / 2 + 8
  const mid = (left + right) / 2

  return (
    <g>
      <path
        d={`M${left},${top + 12} L${left},${top} L${right},${top} L${right},${top + 12}`}
        fill="none"
        stroke="#c8d0d8"
        strokeWidth="1.2"
        strokeDasharray="4 3"
      />
      <rect
        x={mid - loop.label.length * 3.2 - 8}
        y={top - 8}
        width={loop.label.length * 6.4 + 16}
        height={16}
        rx={4}
        fill="#f6f8fb"
        stroke="#c8d0d8"
        strokeWidth="0.8"
      />
      <text
        x={mid}
        y={top}
        textAnchor="middle"
        dominantBaseline="central"
        fill="#5d6b79"
        fontSize="10"
        fontStyle="italic"
        fontFamily='"Space Grotesk", system-ui, sans-serif'
      >
        {loop.label}
      </text>
    </g>
  )
}

/* ── Main renderer ── */

export default function BlueprintRenderer({ config, selectedNodeId, onNodeClick }) {
  const nodesMap = useMemo(() => {
    const m = {}
    config.nodes.forEach(n => { m[n.id] = n })
    return m
  }, [config.nodes])

  // Calculate SVG dimensions from node positions
  const maxCol = Math.max(...config.nodes.map(n => n.col))
  const maxRow = Math.max(...config.nodes.map(n => n.row))
  const svgW = GRID.padX * 2 + (maxCol + 1) * GRID.cellW
  const svgH = GRID.padY * 2 + (maxRow + 1) * GRID.cellH

  return (
    <svg
      viewBox={`0 0 ${svgW} ${svgH}`}
      width="100%"
      style={{ maxHeight: '460px' }}
      className="animate-fade-in"
    >
      <SvgDefs />

      {/* Grid background */}
      <rect width={svgW} height={svgH} fill="url(#bpGridLg)" rx="8" />

      {/* Edges (drawn first, behind nodes) */}
      {config.edges.map((e, i) => (
        <Edge key={i} edge={e} nodesMap={nodesMap} />
      ))}

      {/* Loop indicator */}
      <LoopIndicator loop={config.loop} nodesMap={nodesMap} />

      {/* Nodes */}
      {config.nodes.map(n => (
        <NodeBox
          key={n.id}
          node={n}
          isSelected={selectedNodeId === n.id}
          onClick={onNodeClick}
        />
      ))}
    </svg>
  )
}
