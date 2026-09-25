# Architecture

## Layers and dependency direction

```
workloads/  --depends on-->  core/  <--depends on--  strategies/
                                ^
                                |
                          experiment/  (pandas, Matplotlib)
                                ^
                                |
                              cli/            web/backend/  (FastAPI, thin)
                                                    ^
                                                    |
                                              web/frontend/ (React, browser-only)
```

`web/backend/` sits at the same level as `cli/` -- both are thin front-ends
over `experiment/` (and `core/` directly, for single runs). It adds exactly
one thing `experiment/` didn't already have: an optional `on_run_complete`
progress callback on `run_experiment()`, used to stream real per-run
progress over Server-Sent Events without re-implementing the seed x
strategy loop (see `deadlock_sim/experiment/runner.py` and
`web/backend/app/jobs.py`). It otherwise only reads the same
`results/experiment_<timestamp>/` output `run_experiment()` has always
written (`web/backend/app/results_store.py`). `web/frontend/` never talks to
`deadlock_sim` directly -- everything it shows comes from `web/backend/`'s
JSON/SSE responses. See `web/README.md` for the full web-layer writeup.

`core/` has no dependency on pandas, Matplotlib, `workloads/`, `strategies/`,
or `experiment/`. It defines the *schema* a workload must have
(`core/workload.py`: `Workload`, `ProcessWorkload`) without knowing anything
about how one gets generated -- generation logic lives entirely in
`workloads/generator.py`, which depends on `core/` (for the event/config
types) but not the other way around. `strategies/` depends only on `core/`
(the `Strategy` ABC, `SimulationState`, `RequestEvaluation`,
`PeriodicCheckResult`). `experiment/` is the only place pandas is imported;
`cli/` just wires `experiment/` to argparse.

This means the core simulator and every strategy can be tested (and are
tested) without ever touching pandas, Matplotlib, or a real generated
workload -- see `tests/test_core_semantics.py`, `tests/test_prevention.py`,
`tests/test_banker.py`, `tests/test_detection_recovery.py`, all of which
build small hand-crafted `Workload` objects directly from `core` types.

## Core state model

- `SimulationConfig` (`core/config.py`) -- frozen dataclass, the single
  source of truth for resource names/order/capacities, `num_processes`,
  detection interval, and per-condition `max_ticks`. Resource *rank* for
  Prevention is simply the resource's index in `resource_names` -- there is
  no separate rank table, so it is architecturally impossible for
  Prevention's ordering to drift out of sync with the authoritative resource
  index mapping.
- `Process` (`core/process.py`) -- mutable, owned by the Simulator.
  `Need()` (max_claim - allocation) is computed on demand, never stored, per
  the spec's "compute it when needed" instruction. `generation` increments
  on every restart; see "Restart/replay" below.
- `ResourcePool` (`core/resources.py`) -- capacity/available as NumPy
  arrays. `allocate`/`release` assert the never-negative / never-exceeds-
  capacity invariants on every call -- the one piece of defensive validation
  the spec asks for, not a broader framework.
- `Holding` / `PendingRequest` (`core/holdings.py`) -- per-grant timers and
  the (at most one per pid) outstanding request. Holdings are *bookkeeping*
  for timer expiration only; the resource-accounting source of truth is
  always `process.allocation` vs `resources.available`. Whenever a bulk
  release happens (explicit RELEASE, completion, recovery termination), the
  Simulator releases `process.allocation` as one lump sum and simply
  discards that pid's remaining `Holding` entries -- it does **not**
  additionally release each holding's resource vector, which would double-
  count.
- `SimulationState` (`core/state.py`) -- the single mutable aggregate
  (config, resources, processes, holdings, pending, current_tick). Owned and
  mutated only by the Simulator; strategies receive it read-only by
  discipline (Python cannot enforce true immutability on a mutable object
  graph, but no strategy in this codebase ever assigns into it).

## Event system and restart/replay

