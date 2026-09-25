import { useEffect, useState } from 'react'
import { api } from './api'
import type { AggregateRow, Config, ExperimentDetail, ExperimentListItem } from './types'

interface AsyncState<T> {
  data: T | null
  loading: boolean
  error: string | null
}

function useAsync<T>(fn: () => Promise<T>, deps: unknown[]): AsyncState<T> & { reload: () => void } {
  const [state, setState] = useState<AsyncState<T>>({ data: null, loading: true, error: null })
  const [tick, setTick] = useState(0)

  useEffect(() => {
    let cancelled = false
    setState((s) => ({ ...s, loading: true, error: null }))
    fn()
      .then((data) => {
        if (!cancelled) setState({ data, loading: false, error: null })
      })
      .catch((err: Error) => {
        if (!cancelled) setState({ data: null, loading: false, error: err.message })
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick])

  return { ...state, reload: () => setTick((t) => t + 1) }
}

export function useConfig() {
  return useAsync<Config>(() => api.config(), [])
}

export function useExperimentList() {
  return useAsync<ExperimentListItem[]>(() => api.experiments(), [])
}

export function useExperiment(id: string | null) {
  return useAsync<ExperimentDetail>(() => (id ? api.experiment(id) : Promise.reject(new Error('no id'))), [id])
}

export function useAggregate(id: string | null) {
  return useAsync<AggregateRow[]>(() => (id ? api.aggregate(id) : Promise.reject(new Error('no id'))), [id])
}
