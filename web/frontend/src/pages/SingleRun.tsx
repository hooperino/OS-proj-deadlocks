import { useState } from 'react'
import { Play } from 'lucide-react'
import { useConfig } from '../lib/hooks'
import { api } from '../lib/api'
import type { Condition, SimulationResult, StrategyId } from '../lib/types'
import { STRATEGY_ORDER } from '../lib/format'
import { Card } from '../components/ui/Card'
import { ErrorState, Spinner } from '../components/ui/Feedback'
import { ResultDetail } from '../components/ResultDetail'

export function SingleRun() {
  const { data: config } = useConfig()
  const [condition, setCondition] = useState<Condition>('heavy')
  const [seed, setSeed] = useState<number>(101)
  const [strategy, setStrategy] = useState<StrategyId>('detection_recovery')
  const [result, setResult] = useState<SimulationResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const seedOptions = config ? (condition === 'light' ? config.light_seeds : config.heavy_seeds) : []

  function run() {
    setLoading(true)
    setError(null)
    api
      .singleRun(condition, seed, strategy)
      .then(setResult)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-[22px] font-semibold tracking-tight">Single run</h1>
        <p className="mt-1 max-w-2xl text-[13.5px] text-(--color-text-muted)">
          Pick one workload and one strategy, run it live, and inspect the full result &mdash; the same
          result shape the 180-run experiment produces, for one run instead of 180.
        </p>
      </div>

      <Card className="mb-6">
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <label className="mb-1.5 block text-[11.5px] font-medium text-(--color-text-muted)">Condition</label>
            <div className="flex rounded-md border border-(--color-border-strong) p-0.5">
              {(['light', 'heavy'] as const).map((c) => (
                <button
                  key={c}
                  onClick={() => {
                    setCondition(c)
                    setSeed(c === 'light' ? (config?.light_seeds[0] ?? 1) : (config?.heavy_seeds[0] ?? 101))
                  }}
                  className={`rounded px-3.5 py-1.5 text-[12.5px] font-medium capitalize transition-colors ${
                    condition === c ? 'bg-(--color-amber-soft) text-(--color-amber)' : 'text-(--color-text-muted) hover:text-(--color-text)'
                  }`}
                >
                  {c}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="mb-1.5 block text-[11.5px] font-medium text-(--color-text-muted)">Seed</label>
            <select
              value={seed}
              onChange={(e) => setSeed(Number(e.target.value))}
              className="rounded-md border border-(--color-border-strong) bg-(--color-panel-raised) px-3 py-1.5 text-[12.5px]"
            >
              {seedOptions.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1.5 block text-[11.5px] font-medium text-(--color-text-muted)">Strategy</label>
            <select
              value={strategy}
              onChange={(e) => setStrategy(e.target.value as StrategyId)}
              className="rounded-md border border-(--color-border-strong) bg-(--color-panel-raised) px-3 py-1.5 text-[12.5px]"
            >
              {STRATEGY_ORDER.map((s) => (
                <option key={s} value={s}>
                  {config?.strategies.find((m) => m.id === s)?.label ?? s}
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={run}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-md bg-(--color-amber) px-4 py-2 text-[13px] font-medium text-(--color-void) hover:opacity-90 disabled:opacity-50"
          >
            <Play size={14} />
            {loading ? 'Running\u2026' : 'Run'}
          </button>
        </div>
      </Card>

      {loading && <Spinner label="Running the simulation\u2026" />}
      {error && <ErrorState message={error} />}
      {result && !loading && <ResultDetail result={result} />}
    </div>
  )
}
