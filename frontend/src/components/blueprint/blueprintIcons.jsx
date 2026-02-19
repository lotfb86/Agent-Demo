// Small SVG icons for blueprint node types (20x20 viewBox)
const I = ({ d, color = 'currentColor' }) => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={color}
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    {typeof d === 'string' ? <path d={d} /> : d}
  </svg>
)

export const icons = {
  inbox: (c) => <I color={c} d={<>
    <polyline points="22 12 16 12 14 15 10 15 8 12 2 12" />
    <path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z" />
  </>} />,

  scan: (c) => <I color={c} d={<>
    <path d="M3 7V5a2 2 0 0 1 2-2h2" /><path d="M17 3h2a2 2 0 0 1 2 2v2" />
    <path d="M21 17v2a2 2 0 0 1-2 2h-2" /><path d="M7 21H5a2 2 0 0 1-2-2v-2" />
    <line x1="7" y1="12" x2="17" y2="12" />
  </>} />,

  brain: (c) => <I color={c} d={<>
    <path d="M12 2a4 4 0 0 1 4 4 4 4 0 0 1 2 3.46A4 4 0 0 1 16 16a4 4 0 0 1-4 4 4 4 0 0 1-4-4 4 4 0 0 1-2-6.54A4 4 0 0 1 8 6a4 4 0 0 1 4-4z" />
    <path d="M12 2v18" />
  </>} />,

  shield: (c) => <I color={c} d={<>
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
  </>} />,

  tag: (c) => <I color={c} d={<>
    <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z" />
    <line x1="7" y1="7" x2="7.01" y2="7" />
  </>} />,

  user: (c) => <I color={c} d={<>
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
    <circle cx="12" cy="7" r="4" />
  </>} />,

  database: (c) => <I color={c} d={<>
    <ellipse cx="12" cy="5" rx="9" ry="3" />
    <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
    <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
  </>} />,

  mail: (c) => <I color={c} d={<>
    <rect x="2" y="4" width="20" height="16" rx="2" />
    <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />
  </>} />,

  chart: (c) => <I color={c} d={<>
    <line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" />
    <line x1="6" y1="20" x2="6" y2="14" />
  </>} />,

  truck: (c) => <I color={c} d={<>
    <path d="M1 3h15v13H1z" /><path d="M16 8h4l3 5v5h-7V8z" />
    <circle cx="5.5" cy="18.5" r="2.5" /><circle cx="18.5" cy="18.5" r="2.5" />
  </>} />,

  clipboard: (c) => <I color={c} d={<>
    <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
    <rect x="8" y="2" width="8" height="4" rx="1" />
  </>} />,

  route: (c) => <I color={c} d={<>
    <circle cx="6" cy="19" r="3" /><path d="M9 19h8.5a3.5 3.5 0 0 0 0-7h-11a3.5 3.5 0 0 1 0-7H15" />
    <circle cx="18" cy="5" r="3" />
  </>} />,

  alert: (c) => <I color={c} d={<>
    <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
    <line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" />
  </>} />,

  clock: (c) => <I color={c} d={<>
    <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
  </>} />,

  building: (c) => <I color={c} d={<>
    <rect x="4" y="2" width="16" height="20" rx="2" />
    <path d="M9 22v-4h6v4" /><path d="M8 6h.01" /><path d="M16 6h.01" />
    <path d="M8 10h.01" /><path d="M16 10h.01" /><path d="M8 14h.01" /><path d="M16 14h.01" />
  </>} />,

  search: (c) => <I color={c} d={<>
    <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
  </>} />,

  check: (c) => <I color={c} d={<>
    <polyline points="20 6 9 17 4 12" />
  </>} />,

  split: (c) => <I color={c} d={<>
    <path d="M16 3h5v5" /><path d="M8 3H3v5" />
    <path d="m21 3-8.5 8.5" /><path d="M3 3l8.5 8.5" />
    <path d="M12 12v9" />
  </>} />,

  layers: (c) => <I color={c} d={<>
    <polygon points="12 2 2 7 12 12 22 7 12 2" />
    <polyline points="2 17 12 22 22 17" />
    <polyline points="2 12 12 17 22 12" />
  </>} />,

  wrench: (c) => <I color={c} d={<>
    <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
  </>} />,

  dollar: (c) => <I color={c} d={<>
    <line x1="12" y1="1" x2="12" y2="23" />
    <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
  </>} />,

  users: (c) => <I color={c} d={<>
    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
    <circle cx="9" cy="7" r="4" />
    <path d="M23 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" />
  </>} />,

  target: (c) => <I color={c} d={<>
    <circle cx="12" cy="12" r="10" /><circle cx="12" cy="12" r="6" />
    <circle cx="12" cy="12" r="2" />
  </>} />,
}

export function BlueprintIcon({ name, color }) {
  const render = icons[name]
  if (!render) return null
  return render(color)
}
