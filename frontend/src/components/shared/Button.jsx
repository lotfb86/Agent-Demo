// Button component library with variants
export function Button({ 
  children, 
  variant = 'primary', 
  size = 'md',
  icon: Icon,
  iconPosition = 'left',
  disabled = false, 
  className = '',
  ...props 
}) {
  const baseClasses = 'font-semibold transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2'
  
  const variantClasses = {
    primary: 'bg-rpmx-signal text-white hover:brightness-110 focus:ring-rpmx-signal/40 disabled:opacity-60',
    secondary: 'bg-white border border-rpmx-wash text-rpmx-ink hover:bg-rpmx-deep focus:ring-blue-300 disabled:opacity-60',
    tertiary: 'text-rpmx-signal bg-transparent hover:bg-blue-50 focus:ring-blue-300 disabled:opacity-60',
    danger: 'bg-rpmx-danger text-white hover:brightness-110 focus:ring-rpmx-danger/40 disabled:opacity-60',
  }

  const sizeClasses = {
    sm: 'px-3 py-1.5 text-xs rounded-md',
    md: 'px-4 py-2.5 text-sm rounded-lg',
    lg: 'px-6 py-3 text-base rounded-lg',
    icon: 'p-2 rounded-lg',
  }

  return (
    <button 
      className={`${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
      disabled={disabled}
      {...props}
    >
      <div className="flex items-center justify-center gap-2">
        {Icon && iconPosition === 'left' && <Icon className="w-4 h-4" />}
        {children && <span>{children}</span>}
        {Icon && iconPosition === 'right' && <Icon className="w-4 h-4" />}
      </div>
    </button>
  )
}

export function IconButton({ children, icon: Icon, disabled = false, className = '', ...props }) {
  return (
    <button 
      className={`w-8 h-8 flex items-center justify-center rounded-lg text-rpmx-steel hover:bg-rpmx-deep transition-all duration-200 disabled:opacity-60 ${className}`}
      disabled={disabled}
      {...props}
    >
      {Icon ? <Icon className="w-5 h-5" /> : children}
    </button>
  )
}