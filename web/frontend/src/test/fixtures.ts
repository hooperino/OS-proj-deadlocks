import type { AggregateRow, Config, ExperimentDetail, ExperimentListItem, SimulationResult, SummaryRow } from '../lib/types'

export const mockConfig: Config = {
  resource_names: ['CPU', 'Memory', 'GPU', 'Disk', 'Network'],
  capacities: [10, 8, 6, 12, 5],
  num_processes: 20,
  detection_interval: 10,
  max_ticks_light: 5000,
  max_ticks_heavy: 15000,
  light_seeds: [1, 2, 3],
  heavy_seeds: [101, 102, 103],
  strategies: [
    { id: 'prevention', label: 'Prevention' },
    { id: 'avoidance', label: 'Avoidance (Banker)' },
    { id: 'detection_recovery', label: 'Detection + Recovery' },
  ],
  total_runs: 180,
}

export const mockExperimentList: ExperimentListItem[] = [
  { id: 'experiment_20260920_100000', timestamp: '2026-09-20T10:00:00', total_runs: 180, incomplete_runs: 0 },
]

const strategyRow = (condition: 'light' | 'heavy', strategy: string): SummaryRow => ({
  condition: condition as 'light' | 'heavy',
  strategy: strategy as SummaryRow['strategy'],
  n_runs: 30,
  throughput_mean: 10.5,
  throughput_std: 1.2,
  avg_waiting_time_mean: 8.3,
  avg_waiting_time_std: 2.1,
  unnecessary_denials_mean: condition === 'heavy' ? 20 : 2,
  unnecessary_denials_std: 3,
  deadlock_episodes_mean: strategy === 'detection_recovery' && condition === 'heavy' ? 3 : 0,
  deadlock_episodes_std: 1,
  recovery_actions_mean: strategy === 'detection_recovery' && condition === 'heavy' ? 6 : 0,
  recovery_actions_std: 2,
  useful_work_lost_mean: strategy === 'detection_recovery' && condition === 'heavy' ? 50 : 0,
  useful_work_lost_std: 10,
  blocked_processes_mean: 8,
  blocked_processes_std: 2,
  overall_utilization_mean: 0.25,
  overall_utilization_std: 0.03,
  total_resources_wasted_mean: 5,
  total_resources_wasted_std: 2,
})

export const mockSummary: SummaryRow[] = [
  strategyRow('light', 'prevention'),
  strategyRow('light', 'avoidance'),
  strategyRow('light', 'detection_recovery'),
  strategyRow('heavy', 'prevention'),
  strategyRow('heavy', 'avoidance'),
  strategyRow('heavy', 'detection_recovery'),
]

export const mockExperimentDetail: ExperimentDetail = {
  id: 'experiment_20260920_100000',
  timestamp: '2026-09-20T10:00:00',
  summary: mockSummary,
}

export const mockAggregate: AggregateRow[] = [
  {
    condition: 'heavy',
    seed: 101,
    strategy: 'detection_recovery',
    status: 'COMPLETE',
    ticks_elapsed: 180,
    total_useful_work: 1900,
    throughput: 10.5,
    avg_waiting_time: 9.5,
    blocked_processes: 9,
    overall_utilization: 0.26,
    deadlock_episodes: 2,
    recovery_actions: 3,
    distinct_restarted_processes: 2,
    useful_work_lost: 15,
    total_resources_wasted: 40,
    unnecessary_denials: 0,
    overhead_detection_passes: 18,
  },
]

export const mockSingleRunResult: SimulationResult = {
  condition: 'heavy',
  seed: 101,
  strategy: 'detection_recovery',
  status: 'COMPLETE',
  ticks_elapsed: 180,
  total_useful_work: 1900,
  throughput: 10.5,
  avg_waiting_time: 9.5,
  blocked_processes: 9,
  overall_utilization: 0.26,
  deadlock_episodes: 2,
  recovery_actions: 3,
  distinct_restarted_processes: 2,
  useful_work_lost: 15,
  total_resources_wasted: 40,
  unnecessary_denials: 0,
  waiting_times: [3, 5, 12],
  utilization_CPU: 0.3,
  utilization_Memory: 0.2,
  overhead_detection_passes: 18,
  overhead_processes_examined: 45,
  wasted_CPU: 20,
  wasted_Memory: 20,
}
