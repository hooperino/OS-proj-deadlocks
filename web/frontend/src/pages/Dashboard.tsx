import { Link } from 'react-router-dom'
import { ArrowRight, Play, SearchCode } from 'lucide-react'
import { useExperimentList, useExperiment } from '../lib/hooks'
import { Card, CardHeader } from '../components/ui/Card'
import { StatTile, CountUp } from '../components/ui/StatTile'
import { EmptyState, ErrorState, Spinner } from '../components/ui/Feedback'
import { GroupedBarChart } from '../components/charts/GroupedBarChart'
import { formatTimestamp } from '../lib/format'

function Hero() {
  return (
    <div className="mb-8 flex flex-col gap-8 md:flex-row md:items-center">
      <div className="flex-1">
        <h1 className="text-[26px] font-semibold tracking-tight text-(--color-text) sm:text-[30px]">
          Three ways to keep an operating system out of deadlock.
        </h1>
        <p className="mt-3 max-w-xl text-[14px] leading-relaxed text-(--color-text-muted)">
          A discrete-event simulation of 20 processes contending for 5 resources, run under
          resource-ordering Prevention, Banker&rsquo;s Algorithm Avoidance, and Detection with
          Recovery &mdash; under both Light and Heavy contention. Every number on this page comes
          from a real simulation, run live from this page.
        </p>
        <div className="mt-5 flex flex-wrap gap-3">
          <Link
            to="/run"
            className="inline-flex items-center gap-2 rounded-md bg-(--color-amber) px-4 py-2 text-[13.5px] font-medium text-(--color-void) transition-opacity hover:opacity-90"
          >
            <Play size={15} />
            Run the full experiment
          </Link>
          <Link
            to="/explore"
            className="inline-flex items-center gap-2 rounded-md border border-(--color-border-strong) px-4 py-2 text-[13.5px] font-medium text-(--color-text) transition-colors hover:bg-(--color-panel-raised)"
          >
            <SearchCode size={15} />
            Explore past results
          </Link>
        </div>
      </div>
      <svg viewBox="0 0 220 160" className="hidden w-64 shrink-0 md:block" fill="none">
        <circle cx="45" cy="35" r="22" stroke="var(--color-prevention)" strokeWidth="1.6" />
        <text x="45" y="40" textAnchor="middle" fill="var(--color-prevention)" fontSize="10" fontFamily="var(--font-mono)">P</text>
        <circle cx="175" cy="35" r="22" stroke="var(--color-avoidance)" strokeWidth="1.6" />
        <text x="175" y="40" textAnchor="middle" fill="var(--color-avoidance)" fontSize="10" fontFamily="var(--font-mono)">A</text>
        <circle cx="110" cy="130" r="22" stroke="var(--color-recovery)" strokeWidth="1.6" />
        <text x="110" y="135" textAnchor="middle" fill="var(--color-recovery)" fontSize="10" fontFamily="var(--font-mono)">D</text>
        <rect x="90" y="72" width="40" height="26" rx="4" stroke="var(--color-text-faint)" strokeWidth="1.3" />
        <text x="110" y="88" textAnchor="middle" fill="var(--color-text-muted)" fontSize="8" fontFamily="var(--font-mono)">R1..R5</text>
        <path d="M62 45 L94 78" stroke="var(--color-text-faint)" strokeWidth="1.2" />
        <path d="M158 45 L126 78" stroke="var(--color-text-faint)" strokeWidth="1.2" />
        <path d="M110 98 L110 108" stroke="var(--color-text-faint)" strokeWidth="1.2" />
      </svg>
    </div>
  )
}

export function Dashboard() {
  const { data: experiments, loading: listLoading, error: listError } = useExperimentList()
  const latestId = experiments && experiments.length > 0 ? experiments[0].id : null
  const { data: detail, loading: detailLoading } = useExperiment(latestId)

  if (listLoading) {
    return (
      <>
        <Hero />
        <Spinner label="Checking for existing experiment results…" />
      </>
    )
  }

  if (listError) {
    return (
      <>
        <Hero />
        <ErrorState message={listError} />
      </>
    )
  }

  if (!experiments || experiments.length === 0) {
    return (
      <>
        <Hero />
        <EmptyState
          title="No experiments have been run yet"
          description="Run the complete 180-run comparison (30 Light + 30 Heavy seeds, each against all three strategies) to populate this dashboard with real results."
          action={
            <Link
              to="/run"
              className="inline-flex items-center gap-2 rounded-md bg-(--color-amber) px-4 py-2 text-[13.5px] font-medium text-(--color-void) hover:opacity-90"
            >
              <Play size={15} />
              Run the full experiment
            </Link>
          }
        />
      </>
    )
  }

  const totalIncomplete = experiments.reduce((sum, e) => sum + (e.incomplete_runs ?? 0), 0)
  const totalRuns = experiments.reduce((sum, e) => sum + (e.total_runs ?? 0), 0)

  return (
    <>
      <Hero />

      <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Experiments run" value={<CountUp value={experiments.length} />} />
        <StatTile label="Simulations executed" value={<CountUp value={totalRuns} />} hint="180 per experiment" />
        <StatTile
          label="Runs completed"
          value={<CountUp value={totalRuns - totalIncomplete} />}
          suffix={`/ ${totalRuns}`}
          color={totalIncomplete === 0 ? 'var(--color-good)' : 'var(--color-warn)'}
        />
        <StatTile label="Latest run" value={formatTimestamp(experiments[0].timestamp).split(',')[0]} hint={formatTimestamp(experiments[0].timestamp).split(',')[1]?.trim()} />
      </div>

      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-[15px] font-semibold">Latest experiment at a glance</h2>
        <Link
          to="/compare"
          className="inline-flex items-center gap-1 text-[12.5px] font-medium text-(--color-amber) hover:underline"
        >
          Full comparison <ArrowRight size={13} />
        </Link>
      </div>

      {detailLoading || !detail ? (
        <Spinner />
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader title="Throughput" subtitle="Useful work completed per simulated tick" />
            <GroupedBarChart summary={detail.summary} metricKey="throughput" />
          </Card>
          <Card>
            <CardHeader title="Average waiting time" subtitle="Ticks spent WAITING per request that actually had to wait" />
            <GroupedBarChart summary={detail.summary} metricKey="avg_waiting_time" unit="ticks" />
          </Card>
        </div>
      )}
    </>
  )
}
