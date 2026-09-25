export type Condition = 'light' | 'heavy'
export type StrategyId = 'prevention' | 'avoidance' | 'detection_recovery'

export interface StrategyMeta {
  id: StrategyId
  label: string
}

export interface Config {
  resource_names: string[]
  capacities: number[]
  num_processes: number
  detection_interval: number
  max_ticks_light: number
  max_ticks_heavy: number
  light_seeds: number[]
  heavy_seeds: number[]
  strategies: StrategyMeta[]
  total_runs: number
}

// Fields every run always has, plus dynamic utilization_*/wasted_*/overhead_*
// keys whose exact set depends on the strategy -- read those with the
// pickByPrefix() helper in format.ts rather than naming them all here.
export interface SimulationResult {
  condition: Condition
  seed: number
  strategy: StrategyId
  status: 'COMPLETE' | 'INCOMPLETE'
  ticks_elapsed: number
  total_useful_work: number
  throughput: number
  avg_waiting_time: number
  blocked_processes: number
  overall_utilization: number
  deadlock_episodes: number
  recovery_actions: number
  distinct_restarted_processes: number
  useful_work_lost: number
  total_resources_wasted: number
  unnecessary_denials: number
  waiting_times: number[]
  [key: string]: unknown
}

export interface AggregateRow {
  condition: Condition
  seed: number
  strategy: StrategyId
  status: 'COMPLETE' | 'INCOMPLETE'
  ticks_elapsed: number
  total_useful_work: number
  throughput: number
  avg_waiting_time: number
  blocked_processes: number
  overall_utilization: number
  deadlock_episodes: number
  recovery_actions: number
  distinct_restarted_processes: number
  useful_work_lost: number
  total_resources_wasted: number
  unnecessary_denials: number
  [key: string]: unknown
}

export interface SummaryRow {
  condition: Condition
  strategy: StrategyId
  n_runs: number
  [key: string]: unknown
}

export interface ExperimentListItem {
  id: string
  timestamp: string
  total_runs: number | null
  incomplete_runs: number | null
}

export interface ExperimentDetail {
  id: string
  timestamp: string | null
  summary: SummaryRow[]
}

export interface ProgressEvent {
  event: 'progress'
  done: number
  total: number
  condition: Condition
  seed: number
  strategy: StrategyId
  status: string
  deadlock_episodes: number
  recovery_actions: number
  unnecessary_denials: number
  throughput: number
}

export interface CompleteEvent {
  event: 'complete'
  dir_name: string | null
  error: string | null
}

export type StreamEvent = ProgressEvent | CompleteEvent
