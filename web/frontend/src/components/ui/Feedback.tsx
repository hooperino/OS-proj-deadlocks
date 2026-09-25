import { AlertTriangle, Loader2 } from 'lucide-react'

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2.5 py-10 text-(--color-text-muted)">
      <Loader2 size={16} className="animate-spin" />
      <span className="text-[13px]">{label ?? 'Loading…'}</span>
    </div>
  )
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex items-start gap-2.5 rounded-lg border border-(--color-recovery-soft) bg-(--color-recovery-soft) p-4 text-[13px]" style={{ color: 'var(--color-recovery)' }}>
      <AlertTriangle size={16} className="mt-0.5 shrink-0" />
      <span>{message}</span>
    </div>
  )
}

export function EmptyState({ title, description, action }: { title: string; description: string; action?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-(--color-border-strong) px-6 py-16 text-center">
      <div className="text-[15px] font-medium text-(--color-text)">{title}</div>
      <div className="mt-1.5 max-w-sm text-[13px] text-(--color-text-muted)">{description}</div>
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}
