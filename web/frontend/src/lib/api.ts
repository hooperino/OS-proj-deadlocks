import type {
  AggregateRow,
  Condition,
  Config,
  ExperimentDetail,
  ExperimentListItem,
  SimulationResult,
  StrategyId,
  StreamEvent,
} from './types'

const BASE = '/api'

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`Request failed (${res.status}): ${text || res.statusText}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  config: () => getJSON<Config>('/config'),

  singleRun: (condition: Condition, seed: number, strategy: StrategyId) =>
    getJSON<SimulationResult>(
      `/single-run?condition=${condition}&seed=${seed}&strategy=${strategy}`,
    ),

  experiments: () => getJSON<ExperimentListItem[]>('/experiments'),

  experiment: (id: string) => getJSON<ExperimentDetail>(`/experiments/${id}`),

  aggregate: (id: string) => getJSON<AggregateRow[]>(`/experiments/${id}/aggregate`),

  rawRun: (id: string, condition: Condition, seed: number, strategy: StrategyId) =>
    getJSON<SimulationResult>(`/experiments/${id}/raw/${condition}/${seed}/${strategy}`),

  plotUrl: (id: string, filename: string) => `${BASE}/experiments/${id}/plots/${filename}`,

  startExperiment: () =>
    fetch(`${BASE}/experiments/run`, { method: 'POST' }).then(
      (r) => r.json() as Promise<{ job_id: string; total: number }>,
    ),
}

/** Opens an SSE connection for a running experiment job and forwards every
 * event to `onEvent`. Returns a cleanup function that closes the stream. */
export function streamExperiment(
  jobId: string,
  onEvent: (e: StreamEvent) => void,
  onConnectionError?: () => void,
): () => void {
  const source = new EventSource(`${BASE}/experiments/run/${jobId}/stream`)
  let completed = false
  source.onmessage = (message) => {
    const data = JSON.parse(message.data) as StreamEvent
    if (data.event === 'complete') {
      completed = true
      onEvent(data)
      source.close()
    } else {
      onEvent(data)
    }
  }
  source.onerror = () => {
    source.close()
    if (!completed) onConnectionError?.()
  }
  return () => source.close()
}
