import { useState } from 'react'
import { useExperiment, useExperimentList } from '../lib/hooks'
import { Card, CardHeader } from '../components/ui/Card'
import { EmptyState, ErrorState, Spinner } from '../components/ui/Feedback'
import { GroupedBarChart } from '../components/charts/GroupedBarChart'
import { CostProfileRadar } from '../components/charts/CostProfileRadar'
import { ExperimentPicker } from '../components/ExperimentPicker'
import { StrategyBadge } from '../components/ui/Badge'
import { STRATEGY_ORDER } from '../lib/format'

const METRIC_CHARTS: { key: string; title: string; subtitle: string; unit?: string }[] = [
  { key: 'throughput', title: 'Throughput', subtitle: 'Useful work completed per simulated tick' },
  { key: 'avg_waiting_time', title: 'Average waiting time', subtitle: 'Ticks spent WAITING, per request that actually waited', unit: 'ticks' },
  { key: 'unnecessary_denials', title: 'Unnecessary denials', subtitle: 'WAITs caused by policy despite the resource being available' },
  { key: 'deadlock_episodes', title: 'Deadlock episodes', subtitle: 'No-deadlock \u2192 deadlock transitions caught by periodic detection' },
  { key: 'recovery_actions', title: 'Recovery actions', subtitle: 'Victim terminations performed to break a deadlock' },
  { key: 'useful_work_lost', title: 'Useful work lost', subtitle: 'Work discarded by every recovery termination, accumulated' },
  { key: 'blocked_processes', title: 'Blocked processes', subtitle: 'Distinct processes that entered WAITING at least once' },
  { key: 'overall_utilization', title: 'Resource utilization', subtitle: 'Share of total resource-capacity-time actually in use' },
]

export function Compare() {
  const { data: experiments, loading: listLoading } = useExperimentList()
  const [selected, setSelected] = useState<string | null>(null)
  const experimentId = selected ?? (experiments && experiments[0]?.id) ?? null
  const { data: detail, loading, error } = useExperiment(experimentId)

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-[22px] font-semibold tracking-tight">Compare strategies</h1>
          <p className="mt-1 text-[13.5px] text-(--color-text-muted)">
            Every chart below is grouped by condition (Light / Heavy) with one bar per strategy, computed
            from the same 30 seeds run under all three strategies from fresh state.
          </p>
        </div>
        {experiments && experiments.length > 0 && (
          <ExperimentPicker experiments={experiments} value={experimentId} onChange={setSelected} />
        )}
      </div>

      {listLoading || loading ? (
        <Spinner label="Loading experiment data\u2026" />
      ) : error ? (
        <ErrorState message={error} />
      ) : !detail ? (
        <EmptyState
          title="No experiment results yet"
          description="Run the full experiment first, then come back here to compare the three strategies."
        />
      ) : (
        <>
          <div className="mb-4 flex flex-wrap gap-2">
            {STRATEGY_ORDER.map((s) => (
              <StrategyBadge key={s} strategy={s} />
            ))}
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {METRIC_CHARTS.map((m) => (
              <Card key={m.key}>
                <CardHeader title={m.title} subtitle={m.subtitle} />
                <GroupedBarChart summary={detail.summary} metricKey={m.key} unit={m.unit} />
              </Card>
            ))}
          </div>

          <h2 className="mb-4 mt-10 text-[15px] font-semibold">Cost profile</h2>
          <p className="mb-4 -mt-2 max-w-2xl text-[13px] text-(--color-text-muted)">
            Each axis is normalized against the costliest strategy on that dimension, within one condition
            &mdash; a smaller enclosed shape means a cheaper strategy overall; the shape itself shows{' '}
            <em>where</em> a strategy pays.
          </p>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Card>
              <CardHeader title="Light contention" />
              <CostProfileRadar summary={detail.summary} condition="light" />
            </Card>
            <Card>
              <CardHeader title="Heavy contention" />
              <CostProfileRadar summary={detail.summary} condition="heavy" />
            </Card>
          </div>
        </>
      )}
    </div>
  )
}
