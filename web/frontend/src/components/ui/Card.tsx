import clsx from 'clsx'

export function Card({
  children,
  className,
  accent,
}: {
  children: React.ReactNode
  className?: string
  accent?: string
}) {
  return (
    <div
      className={clsx(
        'rounded-lg border border-(--color-border) bg-(--color-panel) p-5',
        className,
      )}
      style={accent ? { borderLeft: `2.5px solid ${accent}` } : undefined}
    >
      {children}
    </div>
  )
}

export function CardHeader({
  title,
  subtitle,
  action,
}: {
  title: string
  subtitle?: string
  action?: React.ReactNode
}) {
  return (
    <div className="mb-4 flex items-start justify-between gap-4">
      <div>
        <h3 className="text-[14px] font-semibold text-(--color-text)">{title}</h3>
        {subtitle && <p className="mt-0.5 text-[12.5px] text-(--color-text-muted)">{subtitle}</p>}
      </div>
      {action}
    </div>
  )
}