Events are typed, immutable dataclasses (`core/events.py`). The Simulator
schedules them on a `heapq` keyed by `(timestamp, sequence_number)`. Every
scheduled entry also carries the *generation* of the process it belongs to
at schedule time. When a process is restarted, its generation increments and
its *entire original* event list (`core/workload.py`'s
`ProcessWorkload.events`, unchanged) is rescheduled with timestamps shifted
by the restart tick and *fresh* sequence numbers drawn from a counter that
starts at `Workload.next_sequence_number` (guaranteed higher than every
sequence number used anywhere in the original workload). Any stale
(pre-restart) entries still sitting in the heap are discarded the moment
they're popped, by a simple `process.generation != scheduled_generation`
check -- this avoids ever having to search-and-remove from the heap, and
keeps the "restart replays the original workload, not invented behavior"
guarantee trivially true by construction (the replayed events are the exact
same `RequestEvent`/`ReleaseEvent` objects from `ProcessWorkload.events`,
just re-timestamped).

## Why RELEASE does not defer while WAITING, but REQUEST does

This is the single most consequential design decision in the simulator, so
it's worth stating explicitly (it is also the subject of the most important
bug fixed during development -- see commit history).

The spec restricts REQUEST ("a WAITING process cannot issue another request
until its current pending request is granted") but says nothing equivalent
about RELEASE. Early in development, both were made to defer while WAITING,
on the theory that a process is a sequential program and can't "reach" a
later RELEASE while blocked on an earlier REQUEST. That turned out to be
wrong in a way that breaks the whole premise of the project: if a process's
own scheduled RELEASE always eventually fires regardless of its blocked
status, *any* two-process cyclic wait self-rescues as soon as either side's
natural RELEASE timestamp arrives -- Detection+Recovery would never have
genuine, unavoidable work to do, and Prevention's "may become valid later
after higher-ranked resources are released" (spec section 12) explicitly
depends on a blocked process still being able to give up what it holds.

So: **RELEASE fires on its scheduled tick unconditionally** (only a
COMPLETED process's own stale RELEASE is discarded); **REQUEST defers to the
next tick if the process is currently WAITING**. This is what makes it
possible for the workload generator to construct pairs whose natural
self-resolution is scheduled *far* beyond Detection+Recovery's 10-tick
cadence, guaranteeing the detector has to do real work before that natural
release would ever fire (see `workloads/generator.py`), while Prevention's
blocked processes still eventually resolve via their own release, keeping
Prevention runs `COMPLETE` rather than perpetually stuck.

## The Detection algorithm's non-pending-processes fix

The spec's matrix detection description ("Processes with no pending request
may be treated as finished... Work += Allocation[p]" only for processes
*found* via the search step) reads, if implemented completely literally, as
never folding a non-pending process's held resources into `Work` at all.
That is a real bug, not a matter of interpretation: a process with no
pending request is, by definition, not blocked -- it is making independent
progress and will eventually release its resources normally (by completing
or by a future request that gets resolved through the ordinary protocol).
The standard textbook matrix algorithm captures this by initializing
`Finish[i] = true` for such a process and *immediately* folding its
Allocation into `Work` (equivalent to processing it through the search loop,
since its trivial `Request = 0` always satisfies `<= Work`). Skipping this
step makes every currently-healthy RUNNING process's holdings permanently
invisible to the detector, so a single ordinary WAITING process whose
resource happens to be held by a perfectly healthy process gets flagged as
"deadlocked" -- a false positive. In this codebase that false positive
compounded through the restart mechanism into a 750+ restart runaway loop
on 2 of the 30 Heavy seeds before being found and fixed (see
`strategies/detection_recovery.py`'s `periodic_check` for the fix and a
longer inline explanation).

## Strategy interface and where mutation happens

`core/actions.py` defines the common interface:

```python
evaluate_request(state, pid, request) -> RequestEvaluation(decision, unnecessary_denial)
periodic_check(state) -> PeriodicCheckResult(actions, deadlock_detected)
```

Strategies never mutate `SimulationState`. Concretely:

- **Prevention** computes `avail_ok` and `order_ok` from the real state and
  returns GRANT/WAIT -- no mutation needed since it never explores
  hypothetical states.
- **Avoidance** builds *local Python dict/array copies* of
  Allocation/Need/Available, adds the tentative request to the copy, and
  runs the safety algorithm entirely against those copies. If unsafe, the
  copies are simply discarded -- there is nothing to "roll back" on real
  state because real state was never touched. This is a deliberately
  simpler and more obviously-correct implementation than mutate-then-
  rollback.
- **Detection+Recovery**'s `periodic_check` runs its entire
  detect -> pick-victim -> (locally) release -> re-detect loop against local
  copies too, and returns the full *ordered* list of `TerminateVictimAction`
  for that tick. The Simulator is the only thing that ever actually
  terminates and restarts a process.

Diagnostics/overhead counters (`ordering_checks`, `safety_iterations`,
`detection_passes`, etc.) are the one piece of state a strategy *does* keep
as private instance attributes across calls within a single run. This does
not violate "must not mutate shared simulation state" -- these counters are
strategy-local bookkeeping, not part of `SimulationState`, and a fresh
`Strategy` instance is constructed for every run (see
`experiment/runner.py`), so there is no cross-run leakage.

## Simulator tick loop

`core/simulator.py`'s `Simulator.run()` executes the locked 7-step order
every tick (see the module docstring for the exact steps). A few
non-obvious points worth flagging for whoever reads this next:

- **Zero-resource requests** need no special-casing at all: the ordering
  check is vacuously true over an empty resource-index selection, the
  availability check (`0 <= available`) is always true, and Banker's safety
  check over an unchanged tentative state stays safe if it was already
  safe. The only special case is that a zero vector does not create a
  `Holding` entry (`if np.any(request_vec)`), matching "no timer" in the
  spec.
- **`unnecessary_denials`** is only incremented at the *initial* (step 4)
  evaluation of a newly-arrived REQUEST, never during its later step-5
  reconsiderations -- otherwise a single logical request that stays pending
  for many ticks would inflate the counter once per tick it's reconsidered,
  which conflates "requests blocked" (a per-request count) with "algorithm
  overhead" (which *does* count every evaluation call, tracked separately
  via each strategy's own counters).
- **Deadlock episode counting** does not need a persisted "was a deadlock
  already active" flag across ticks: detection only ever *runs* on 10-tick
  boundaries, and the victim loop inside a single `periodic_check` call
  always fully resolves whatever it finds (by construction -- it keeps
  removing victims until its local re-detection finds none left), so by the
  end of any detection tick the system is provably clear again. That means
  every detection tick that finds >=1 deadlocked process at its *first*
  (pre-removal) pass is, by construction, a new no-deadlock -> deadlock
  transition. `PeriodicCheckResult.deadlock_detected` carries exactly that
  boolean.

## Metric definitions worth being explicit about

- **`avg_waiting_time`** is the mean of `waiting_times`, which contains one
  entry per request that actually passed through `PendingRequest` (i.e.
  really did wait) -- an immediate (step-4) grant is not appended to this
  list at all, rather than being appended as a `0` and diluting the
  average. The spec's "immediate grants contribute zero" is read here as
  clarifying that immediate grants don't add wait time, not as a mandate to
  average over every request including the trivial ones; this matches
  `blocked_processes` (distinct processes that *ever* waited) staying
  consistent with `avg_waiting_time` being `0.0` exactly when
  `blocked_processes` is `0` for a given run, which is what the real
  180-run experiment shows for Light under Avoidance and Detection+Recovery
  (see the summary CSV).
- **`resources_wasted`** is accumulated once per termination, from each of
  the victim's *active* holdings at that moment: `holding.resources *
  (termination_tick - holding.grant_tick)`. It is never reset across
  repeated restarts of the same process within a run -- it is a running
  total over the whole run, matching "accumulate across repeated restarts".

## Experiment/metrics/plotting flow

`SimulationResult -> ExperimentRunner -> pandas DataFrame -> Matplotlib`,
exactly as specified. `experiment/metrics.py` is the only module that turns
a `SimulationResult` into a flat dict (`SimulationResult.to_flat_dict()`,
defined in `core/result.py` for stable schema but with no pandas
dependency) and assembles the DataFrame; `experiment/plots.py` consumes that
DataFrame (via a `groupby(...).agg(["mean","std"])` summary) to produce the
8 required static PNGs. `experiment/runner.py` is pure orchestration: it
owns the seed x strategy double loop, writes raw/aggregate/summary/plots to
a timestamped directory, and is the one place `STRATEGY_FACTORIES` maps
`StrategyName -> Strategy subclass` (so both the CLI's `single-run` and the
full `experiment` command share exactly one source of truth for "how do I
build a fresh strategy instance").
