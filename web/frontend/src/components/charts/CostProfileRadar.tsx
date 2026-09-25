import {
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from 'recharts'
import type { SummaryRow } from '../../lib/types'
import { STRATEGY_META, STRATEGY_ORDER } from '../../lib/format'
import type { Condition } from '../../lib/types'

const COST_METRICS: { key: string; label: string }[] = [
  { key: 'avg_waiting_time', label: 'Waiting time' },
  { key: 'unnecessary_denials', label: 'Unnecessary denials' },
  { key: 'deadlock_episodes', label: 'Deadlock episodes' },
  { key: 'useful_work_lost', label: 'Work lost' },
  { key: 'total_resources_wasted', label: 'Resources wasted' },
]

/** Normalizes each cost metric to 0-1 *within this condition's three
 * strategies* (1 = whichever strategy costs the most on that dimension),
 * so the radar shows relative cost shape, not absolute units that would
 * otherwise be incomparable on one axis. A strategy with a small enclosed
 * area is cheaper across the board; the shape shows *where* it pays. */
export function CostProfileRadar({ summary, condition }: { summary: SummaryRow[]; condition: Condition }) {
  const rows = summary.filter((r) => r.condition === condition)

  const data = COST_METRICS.map(({ key, label }) => {
    const raw = Object.fromEntries(
      STRATEGY_ORDER.map((s) => [s, (rows.find((r) => r.strategy === s)?.[`${key}_mean`] as number) ?? 0]),
    )
    const max = Math.max(...Object.values(raw), 1e-9)
    const point: Record<string, unknown> = { metric: label }
    for (const s of STRATEGY_ORDER) point[s] = max > 0 ? raw[s] / max : 0
    return point
  })

  return (
    <ResponsiveContainer width="100%" height={320}>
      <RadarChart data={data} outerRadius="72%">
        <PolarGrid stroke="var(--color-border)" />
        <PolarAngleAxis dataKey="metric" tick={{ fill: 'var(--color-text-muted)', fontSize: 11.5 }} />
        <Tooltip
          contentStyle={{
            background: 'var(--color-panel-raised)',
            border: '1px solid var(--color-border-strong)',
            borderRadius: 8,
            fontSize: 12.5,
          }}
          labelStyle={{ color: 'var(--color-text)' }}
          formatter={(value, name) => [
            `${Math.round((typeof value === 'number' ? value : Number(value)) * 100)}% of worst`,
            STRATEGY_META[name as keyof typeof STRATEGY_META]?.short ?? String(name),
          ]}
        />
        {STRATEGY_ORDER.map((s) => (
          <Radar
            key={s}
            dataKey={s}
            name={s}
            stroke={STRATEGY_META[s].color}
            fill={STRATEGY_META[s].color}
            fillOpacity={0.12}
            strokeWidth={1.8}
          />
        ))}
      </RadarChart>
    </ResponsiveContainer>
  )
}
