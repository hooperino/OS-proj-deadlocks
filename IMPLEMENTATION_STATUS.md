# Implementation Status

Last updated: after the workload-generator redesign (differentiation pass).
This file is updated in the same commit as the work it describes.

## Current milestone: Complete. Workload generator redesigned for strong,
## legitimate strategy differentiation; all guarantees re-verified; full
## 180-run experiment re-executed and compared against prior results.

## Workload-generator redesign (this session)

### Why
The original generator (one recurring "grab-then-cross" pair template,
shared across all strategic pressure) produced technically valid but weakly
differentiated results. Inspecting the prior 180-run CSV showed the real
weaknesses concretely: under Light, Avoidance and Detection+Recovery were
*indistinguishable* from each other (`avg_waiting_time == 0.0`,
`unnecessary_denials == 0` for both, every run) -- the workload never
created enough pressure for Banker's safety check to ever refuse anything.
Under Heavy, Prevention's and Avoidance's `unnecessary_denials` were close
in magnitude (8.6 vs 6.5) for the same underlying reason: the single pair
template's "unnecessary denials" were mostly artifacts of raw two-party
resource overflow, not a clean demonstration of Banker's unique
available-but-unsafe refusal.

### What changed
Only `workloads/generator.py` -- the core simulator, strategies, metrics
definitions, and experiment framework were not touched (confirmed via
`git diff --stat` before/after: one file changed). Replaced the single
conflated pattern with three separate, purpose-built pressure types, mixed
with plain ordinary background processes (see the module docstring in
`workloads/generator.py` for the full mathematical reasoning):

1. **Ordering-violation processes** -- a lone process holds a higher-ranked
   resource then requests a *modest* (15-25% of capacity, well under the
   intensity cap) amount of a lower-ranked one, so the resulting Prevention
   WAIT is almost always attributable to policy, not scarcity.
2. **Banker-trap groups** -- N processes claim one resource sized (per-
   process cap M = floor(capacity * intensity_cap)) so that after N-1
   modest initial grabs, the last process's request is *currently
   available* but leaves Available at exactly 0 with every process's Need
   still positive -- the textbook unsafe state, solved generally for any
   resource/group-size combination (feasibility-checked; infeasible
   combinations are skipped rather than silently producing a broken
   pattern).
3. **Deadlock cycles** -- varied 2-process cycles (an arbitrary resource
   pair each time, not just adjacent ranks) plus a genuine 3-process cycle
   in Heavy (P0 holds A wants B, P1 holds B wants C, P2 holds C wants A),
   reusing the same bilateral-overflow sizing that guarantees a real cyclic
   wait under Heavy's 70% cap.

Per-condition pid budget (`_plan_for`): Light = 4 (one Banker-trap group) +
2 (one 2-cycle) + 3 (ordering-violation) + 11 background = 20. Heavy = 6
(two Banker-trap groups) + 4 (two 2-cycles) + 3 (one 3-cycle) + 5
(ordering-violation) + 2 background = 20. Every pid still gets ordinary
padding activity on resources its structured pattern doesn't use, so no
process is purely a single-purpose adversarial construct.

### Two real bugs found and fixed during this redesign
1. **Request-count-range violation**: `_build_incremental_requests`'s old
   random per-draw splitting could exhaust a claimed resource's remaining
   budget before reaching the target number of REQUEST events, silently
   undershooting the locked 3-5 (Light) / 6-8 (Heavy) range (caught by pid
   9 in a Light seed having only 2 requests). This was a latent gap in the
   *original* generator too -- the original test suite never explicitly
   checked exact request-count bounds. Fixed by rewriting the split to be
   deterministic-by-construction (`_split_into_parts`, exact positive-
   integer partition) with an explicit top-up (claim more eligible
   resources, capped at 4 claimed) when the initial claim can't support
   enough >=1-unit chunks. Verified 0 violations across all 60 seeds x 20
   processes = 1200 processes after the fix.
2. **Banker-trap requester starvation**: the excess-reduction step could
   zero out the *requester's own* allocation (the one whose tentative
   grant is actually evaluated), silently turning the "available but
   unsafe" scenario into a trivial zero-resource grant that tests nothing.
   Caught by a new white-box test
   (`test_banker_trap_group_is_mathematically_available_but_unsafe`).
   Fixed by reducing non-requester allocations first, only touching the
   requester's allocation as an absolute last resort, and returning `None`
   (feasibility failure, caller tries a different resource) if the
   requester would end up with nothing meaningful to request.

