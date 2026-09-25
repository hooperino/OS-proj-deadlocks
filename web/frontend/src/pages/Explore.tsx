import { useMemo, useState } from 'react'
import { ArrowDown, ArrowUp, ImageOff } from 'lucide-react'
import { useAggregate, useExperimentList } from '../lib/hooks'
import { api } from '../lib/api'
import type { AggregateRow, Condition, SimulationResult, StrategyId } from '../lib/types'
import { STRATEGY_META, fmtNum } from '../lib/format'
import { Card, CardHeader } from '../components/ui/Card'
import { EmptyState, ErrorState, Spinner } from '../components/ui/Feedback'
import { StatusBadge, StrategyBadge } from '../components/ui/Badge'
import { ExperimentPicker } from '../components/ExperimentPicker'
import { Modal } from '../components/Modal'
import { ResultDetail } from '../components/ResultDetail'

const PLOT_FILES = [
  'throughput.png',
  'avg_waiting_time.png',
  'resource_utilization.png',
  'blocked_processes.png',
  'deadlock_episodes.png',
  'recovery_cost.png',
  'useful_work_lost.png',
  'terminated_restarted_processes.png',
]

type SortKey = keyof AggregateRow
type SortDir = 'asc' | 'desc'

const COLUMNS: { key: SortKey; label: string; numeric?: boolean }[] = [
  { key: 'seed', label: 'Seed', numeric: true },
  { key: 'condition', label: 'Condition' },
  { key: 'strategy', label: 'Strategy' },
  { key: 'status', label: 'Status' },
  { key: 'throughput', label: 'Throughput', numeric: true },
  { key: 'avg_waiting_time', label: 'Avg wait', numeric: true },
  { key: 'deadlock_episodes', label: 'Deadlocks', numeric: true },
  { key: 'recovery_actions', label: 'Recoveries', numeric: true },
  { key: 'useful_work_lost', label: 'Work lost', numeric: true },
  { key: 'unnecessary_denials', label: 'Denials', numeric: true },
]

function PlotImage({ experimentId, filename }: { experimentId: string; filename: string }) {
  const [failed, setFailed] = useState(false)
  const title = filename.replace('.png', '').replace(/_/g, ' ')
  if (failed) {
    return (
      <div className="flex h-40 flex-col items-center justify-center gap-2 rounded-md border border-dashed border-(--color-border-strong) text-(--color-text-faint)">
        <ImageOff size={18} />
        <span className="text-[11.5px] capitalize">{title} unavailable</span>
      </div>
    )
  }
  return (
    <div>
      <img
        src={api.plotUrl(experimentId, filename)}
        alt={title}
        className="w-full rounded-md border border-(--color-border) bg-white"
        onError={() => setFailed(true)}
      />
      <div className="mt-1.5 text-center text-[11.5px] capitalize text-(--color-text-muted)">{title}</div>
    </div>
  )
}

