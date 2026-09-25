import type { SimulationResult } from '../lib/types'
import { fmtNum, fmtPercent, pickByPrefix } from '../lib/format'
import { Card, CardHeader } from './ui/Card'
import { StatTile } from './ui/StatTile'
import { StatusBadge, StrategyBadge } from './ui/Badge'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

function ResourceUtilizationChart({ result }: { result: SimulationResult }) {
  const util = pickByPrefix(result, 'utilization_')
  const data = Object.entries(util).map(([resource, value]) => ({ resource, value }))
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16 }}>
        <CartesianGrid stroke="var(--color-border)" horizontal={false} />
        <XAxis type="number" domain={[0, 'dataMax']} tickFormatter={(v) => `${Math.round(v * 100)}%`} tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }} axisLine={false} tickLine={false} />
        <YAxis type="category" dataKey="resource" tick={{ fill: 'var(--color-text-muted)', fontSize: 12 }} axisLine={false} tickLine={false} width={64} />
        <Tooltip
          cursor={{ fill: 'var(--color-panel-raised)' }}
          contentStyle={{ background: 'var(--color-panel-raised)', border: '1px solid var(--color-border-strong)', borderRadius: 8, fontSize: 12.5 }}
          formatter={(v) => [fmtPercent(typeof v === 'number' ? v : Number(v)), 'Utilization']}
        />
        <Bar dataKey="value" radius={[0, 3, 3, 0]} maxBarSize={22}>
          {data.map((_, i) => (
            <Cell key={i} fill="var(--color-amber)" fillOpacity={0.85} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

export function ResultDetail({ result }: { result: SimulationResult }) {
  const overhead = pickByPrefix(result, 'overhead_')
  const wasted = pickByPrefix(result, 'wasted_')
  const totalWasted = Object.values(wasted).reduce((a, b) => a + b, 0)

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-center gap-2">
        <StrategyBadge strategy={result.strategy} />
        <span className="text-[12px] text-(--color-text-muted)">
          {result.condition} &middot; seed {result.seed}
        </span>
        <StatusBadge status={result.status} />
      </div>

      <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Ticks elapsed" value={fmtNum(result.ticks_elapsed, 0)} />
        <StatTile label="Throughput" value={fmtNum(result.throughput)} suffix="work/tick" />
        <StatTile label="Total useful work" value={fmtNum(result.total_useful_work, 0)} />
        <StatTile label="Overall utilization" value={fmtPercent(result.overall_utilization)} />
        <StatTile label="Avg waiting time" value={fmtNum(result.avg_waiting_time)} suffix="ticks" />
        <StatTile label="Blocked processes" value={fmtNum(result.blocked_processes, 0)} suffix="/ 20" />
        <StatTile label="Unnecessary denials" value={fmtNum(result.unnecessary_denials, 0)} />
        <StatTile
          label="Deadlock episodes"
          value={fmtNum(result.deadlock_episodes, 0)}
          color={result.deadlock_episodes > 0 ? 'var(--color-recovery)' : undefined}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Resource utilization" subtitle="Share of capacity-time each resource was actually held" />
          <ResourceUtilizationChart result={result} />
        </Card>

        <Card>
          <CardHeader title="Recovery & overhead" subtitle="Cost of the strategy's own bookkeeping" />
          <div className="space-y-2 text-[13px]">
            <div className="flex justify-between border-b border-(--color-border) pb-2">
              <span className="text-(--color-text-muted)">Recovery actions</span>
              <span className="font-mono">{result.recovery_actions}</span>
            </div>
            <div className="flex justify-between border-b border-(--color-border) pb-2">
              <span className="text-(--color-text-muted)">Distinct processes restarted</span>
              <span className="font-mono">{result.distinct_restarted_processes}</span>
            </div>
            <div className="flex justify-between border-b border-(--color-border) pb-2">
              <span className="text-(--color-text-muted)">Useful work lost</span>
              <span className="font-mono">{result.useful_work_lost}</span>
            </div>
            <div className="flex justify-between border-b border-(--color-border) pb-2">
              <span className="text-(--color-text-muted)">Resources wasted</span>
              <span className="font-mono">{fmtNum(totalWasted)}</span>
            </div>
            <div className="pt-1 text-[11.5px] font-medium uppercase tracking-wide text-(--color-text-faint)">
              Algorithm overhead
            </div>
            {Object.entries(overhead).map(([key, value]) => (
              <div key={key} className="flex justify-between text-[12.5px]">
                <span className="text-(--color-text-muted)">{key.replace(/_/g, ' ')}</span>
                <span className="font-mono">{value}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  )
}
