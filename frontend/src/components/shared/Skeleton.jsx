// Skeleton loader component for loading states
export function Skeleton({ width = 'w-full', height = 'h-4', className = '', count = 1 }) {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <div 
          key={i}
          className={`skeleton ${width} ${height} ${className} ${i > 0 ? 'mt-3' : ''}`}
        />
      ))}
    </>
  )
}

export function SkeletonCard() {
  return (
    <div className="card p-4 space-y-4">
      <div className="flex items-start justify-between gap-3">
        <Skeleton width="w-32" height="h-5" />
        <Skeleton width="w-16" height="h-4" />
      </div>
      <Skeleton width="w-24" height="h-3" />
      <Skeleton height="h-12" />
      <div className="pt-2 border-t border-rpmx-wash">
        <Skeleton width="w-20" height="h-3" />
      </div>
    </div>
  )
}

export function SkeletonGrid({ count = 3 }) {
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonCard key={i} />
      ))}
    </div>
  )
}