### Validation performed
- Structural: all 60 seeds re-validated (20 processes, total_work 50-150,
  >=1 REQUEST and RELEASE per process, chronological events, unique global
  sequence numbers, cumulative requests never exceed `max_claim`, claim
  intensity within the 40%/70% caps, **and now also the exact 3-5/6-8
  request-count range** -- the gap the first bug above closed).
- Determinism: unchanged, still verified (same seed+condition -> identical
  `Workload`).
- Behavioral guarantees re-run after every change: 0 incomplete runs across
  all 180 (seed, strategy) combinations; all 30 Heavy seeds still guarantee
  >=1 genuine detected-and-recovered deadlock episode under
  Detection+Recovery; no runaway restart loops (max restarts observed: 6,
  vs the 750+ seen once during the original build before the detection
  false-positive fix).
- New pattern-specific tests added to `tests/test_workload_generator.py`:
  the Banker-trap math invariant directly; the ordering-violation's
  descending-rank + modest-amount property directly; four representative
  Heavy seeds each checked for the "clean attribution" property (Prevention
  and Avoidance show `unnecessary_denials > 0` with `deadlock_episodes ==
  0`; Detection+Recovery shows `deadlock_episodes >= 1` with
  `unnecessary_denials == 0`); resource-combination variety across seeds
  (not the same pair/triple every time); heterogeneity (background pids
  exist, every pid assigned exactly one role); and a regression guard for
  the headline finding (Heavy Avoidance's average wait exceeds Prevention's
  by >30% on a representative seed subset). **206 tests total, 0 failed.**
- Full 180-run experiment executed three times during this redesign
  (initial redesign, after rebalancing Heavy's cycle count back up, after
  the Banker-trap requester fix) -- inspected the actual summary CSV and
  plot images after each run, not just exit codes.

### Resulting experiment behavior (before -> after, Heavy)

| metric (mean) | before | after |
|---|---|---|
| throughput: prevention / avoidance / detection | 10.82 / 10.72 / 10.60 | 9.62 / 8.30 / 9.16 |
| avg_waiting_time: prevention / avoidance / detection | 12.27 / 30.26 / 8.93 | 10.69 / 22.62 / 10.89 |
| unnecessary_denials: prevention / avoidance | 8.63 / 6.53 | 22.07 / 22.87 |
| deadlock_episodes / recovery_actions / work_lost (detection) | 3.23 / 5.97 / 59.8 | 3.03 / 6.03 / 53.8 |

And, the headline fix -- Light, avoidance / detection_recovery:

| metric (mean) | before | after |
|---|---|---|
| avg_waiting_time | 0.0 / 0.0 | 2.29 / 1.59 |
| unnecessary_denials | 0.0 / 0.0 | 0.73 / 0.0 |

Light's Avoidance now shows a real, broadly-distributed (not a 1-seed
fluke) signal: 18/30 seeds show >=1 unnecessary denial. Heavy's three
strategies are now cleanly separated on *multiple, mechanism-distinct*
dimensions simultaneously: Prevention and Avoidance both show strong,
comparable-magnitude `unnecessary_denials` (driven by different
mechanisms -- ordering vs. safety) but are clearly told apart by
`avg_waiting_time` (Avoidance's conservative refusals cost more than 2x
Prevention's wait time) and by throughput (Avoidance pays the most,
Prevention and Detection+Recovery close to each other); Detection+Recovery
alone shows nonzero `deadlock_episodes`/`recovery_actions`/`useful_work_lost`
and is the only strategy with exactly zero `unnecessary_denials` -- it
never preemptively refuses anything, it just cleans up after the fact.
This is judged a genuinely stronger, more legitimate, and more defensible
separation than the original design, caused entirely by workload structure
(the simulator/strategies/metrics code is byte-for-byte unchanged this
session).

## What's complete and verified (full project)

