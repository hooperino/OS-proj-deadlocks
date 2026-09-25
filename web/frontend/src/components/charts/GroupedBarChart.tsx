import {
  Bar,
  BarChart,
  CartesianGrid,
  ErrorBar,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { SummaryRow } from '../../lib/types'
import { STRATEGY_META, STRATEGY_ORDER, fmtNum } from '../../lib/format'

interface Props {
  summary: SummaryRow[]
  metricKey: string
  unit?: string
  height?: number
  showErrorBars?: boolean
}

export function GroupedBarChart({ summary, metricKey, unit, height = 300, showErrorBars = true }: Props) {
  const data = (['light', 'heavy'] as const).map((condition) => {
    const row: Record<string, unknown> = { condition: condition === 'light' ? 'Light' : 'Heavy' }
    for (const strategy of STRATEGY_ORDER) {
      const source = summary.find((r) => r.condition === condition && r.strategy === strategy)
      const mean = (source?.[`${metricKey}_mean`] as number | undefined) ?? 0
      const std = (source?.[`${metricKey}_std`] as number | undefined) ?? 0
      row[strategy] = mean
      row[`${strategy}_range`] = [std, std]
    }
    return row
  })

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }} barGap={4}>
        <CartesianGrid stroke="var(--color-border)" vertical={false} />
        <XAxis
          dataKey="condition"
          tick={{ fill: 'var(--color-text-muted)', fontSize: 12.5 }}
          axisLine={{ stroke: 'var(--color-border-strong)' }}
          tickLine={false}
        />
        <YAxis
          tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          width={44}
        />
        <Tooltip
          cursor={{ fill: 'var(--color-panel-raised)' }}
          contentStyle={{
            background: 'var(--color-panel-raised)',
            border: '1px solid var(--color-border-strong)',
            borderRadius: 8,
            fontSize: 12.5,
          }}
          labelStyle={{ color: 'var(--color-text)', marginBottom: 4 }}
          formatter={(value, name) => [
            `${fmtNum(typeof value === 'number' ? value : Number(value))}${unit ? ` ${unit}` : ''}`,
            STRATEGY_META[name as keyof typeof STRATEGY_META]?.short ?? String(name),
          ]}
        />
        <Legend
          formatter={(value: string) => (
            <span style={{ color: 'var(--color-text-muted)', fontSize: 12.5 }}>
              {STRATEGY_META[value as keyof typeof STRATEGY_META]?.short ?? value}
            </span>
          )}
          wrapperStyle={{ paddingTop: 10 }}
        />
        {STRATEGY_ORDER.map((strategy) => (
          <Bar key={strategy} dataKey={strategy} name={strategy} fill={STRATEGY_META[strategy].color} radius={[3, 3, 0, 0]} maxBarSize={64}>
            {showErrorBars && (
              <ErrorBar dataKey={`${strategy}_range`} width={4} strokeWidth={1.4} stroke="var(--color-text-faint)" direction="y" />
            )}
          </Bar>
        ))}
      </BarChart>
    </ResponsiveContainer>
  )
}
