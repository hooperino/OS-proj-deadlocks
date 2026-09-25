import type { StrategyId } from '../../lib/types'
import { STRATEGY_META } from '../../lib/format'

export function StrategyBadge({ strategy, size = 'md' }: { strategy: StrategyId; size?: 'sm' | 'md' }) {
  const meta = STRATEGY_META[strategy]
  return (
    <span
      className={
        size === 'sm'
          ? 'inline-flex items-center gap-1.5 rounded px-1.5 py-0.5 text-[11px] font-medium'
          : 'inline-flex items-center gap-2 rounded-md px-2.5 py-1 text-[13px] font-medium'
      }
      style={{ background: meta.soft, color: meta.color }}
    >
      <span
        className="inline-block shrink-0 rounded-full"
        style={{ width: size === 'sm' ? 6 : 7, height: size === 'sm' ? 6 : 7, background: meta.color }}
      />
      {meta.short}
    </span>
  )
}

export function ConditionBadge({ condition }: { condition: 'light' | 'heavy' }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded px-1.5 py-0.5 text-[11px] font-medium text-(--color-text-muted) ring-1 ring-inset ring-(--color-border-strong)">
      {condition === 'light' ? 'Light' : 'Heavy'}
    </span>
  )
}

export function StatusBadge({ status }: { status: string }) {
  const ok = status === 'COMPLETE'
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded px-1.5 py-0.5 text-[11px] font-medium"
      style={{
        color: ok ? 'var(--color-good)' : 'var(--color-bad)',
        background: ok ? 'var(--color-avoidance-soft)' : 'var(--color-recovery-soft)',
      }}
    >
      {status}
    </span>
  )
}