### Phase 1-2: Foundation + core engine
`core/`: `SimulationConfig` (immutable), `Process`, `ResourcePool`,
`Holding`, `PendingRequest`, `SimulationState`, `Workload`/`ProcessWorkload`
(schema), `RequestEvent`/`ReleaseEvent`, `Strategy` ABC +
`RequestEvaluation`/`TerminateVictimAction`/`PeriodicCheckResult`,
`SimulationResult`, and `core/simulator.py` (the locked 7-step tick loop,
holding timers, FCFS pending reconsideration, restart/replay via
generation-tagged event heap).

### Phase 3-5: Strategies
Prevention (resource ordering), Banker Avoidance (safety algorithm against
local read-only copies), Detection+Recovery (matrix detection + victim loop
computed locally, applied by the Simulator). All three implement the common
`Strategy` interface and never mutate `SimulationState`.

### Phase 6: Workload generation
`workloads/generator.py`: deterministic `generate_light(1..30)` /
`generate_heavy(101..130)`. Three separated pressure patterns (ordering-
violation, Banker-trap, deadlock cycles) mixed with ordinary background
processes -- see the redesign section above for the full story.

### Phase 7: Metrics + experiment framework
`core/result.py` (`SimulationResult`, `to_flat_dict`/`to_json_dict`),
`experiment/metrics.py` (pandas aggregation + mean/std summary),
`experiment/plots.py` (8 required Matplotlib plots), `experiment/runner.py`
(`run_single`, `run_experiment`).

### Phase 8: CLI
`cli/main.py`: `experiment` (`--output`, `--quiet`) and `single-run`
(`--condition`, `--seed`, `--strategy`, `--output`) subcommands.

### Phase 9: Final verification
- `pyflakes` clean across `src/` and `tests/`.
- Every dict/set iteration audited for order-sensitivity -- deterministic
  order via explicit `sorted()` wherever it matters.
- CLI manually exercised (found + fixed a `--output` parent-directory bug).
- Every metric formula re-derived against Master Prompt section 18.
- No TODO/FIXME/stub markers, no dead code.
- `git ls-files` contains only real source.

## Known, deliberate scope decisions (not gaps)

- `blocked_processes`'s "instantaneous waiting counts over time" is
  explicitly optional in the spec ("where useful") and is not implemented
  as a separate time series -- `waiting_times` + `avg_waiting_time` already
  capture the substantive metric.
- A structured-pattern process's padding activity can occasionally not
  fully realize every increment for an unlucky (small) `total_work` draw.
  Soft/graceful (the simulator discards not-yet-reached events for a
  since-completed process), not a correctness bug -- and no longer affects
  the *request-count range itself*, which is now guaranteed exactly (see
  the redesign section).
- No `CHANGELOG.md` -- the spec marks it optional and git history + this
  file already give full continuity.

## Commands verified in this environment

```bash
pip install -e .
python -m pytest tests/ -q                                    # 206 passed
python -m deadlock_sim.cli.main experiment                    # full 180-run experiment
python -m deadlock_sim.cli.main experiment --output DIR --quiet
python -m deadlock_sim.cli.main single-run --condition heavy --seed 101 --strategy detection_recovery
python -m deadlock_sim.cli.main single-run --condition light --seed 5 --strategy avoidance --output result.json
python -m pyflakes src/deadlock_sim tests                     # clean
```

## Repository layout

```
README.md / ARCHITECTURE.md / INTEGRATION_CONTRACT.md / IMPLEMENTATION_STATUS.md
pyproject.toml / requirements.txt / .gitignore
src/deadlock_sim/
  core/        config, process, resources, holdings, state, events, workload
               schema, actions/Strategy ABC, result, simulator
  strategies/  prevention.py, banker.py, detection_recovery.py
  workloads/   generator.py (Light/Heavy -- 3-pattern redesign)
  experiment/  metrics.py, plots.py, runner.py
  cli/         main.py
tests/         206 tests, all passing
```

## If resuming this project in a new session

There is no known unfinished work. Run `python -m pytest tests/ -q` and
`python -m deadlock_sim.cli.main experiment` to re-confirm nothing
regressed, then treat any *new* request as an addition to this baseline.
If asked to further tune workload differentiation, read the redesign
section above first -- it records the exact mathematical constructions in
use and the before/after numbers, so further iteration can build on this
rather than rediscovering it.
