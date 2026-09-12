# Deadlock Handling Strategy Simulator

## Objective

A discrete-event simulation to quantitatively compare three OS deadlock handling strategies under identical deterministic workloads:

1. **Prevention** — Resource Ordering
2. **Avoidance** — Banker's Algorithm
3. **Detection & Recovery**

The project evaluates how each strategy affects performance, resource usage, deadlocks, and recovery overhead under **Light** and **Heavy** resource contention.

## Workload

- 20 processes
- 5 resources: CPU, Memory, GPU, Disk, Network
- Heterogeneous resource capacities
- Deterministic workloads with intentional deadlock-prone patterns
- 30 Light workloads + 30 Heavy workloads
- Each workload is independently replayed under all three strategies
- **180 total simulation runs**

## Metrics

- Throughput
- Average waiting time
- Resource utilization
- Blocked processes
- Deadlocks
- Recovery actions
- Useful work lost
- Recovery cost
- Unnecessarily denied requests
- Algorithmic overhead

Results are retained per run and aggregated using **mean ± standard deviation**.

## Execution

The project provides two modes:

- `experiment` — Runs the complete 180-run experiment and generates results and plots.
- `single-run` — Runs an individual workload and strategy for debugging.

## Reproducibility

Given the same configuration, workload, seed, and strategy, simulation results are deterministic.