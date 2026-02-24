// Card component for consistent container styling
export function Card({ 
  children, 
  hover = true, 
  padding = true,
  className = '',
  ...props 
}) {
  const baseClasses = 'bg-white border border-rpmx-wash rounded-lg shadow-soft'
  const hoverClasses = hover ? 'hover:shadow-hover hover:-translate-y-px transition-all duration-200' : ''
  const paddingClasses = padding ? 'p-4 sm:p-6' : ''

  return (
    <div className={`${baseClasses} ${hoverClasses} ${paddingClasses} ${className}`} {...props}>
      {children}
    </div>
  )
}