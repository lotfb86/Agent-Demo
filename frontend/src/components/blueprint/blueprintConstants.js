// Grid & layout constants for the Blueprint renderer
export const GRID = {
  cellW: 200,      // horizontal spacing between node centers
  cellH: 140,      // vertical spacing between node centers
  padX: 80,        // left/right padding inside the SVG
  padY: 60,        // top/bottom padding inside the SVG
}

export const NODE = {
  w: 156,          // default node width
  h: 64,           // default node height
  rx: 12,          // border radius
  iconSize: 20,    // icon dimensions inside node
}

// Node type → visual config
export const NODE_STYLES = {
  source: {
    fill: '#f6f8fb',       // rpmx-canvas
    stroke: '#c8d0d8',     // rpmx-slate
    strokeDash: '6 4',
    strokeWidth: 1.5,
    iconColor: '#5d6b79',  // rpmx-steel
    label: 'Data Source',
  },
  process: {
    fill: '#ffffff',       // rpmx-panel
    stroke: '#c8d0d8',     // rpmx-slate
    strokeDash: null,
    strokeWidth: 1.5,
    iconColor: '#1f2a36',  // rpmx-ink
    label: 'Process',
  },
  ai_decision: {
    fill: 'url(#aiGradient)',
    stroke: '#ff6f3c',     // rpmx-signal
    strokeDash: null,
    strokeWidth: 2.5,
    iconColor: '#ff6f3c',  // rpmx-signal
    label: 'AI Decision',
  },
  human: {
    fill: '#fef9f3',       // light amber tint
    stroke: '#f2a65a',     // rpmx-amber
    strokeDash: '6 4',
    strokeWidth: 2,
    iconColor: '#f2a65a',  // rpmx-amber
    label: 'Human Review',
  },
  output: {
    fill: '#f0faf5',       // light mint tint
    stroke: '#2bb673',     // rpmx-mint
    strokeDash: null,
    strokeWidth: 2,
    iconColor: '#2bb673',  // rpmx-mint
    label: 'Output',
  },
}

// Edge style presets
export const EDGE_STYLES = {
  normal: { stroke: '#c8d0d8', strokeWidth: 1.5, dash: null },
  exception: { stroke: '#f2a65a', strokeWidth: 1.5, dash: '6 4' },
  error: { stroke: '#d64545', strokeWidth: 1.5, dash: '4 3' },
}