export function Explore() {
  const { data: experiments, loading: listLoading } = useExperimentList()
  const [selected, setSelected] = useState<string | null>(null)
  const experimentId = selected ?? (experiments && experiments[0]?.id) ?? null
  const { data: rows, loading, error } = useAggregate(experimentId)

  const [conditionFilter, setConditionFilter] = useState<Condition | 'all'>('all')
  const [strategyFilter, setStrategyFilter] = useState<StrategyId | 'all'>('all')
  const [sortKey, setSortKey] = useState<SortKey>('seed')
  const [sortDir, setSortDir] = useState<SortDir>('asc')
  const [activeRun, setActiveRun] = useState<{ condition: Condition; seed: number; strategy: StrategyId } | null>(null)
  const [activeResult, setActiveResult] = useState<SimulationResult | null>(null)
  const [showPlots, setShowPlots] = useState(false)

  const filteredSorted = useMemo(() => {
    if (!rows) return []
    let out = rows
    if (conditionFilter !== 'all') out = out.filter((r) => r.condition === conditionFilter)
    if (strategyFilter !== 'all') out = out.filter((r) => r.strategy === strategyFilter)
    out = [...out].sort((a, b) => {
      const av = a[sortKey]
      const bv = b[sortKey]
      const cmp = typeof av === 'number' && typeof bv === 'number' ? av - bv : String(av).localeCompare(String(bv))
      return sortDir === 'asc' ? cmp : -cmp
    })
    return out
  }, [rows, conditionFilter, strategyFilter, sortKey, sortDir])

  function toggleSort(key: SortKey) {
    if (key === sortKey) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  function openRun(row: AggregateRow) {
    if (!experimentId) return
    setActiveRun({ condition: row.condition, seed: row.seed, strategy: row.strategy })
    setActiveResult(null)
    api.rawRun(experimentId, row.condition, row.seed, row.strategy).then(setActiveResult)
  }

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-[22px] font-semibold tracking-tight">Explore results</h1>
          <p className="mt-1 max-w-2xl text-[13.5px] text-(--color-text-muted)">
            Every individual run from a full experiment, filterable and sortable. Click a row for the
            complete result.
          </p>
        </div>
        {experiments && experiments.length > 0 && (
          <ExperimentPicker experiments={experiments} value={experimentId} onChange={setSelected} />
        )}
      </div>

      {listLoading || loading ? (
        <Spinner label="Loading runs\u2026" />
      ) : error ? (
        <ErrorState message={error} />
      ) : !rows || rows.length === 0 ? (
        <EmptyState title="No experiments yet" description="Run the full experiment to populate this table with real results." />
      ) : (
        <>
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <select
              value={conditionFilter}
              onChange={(e) => setConditionFilter(e.target.value as Condition | 'all')}
              className="rounded-md border border-(--color-border-strong) bg-(--color-panel-raised) px-2.5 py-1.5 text-[12px]"
            >
              <option value="all">All conditions</option>
              <option value="light">Light</option>
              <option value="heavy">Heavy</option>
            </select>
            <select
              value={strategyFilter}
              onChange={(e) => setStrategyFilter(e.target.value as StrategyId | 'all')}
              className="rounded-md border border-(--color-border-strong) bg-(--color-panel-raised) px-2.5 py-1.5 text-[12px]"
            >
              <option value="all">All strategies</option>
              {Object.entries(STRATEGY_META).map(([id, meta]) => (
                <option key={id} value={id}>
                  {meta.label}
                </option>
              ))}
            </select>
            <span className="text-[12px] text-(--color-text-faint)">{filteredSorted.length} runs</span>
            <button
              onClick={() => setShowPlots((v) => !v)}
              className="ml-auto rounded-md border border-(--color-border-strong) px-3 py-1.5 text-[12px] font-medium hover:bg-(--color-panel-raised)"
            >
              {showPlots ? 'Hide' : 'Show'} presentation plots
            </button>
          </div>

          {showPlots && experimentId && (
            <Card className="mb-5">
              <CardHeader title="Presentation plots" subtitle="The exact static Matplotlib exports the CLI's `experiment` command generates" />
              <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
                {PLOT_FILES.map((f) => (
                  <PlotImage key={f} experimentId={experimentId} filename={f} />
                ))}
              </div>
            </Card>
          )}

          <Card className="overflow-x-auto p-0">
            {filteredSorted.length === 0 ? (
              <div className="px-4 py-10 text-center text-[13px] text-(--color-text-muted)">
                No runs match this filter combination.
              </div>
            ) : (
            <table className="w-full min-w-[720px] text-[12.5px]">
              <thead>
                <tr className="border-b border-(--color-border) text-left text-[11px] text-(--color-text-faint)">
                  {COLUMNS.map((col) => (
                    <th
                      key={col.key}
                      onClick={() => toggleSort(col.key)}
                      className="cursor-pointer select-none whitespace-nowrap px-3 py-2.5 font-medium hover:text-(--color-text)"
                    >
                      <span className="inline-flex items-center gap-1">
                        {col.label}
                        {sortKey === col.key && (sortDir === 'asc' ? <ArrowUp size={11} /> : <ArrowDown size={11} />)}
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredSorted.map((row) => (
                  <tr
                    key={`${row.condition}-${row.seed}-${row.strategy}`}
                    onClick={() => openRun(row)}
                    className="cursor-pointer border-b border-(--color-border) transition-colors last:border-0 hover:bg-(--color-panel-raised)"
                  >
                    <td className="px-3 py-2 font-mono">{row.seed}</td>
                    <td className="px-3 py-2 capitalize text-(--color-text-muted)">{row.condition}</td>
                    <td className="px-3 py-2">
                      <StrategyBadge strategy={row.strategy} size="sm" />
                    </td>
                    <td className="px-3 py-2">
                      <StatusBadge status={row.status as string} />
                    </td>
                    <td className="px-3 py-2 font-mono">{fmtNum(row.throughput)}</td>
                    <td className="px-3 py-2 font-mono">{fmtNum(row.avg_waiting_time)}</td>
                    <td className="px-3 py-2 font-mono">{row.deadlock_episodes as number}</td>
                    <td className="px-3 py-2 font-mono">{row.recovery_actions as number}</td>
                    <td className="px-3 py-2 font-mono">{row.useful_work_lost as number}</td>
                    <td className="px-3 py-2 font-mono">{row.unnecessary_denials as number}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            )}
          </Card>
        </>
      )}

      <Modal open={activeRun !== null} onClose={() => setActiveRun(null)}>
        {activeRun && (activeResult ? <ResultDetail result={activeResult} /> : <Spinner label="Loading run detail\u2026" />)}
      </Modal>
    </div>
  )
}
