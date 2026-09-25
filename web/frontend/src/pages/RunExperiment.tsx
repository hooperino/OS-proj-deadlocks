import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { CheckCircle2, Play, RotateCcw } from 'lucide-react'
import { api, streamExperiment } from '../lib/api'
import type { CompleteEvent, ProgressEvent, StrategyId } from '../lib/types'
import { STRATEGY_META, STRATEGY_ORDER, fmtNum } from '../lib/format'
import { Card } from '../components/ui/Card'
import { ErrorState } from '../components/ui/Feedback'

type Phase = 'idle' | 'running' | 'done' | 'error'

interface Tally {
  runs: number
  deadlockEpisodes: number
  recoveryActions: number
  unnecessaryDenials: number
  throughputSum: number
}

const emptyTally = (): Tally => ({ runs: 0, deadlockEpisodes: 0, recoveryActions: 0, unnecessaryDenials: 0, throughputSum: 0 })

export function RunExperiment() {
  const [phase, setPhase] = useState<Phase>('idle')
  const [events, setEvents] = useState<ProgressEvent[]>([])
  const [tallies, setTallies] = useState<Record<StrategyId, Tally>>({
    prevention: emptyTally(),
    avoidance: emptyTally(),
    detection_recovery: emptyTally(),
  })
  const [resultDir, setResultDir] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const logRef = useRef<HTMLDivElement>(null)
  const stopRef = useRef<() => void>(() => {})

  useEffect(() => () => stopRef.current(), [])

  useEffect(() => {
    const el = logRef.current
    if (el && typeof el.scrollTo === 'function') {
      el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
    }
  }, [events])

  function start() {
    setPhase('running')
    setEvents([])
    setResultDir(null)
    setError(null)
    setTallies({ prevention: emptyTally(), avoidance: emptyTally(), detection_recovery: emptyTally() })

    api
      .startExperiment()
      .then(({ job_id }) => {
        stopRef.current = streamExperiment(job_id, (evt) => {
          if (evt.event === 'progress') {
            const p = evt as ProgressEvent
            setEvents((prev) => [...prev.slice(-199), p])
            setTallies((prev) => {
              const t = prev[p.strategy]
              return {
                ...prev,
                [p.strategy]: {
                  runs: t.runs + 1,
                  deadlockEpisodes: t.deadlockEpisodes + p.deadlock_episodes,
                  recoveryActions: t.recoveryActions + p.recovery_actions,
                  unnecessaryDenials: t.unnecessaryDenials + p.unnecessary_denials,
                  throughputSum: t.throughputSum + p.throughput,
                },
              }
            })
          } else {
            const c = evt as CompleteEvent
            if (c.error) {
              setError(c.error)
              setPhase('error')
            } else {
              setResultDir(c.dir_name)
              setPhase('done')
            }
          }
        }, () => {
          setError('Lost connection to the server before the experiment finished.')
          setPhase('error')
        })
      })
      .catch((err: Error) => {
        setError(err.message)
        setPhase('error')
      })
  }

  const done = events.length > 0 ? events[events.length - 1].done : 0
  const total = events.length > 0 ? events[events.length - 1].total : 180
  const pct = total > 0 ? (done / total) * 100 : 0

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-[22px] font-semibold tracking-tight">Run experiment</h1>
        <p className="mt-1 max-w-2xl text-[13.5px] text-(--color-text-muted)">
          Executes all 180 combinations &mdash; 30 Light seeds and 30 Heavy seeds, each against
          Prevention, Avoidance, and Detection+Recovery from fresh state &mdash; live, in this browser
          tab. Every run below is a genuine simulation completing in real time, not a replay.
        </p>
      </div>

      {phase === 'idle' && (
        <Card className="flex flex-col items-center gap-4 py-14 text-center">
          <div className="rounded-full bg-(--color-amber-soft) p-4">
            <Play size={22} className="text-(--color-amber)" />
          </div>
          <div>
            <div className="text-[15px] font-medium">Ready to run the full comparison</div>
            <div className="mt-1 text-[13px] text-(--color-text-muted)">
              Usually finishes in a few seconds &mdash; 180 discrete-event simulations is genuinely fast.
            </div>
          </div>
          <button
            onClick={start}
            className="inline-flex items-center gap-2 rounded-md bg-(--color-amber) px-5 py-2.5 text-[13.5px] font-medium text-(--color-void) hover:opacity-90"
          >
            <Play size={15} />
            Start experiment
          </button>
        </Card>
      )}

      {phase !== 'idle' && (
        <>
          <Card className="mb-5">
            <div className="mb-2 flex items-center justify-between text-[13px]">
              <span className="font-medium">
                {phase === 'running' && 'Running\u2026'}
                {phase === 'done' && (
                  <span className="inline-flex items-center gap-1.5 text-(--color-good)">
                    <CheckCircle2 size={15} /> Complete
                  </span>
                )}
                {phase === 'error' && 'Failed'}
              </span>
              <span className="font-mono text-(--color-text-muted)">
                {done} / {total} runs
              </span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-(--color-panel-inset)">
              <motion.div
                className="h-full rounded-full bg-(--color-amber)"
                initial={{ width: 0 }}
                animate={{ width: `${pct}%` }}
                transition={{ ease: 'easeOut', duration: 0.2 }}
              />
            </div>

            {phase === 'done' && resultDir && (
              <div className="mt-4 flex flex-wrap items-center gap-3">
                <Link
                  to="/compare"
                  className="inline-flex items-center gap-2 rounded-md bg-(--color-amber) px-3.5 py-2 text-[13px] font-medium text-(--color-void) hover:opacity-90"
                >
                  View comparison
                </Link>
                <Link
                  to="/explore"
                  className="inline-flex items-center gap-2 rounded-md border border-(--color-border-strong) px-3.5 py-2 text-[13px] font-medium hover:bg-(--color-panel-raised)"
                >
                  Explore raw runs
                </Link>
                <button
                  onClick={start}
                  className="inline-flex items-center gap-2 rounded-md border border-(--color-border-strong) px-3.5 py-2 text-[13px] font-medium hover:bg-(--color-panel-raised)"
                >
                  <RotateCcw size={13} /> Run again
                </button>
              </div>
            )}
            {phase === 'error' && error && <div className="mt-4"><ErrorState message={error} /></div>}
          </Card>

          <div className="mb-5 grid grid-cols-1 gap-3 sm:grid-cols-3">
            {STRATEGY_ORDER.map((s) => {
              const t = tallies[s]
              return (
                <Card key={s} accent={STRATEGY_META[s].color}>
                  <div className="text-[12px] font-medium" style={{ color: STRATEGY_META[s].color }}>
                    {STRATEGY_META[s].short}
                  </div>
                  <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1.5 text-[12px]">
                    <span className="text-(--color-text-faint)">Runs so far</span>
                    <span className="text-right font-mono">{t.runs}</span>
                    <span className="text-(--color-text-faint)">Avg throughput</span>
                    <span className="text-right font-mono">{t.runs ? fmtNum(t.throughputSum / t.runs) : '\u2014'}</span>
                    <span className="text-(--color-text-faint)">Deadlock episodes</span>
                    <span className="text-right font-mono">{t.deadlockEpisodes}</span>
                    <span className="text-(--color-text-faint)">Recovery actions</span>
                    <span className="text-right font-mono">{t.recoveryActions}</span>
                    <span className="text-(--color-text-faint)">Unnecessary denials</span>
                    <span className="text-right font-mono">{t.unnecessaryDenials}</span>
                  </div>
                </Card>
              )
            })}
          </div>

          <Card>
            <div className="mb-3 text-[13px] font-medium text-(--color-text-muted)">Live run log</div>
            <div ref={logRef} className="max-h-72 overflow-x-auto overflow-y-auto font-mono text-[11.5px] leading-relaxed">
              <div className="min-w-[480px]">
                {events.slice(-60).map((e, i) => (
                  <div key={i} className="flex items-center gap-3 border-b border-(--color-border) py-1 last:border-0">
                    <span className="w-10 shrink-0 text-(--color-text-faint)">#{e.done}</span>
                    <span className="w-12 shrink-0 uppercase text-(--color-text-faint)">{e.condition}</span>
                    <span className="w-14 shrink-0 text-(--color-text-faint)">seed {e.seed}</span>
                    <span className="w-40 shrink-0" style={{ color: STRATEGY_META[e.strategy].color }}>
                      {STRATEGY_META[e.strategy].short}
                    </span>
                    <span className="flex-1 truncate text-(--color-text-muted)">
                      {e.deadlock_episodes > 0
                        ? `${e.deadlock_episodes} deadlock episode(s), ${e.recovery_actions} recovery action(s)`
                        : e.unnecessary_denials > 0
                          ? `${e.unnecessary_denials} unnecessary denial(s)`
                          : 'completed cleanly'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </Card>
        </>
      )}
    </div>
  )
}
