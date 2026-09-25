# Integration Contract

Stable interfaces between modules. Future changes to the implementation
should preserve these unless a genuine correctness issue requires changing
the contract itself -- in which case update this file in the same commit.

## `core.config.SimulationConfig`

Frozen dataclass. `resource_names` (tuple, index order IS Prevention rank),
`capacities` (tuple, same length/order), `num_processes`,
`detection_interval`, `max_ticks_light`, `max_ticks_heavy`. Helper methods:
`num_resources`, `capacities_array() -> np.ndarray` (fresh copy each call),
`max_ticks_for(Condition) -> int`, `resource_index(name) -> int`.
`DEFAULT_CONFIG` is the canonical instance used everywhere except tests that
deliberately construct a custom config (e.g. tiny `max_ticks` to exercise
INCOMPLETE, or capacity=1 to model single-instance resources).
`LIGHT_SEEDS = range(1, 31)`, `HEAVY_SEEDS = range(101, 131)` are also
defined in this module and re-used by the generator, experiment runner, and
CLI -- there is exactly one place seed ranges are defined.

## `core.workload.Workload` / `ProcessWorkload`

Immutable schema, no generation logic. `Workload(condition, seed, processes,
next_sequence_number)`. `ProcessWorkload(pid, total_work, max_claim,
events)`. `events` is a tuple of `RequestEvent`/`ReleaseEvent`
(`core.events`), sorted by timestamp. `next_sequence_number` must be
strictly greater than every `sequence_number` used anywhere in `processes`
-- the Simulator uses it as the starting counter for sequence numbers it
assigns to restart-replayed events. Anything that builds a `Workload`
(the generator, or a test's hand-crafted scenario) must satisfy this
invariant; the Simulator trusts it without re-validating.

## `strategies.*.Strategy` (ABC in `core.actions`)

```python
class Strategy(ABC):
    name: StrategyName
    def evaluate_request(self, state: SimulationState, pid: int, request: np.ndarray) -> RequestEvaluation
    def periodic_check(self, state: SimulationState) -> PeriodicCheckResult
    def overhead_stats(self) -> Dict[str, int]
```

- Never mutates `state`. May freely read it.
- `evaluate_request` is called once per newly-arrived REQUEST event (with
  the process guaranteed `RUNNING`, never `WAITING`/`COMPLETED`) and again,
  every subsequent tick, for each still-pending request in FCFS order until
  it returns GRANT. It must be safe to call repeatedly with unchanged state
  and get the same answer (all three implementations are pure functions of
  `state` plus their own private overhead counters).
- `periodic_check` is called exactly once per tick, for every tick,
  regardless of strategy. Prevention and Avoidance always return
  `PeriodicCheckResult()` (empty). Detection+Recovery returns non-empty only
  on ticks where `current_tick > 0 and current_tick % interval == 0`, and
  when it does, `actions` is the *complete, ordered* list of victims to
  terminate this tick -- the Simulator applies them in that exact order
  without re-consulting the strategy mid-loop.
- `overhead_stats()` keys are strategy-specific and stable:
  - Prevention: `ordering_checks`, `request_evaluations`
  - Avoidance: `safety_checks`, `processes_examined`, `safety_iterations`
  - Detection+Recovery: `detection_passes`, `processes_examined`,
    `detection_iterations`, `victim_selections`

  These become `overhead_<key>` columns in the aggregate CSV; a row's
  columns for a *different* strategy's keys are `NaN`, not zero (zero would
  wrongly imply "this strategy did zero of that other strategy's kind of
  work").
- A fresh `Strategy` instance must be constructed per simulation run (never
  reused across runs) -- its overhead counters accumulate for the lifetime
  of the instance. `experiment.runner.STRATEGY_FACTORIES` is the single
  source of truth mapping `StrategyName -> Strategy subclass` for this
  purpose; nothing else in the codebase should hardcode that mapping.

## `core.simulator.Simulator`

```python
Simulator(config: SimulationConfig, workload: Workload, strategy: Strategy)
Simulator.run() -> SimulationResult
```

Constructing a `Simulator` builds fresh `SimulationState` from `workload`
immediately (no separate "reset" call) -- one `Simulator` instance is good
for exactly one `run()`. `run()` is deterministic: identical
`(config, workload, strategy_class)` always produces a `SimulationResult`
that compares equal via `to_json_dict()` (see `tests/test_determinism.py`).
The individual `_step*` methods (`_step1_expirations` through
`_step7_completion`, plus `_pop_due_events`) are technically private but are
used directly by tests that need fine-grained control over tick-by-tick
state (e.g. to force an exact detection tick, or to assert intermediate
holding state) -- they are part of the de facto contract for white-box
testing even though they're not part of the public run() API. Any
refactor of the tick loop's internal structure should keep these seven
methods (or clearly update the tests that depend on their names/signatures
in the same commit).

## `core.result.SimulationResult`

Frozen dataclass; see field list in `core/result.py`. Two serialization
methods: `to_flat_dict()` (one flat row, used for the aggregate CSV/
DataFrame -- expands `resource_utilization`/`resources_wasted`/
`algorithm_overhead` dicts into `utilization_<name>`/`wasted_<name>`/
`overhead_<key>` columns) and `to_json_dict()` (flat dict plus
`waiting_times` as a list, used for raw per-run JSON). Any new field added
to `SimulationResult` should be added to `to_flat_dict()` too, or it will
silently be missing from the CSV/plots.

## `experiment.metrics`

`results_to_dataframe(List[SimulationResult]) -> pd.DataFrame` (one row per
run, via `to_flat_dict()`). `summarize(df) -> pd.DataFrame`: grouped by
`["condition", "strategy"]`, every other numeric column gets `_mean`/`_std`
suffixed columns, plus an `n_runs` column from `groupby(...).size()`. This
is the only pandas-touching code path that `experiment.plots` and
`experiment.runner` both depend on -- if the grouping keys or suffix
convention change, both callers need updating together.

## `experiment.plots`

`generate_all_plots(df: pd.DataFrame, out_dir: Path) -> None`. Writes
exactly 8 PNGs with fixed filenames (`throughput.png`,
`avg_waiting_time.png`, `resource_utilization.png`, `blocked_processes.png`,
`deadlock_episodes.png`, `recovery_cost.png`, `useful_work_lost.png`,
`terminated_restarted_processes.png`) -- the CLI, tests, and any future
report-generation code can rely on these exact names existing under
`out_dir` after the call returns. Uses the `Agg` backend and never calls
`plt.show()`.

## `experiment.runner`

`run_single(condition, seed, strategy_name, config=DEFAULT_CONFIG) ->
SimulationResult` -- one run, used by both the CLI's `single-run` and
several tests. `run_experiment(output_root=Path("results"),
config=DEFAULT_CONFIG, progress=True, on_run_complete=None) -> Path` -- the
full 180-run comparison; returns the timestamped output directory
(`<output_root>/experiment_<YYYYMMDD_HHMMSS>/`) containing `raw/`,
`raw_all.json`, `aggregate.csv`, `summary.csv`, `run_report.txt`, `plots/`.
`on_run_complete`, if given, is called synchronously as
`(result: SimulationResult, done: int, total: int)` after every individual
run -- this is the hook `web/backend` uses to stream live progress; it has
no effect on CLI behavior (default `None`) and receives the exact same
`SimulationResult` objects that end up in the output, never a duplicate
computation. `TOTAL_RUNS` (180) and `STRATEGY_FACTORIES` are importable
constants other modules (tests, CLI, web backend) rely on rather than
recomputing.

## `cli.main`

`main(argv=None) -> int`, importable and callable directly (used by tests
indirectly via `run_experiment`/`run_single`; the CLI layer itself is a thin
argparse wrapper with no independent logic worth a separate contract beyond
"the `experiment` and `single-run` subcommands exist with the flags
documented in README.md").

## `web/backend` HTTP API

Thin FastAPI layer over everything above; full request/response shapes are
self-documented at `/docs` (FastAPI's generated OpenAPI UI) when the server
is running. The contract other code should be able to rely on:

- `GET /api/config` -- static `SimulationConfig`-derived info (resource
  names/capacities, seed ranges, strategy list). No simulation state.
- `GET /api/single-run?condition=&seed=&strategy=` -- runs
  `run_single()` live; returns `SimulationResult.to_json_dict()` verbatim.
- `GET /api/experiments` -- lists `results/experiment_*` directories
  (newest first) that have a `summary.csv` (i.e. are complete, browsable).
- `GET /api/experiments/{id}`, `.../aggregate`,
  `.../raw/{condition}/{seed}/{strategy}`, `.../plots/{filename}` -- read
  `summary.csv`, `aggregate.csv`, `raw/*.json`, `plots/*.png` respectively,
  from exactly the directory `run_experiment()` wrote. `{id}` is validated
  against the `experiment_YYYYMMDD_HHMMSS` pattern before touching the
  filesystem (see `results_store._experiment_dir`), so it can never escape
  `results/`.
- `POST /api/experiments/run` -- starts a full `run_experiment()` call in a
  background thread; returns `{job_id, total}` immediately.
- `GET /api/experiments/run/{job_id}/stream` -- Server-Sent Events. Each
  message is one JSON object: `{"event": "progress", "done", "total",
  "condition", "seed", "strategy", "status", "deadlock_episodes",
  "recovery_actions", "unnecessary_denials", "throughput"}` per completed
  run, followed by exactly one final `{"event": "complete", "dir_name",
  "error"}` (```dir_name``` is the same directory `/api/experiments` will
  subsequently list; `error` is non-null only if the background run raised).

Any new frontend or client should treat `SimulationResult.to_json_dict()`
(used by both `single-run` and `raw/...`) and the `aggregate.csv`/
`summary.csv` row shapes (used by `aggregate`/the `{id}` summary) as the
stable schemas -- both are defined once in `core/result.py` and
`experiment/metrics.py` respectively and never duplicated in the web layer.
