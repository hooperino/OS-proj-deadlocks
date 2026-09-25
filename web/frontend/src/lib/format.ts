import type { StrategyId } from './types'

export const STRATEGY_META: Record<StrategyId, { label: string; short: string; color: string; soft: string }> = {
  prevention: { label: 'Prevention', short: 'Prevention', color: 'var(--color-prevention)', soft: 'var(--color-prevention-soft)' },
  avoidance: { label: 'Avoidance (Banker)', short: 'Avoidance', color: 'var(--color-avoidance)', soft: 'var(--color-avoidance-soft)' },
  detection_recovery: { label: 'Detection + Recovery', short: 'Detection+Recovery', color: 'var(--color-recovery)', soft: 'var(--color-recovery-soft)' },
}

export const STRATEGY_ORDER: StrategyId[] = ['prevention', 'avoidance', 'detection_recovery']

export function fmtNum(value: unknown, digits = 2): string {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—'
  if (Number.isInteger(value)) return value.toLocaleString()
  return value.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

export function fmtPercent(value: unknown, digits = 1): string {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—'
  return `${(value * 100).toFixed(digits)}%`
}

export function fmtTicks(value: unknown): string {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—'
  return `${value.toLocaleString()} ticks`
}

/** Picks every key on `obj` starting with `prefix`, stripped of that
 * prefix, dropping null/undefined (a strategy-irrelevant column). Used for
 * the dynamic utilization_, wasted_, and overhead_ prefixed fields. */
export function pickByPrefix(obj: Record<string, unknown>, prefix: string): Record<string, number> {
  const out: Record<string, number> = {}
  for (const [key, value] of Object.entries(obj)) {
    if (key.startsWith(prefix) && typeof value === 'number') {
      out[key.slice(prefix.length)] = value
    }
  }
  return out
}

export function titleCase(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1)
}

export function formatTimestamp(iso: string | null): string {
  if (!iso) return 'unknown time'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}
