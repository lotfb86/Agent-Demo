// Badge component with semantic variants
export function Badge({ 
  children, 
  variant = 'slate', 
  icon: Icon,
  pulse = false,
  className = '',
  ...props 
}) {
  const variantClasses = {
    primary: 'bg-blue-100 text-blue-700',
    success: 'bg-green-100 text-green-700',
    warning: 'bg-amber-100 text-amber-700',
    danger: 'bg-red-100 text-red-700',
    slate: 'bg-slate-100 text-slate-600',
  }

  return (
    <span 
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold uppercase tracking-wide ${variantClasses[variant]} ${className}`}
      {...props}
    >
      {Icon && <Icon className={`w-3 h-3 ${pulse ? 'animate-pulse' : ''}`} />}
      {children}
    </span>
  )
}

export function StatusBadge({ status, label, pulse = false }) {
  const statusMap = {
    active: { variant: 'primary', icon: '●' },
    error: { variant: 'danger', icon: '●' },
    ready: { variant: 'slate', icon: '○' },
    review: { variant: 'warning', icon: '◐' },
  }

  const config = statusMap[status] || statusMap.ready

  return (
    <Badge variant={config.variant} pulse={pulse}>
      <span className="text-[10px] mr-0.5">{config.icon}</span>
      {label}
    </Badge>
  )
}