// Empty state component for when there's no content
export function EmptyState({ 
  icon: Icon, 
  title, 
  description,
  action,
  className = ''
}) {
  return (
    <div className={`flex flex-col items-center justify-center py-12 animate-fade-in ${className}`}>
      {Icon && (
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-white border border-rpmx-wash shadow-soft mb-4">
          <Icon className="h-6 w-6 text-rpmx-muted" />
        </div>
      )}
      {title && (
        <h3 className="text-sm font-semibold text-rpmx-ink mb-2">
          {title}
        </h3>
      )}
      {description && (
        <p className="text-xs text-rpmx-steel text-center max-w-xs leading-relaxed mb-6">
          {description}
        </p>
      )}
      {action && (
        <div className="flex gap-2">
          {action}
        </div>
      )}
    </div>
  )
}