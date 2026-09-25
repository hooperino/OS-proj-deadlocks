# Implementation Status

Last updated: after adding the web dashboard (live experiments + results
exploration in the browser). This file is updated in the same commit as the
work it describes.

## Current milestone: Complete. Simulator, workload generator, experiment
## pipeline, CLI, and a full web dashboard are all implemented, tested, and
## verified end-to-end.

## Web dashboard (this session)

### What it is
A dark-themed browser dashboard (`web/`) built directly on the existing
`deadlock_sim` package -- FastAPI backend (`web/backend/`), React +
TypeScript + Tailwind v4 frontend (`web/frontend/`). Five pages: Dashboard
(KPIs + latest-experiment glance), Compare strategies (every required
metric grouped by condition, plus a normalized cost-profile radar), Run
experiment (a genuine live 180-run experiment streamed into the browser via
Server-Sent Events, not a replay), Single run (one workload/strategy, run
live, full result), Explore results (sortable/filterable table of all 180
runs, per-run drill-down, and the actual Matplotlib-generated presentation
plots). See `web/README.md` for the full architecture writeup and
`ARCHITECTURE.md`'s updated dependency diagram for where it sits.

### Design approach
Read `/mnt/skills/public/frontend-design/SKILL.md` before building and
deliberately avoided its listed generic-AI-dashboard tells: no
near-black-plus-single-neon-accent (the palette is a warm amber UI accent
plus the three strategy colors -- reused at the *exact same hex values* as
the CLI's Matplotlib plots, `#4C72B0`/`#55A868`/`#C44E52`, so the live
dashboard and the static presentation exports read as one visual system,
not two different tools); no SaaS-card-kit uniform shadows (flat panels
with hairline borders and accent-left-borders for hierarchy instead); no
ALL-CAPS/middle-dot/arrow-suffixed template chrome; two type families
(IBM Plex Sans for UI text, IBM Plex Mono for actual numeric/technical data)
chosen because the content is genuinely numeric simulation output, not
decoration. One deliberate load-time motion moment on the dashboard
(KPI count-up); the Run Experiment page's motion is earned -- it is showing
real state change (a real progress bar, a real streaming log), not
decoration.

### Why `run_experiment()` needed one small, backward-compatible addition
Live progress needs a way to observe each run as it completes without
re-implementing the seed x strategy orchestration loop in the web layer
(which would violate "build around the existing implementation" and risk
drifting out of sync). Added an optional `on_run_complete: Callable[[result,
done, total], None]` parameter, default `None` (CLI behavior byte-for-byte
unchanged). `web/backend/app/jobs.py` passes a callback that pushes each
event onto a thread-safe queue an SSE endpoint drains. Verified with a new
regression test (`test_on_run_complete_callback_fires_for_every_run_with_
correct_progress`) confirming the callback fires exactly 180 times with
strictly-increasing counters and receives results identical to what ends up
in `raw_all.json`.

### Real bugs found and fixed while building this (not just written
### correctly the first time)
1. `main.py` referenced a `jobs.run_experiment_single` helper that was
   never defined (caught immediately on first import -- fixed by using the
   existing `runner.run_single` directly).
2. Two JSDoc comments in `format.ts`/nowhere else contained a literal `*/`
   inside their text (`utilization_*/wasted_*/overhead_*`), which
   prematurely closed the comment and broke the TypeScript build. Caught by
   `npm run build`, fixed by rewording.
3. Several Recharts `Tooltip`/`Radar` `formatter` callbacks were typed
   against Recharts' newer `ValueType` (which can be `undefined`), not the
   `number` my code assumed -- caught by `tsc`, fixed with explicit
   guards/casts.
4. `AggregateRow`, originally defined as `Omit<SimulationResult,
   'waiting_times'>`, resolved every explicitly-typed field to `unknown`
   wherever it was actually used in `Explore.tsx` -- a real TypeScript
   quirk where `Omit` on a type with a string index signature loses field
   specificity. Fixed by giving `AggregateRow` its own explicit interface.
5. **A real backend security/correctness bug**: the SPA catch-all route
   (`GET /{full_path:path}`, needed so React Router's client-side paths
   like `/compare` don't 404) was declared without excluding `/api/*`, so
   an unmatched API path silently returned the HTML shell with a `200`
   instead of a `404`. Caught by an explicit curl check
   (`/api/nonexistent` -> expected 404, got 200), not by the type checker
   or the build. Fixed by checking `full_path.startswith("api/")` first.
6. A related bug found in the same pass: Vite's `public/` directory
   (`favicon.svg`, `icons.svg`) is copied to the *root* of `dist/`, not
   `dist/assets/`, so it wasn't reachable through the `/assets` static
   mount and fell through to the same catch-all, serving HTML with an
   `image/svg+xml`-expecting request returning `text/html`. Fixed by
   having the catch-all check for a real file at that path within
   `dist/` (with a path-traversal guard: `resolve()` + `startswith()`
   against the resolved dist root) before falling back to the SPA shell.
   Verified the traversal guard directly with `%2e%2e`-encoded and literal
   `../../../etc/passwd` attempts against the running server -- both
   correctly fell through to the ordinary SPA/404 behavior, never exposing
   a file outside `dist/`.
7. `jsdom` (used for the frontend component tests, see below) has no
   `Element.scrollTo`, which crashed `RunExperiment`'s auto-scroll effect
   during testing. Real defensive-coding gap either way (nothing guaranteed
   `scrollTo` exists before calling it) -- fixed with a `typeof
   el.scrollTo === 'function'` guard, which also makes the component more
   robust in any real environment that happens to lack it.

### Verification performed
No real browser was available in the build sandbox (confirmed: no working
Chromium -- the `chromium-browser` apt package is a snap stub and `snapd`
isn't available; Playwright/Puppeteer's browser-binary downloads are also
outside the sandbox's allowed network domains). Verification therefore used
every other available signal, deliberately layered rather than skipped:

- **Type safety**: `tsc -b --noEmit` clean.
- **Lint**: `oxlint` clean (0 warnings/errors across 32 files).
- **Build**: `vite build` succeeds; route-level code-splitting via
  `React.lazy` keeps the main bundle to 123KB gzipped with Recharts split
  into its own on-demand chunk.
- **Component rendering** (the best available substitute for real browser
  QA): Vitest + React Testing Library + jsdom, with the backend `api`
  module mocked to realistic fixtures matching the actual JSON shapes.
  7 tests across all 5 pages, covering both populated and empty
  (no-experiments-yet) states, a live SSE-driven run, a single-run
  request/response cycle, and table filtering/drill-down. All pass.
- **Backend, exhaustively, against a real running server** (not just
  imported): every endpoint hit with `curl` in single-shot bash sessions
  (background processes were found not to survive between separate tool
  calls in this environment, so each verification pass starts and stops
  its own server within one shell session) -- health, config, single-run
  (success and validation-error paths), experiment listing/detail/
  aggregate/raw-run/plot-file, the full POST-then-SSE-stream lifecycle
  (captured all 180 progress events plus the final `complete` event with
  correct `dir_name`), NaN-to-null JSON serialization for strategy-specific
  columns, and two path-traversal attempts against both the experiment-ID
  and static-file-serving code paths (both correctly blocked).
- **Full combined integration**: built the frontend, served it from the
  same FastAPI process as the API, and re-ran the endpoint sweep against
  that combined server -- root path serves the SPA shell, client-side
  routes (`/compare`, `/explore`, ...) fall back to the SPA shell, static
  assets (JS/CSS/favicon/icons) serve with correct content-types, `/api/*`
  routes still resolve correctly alongside the static mount, and an
  unmatched `/api/*` path now correctly 404s.
- **A complete realistic session end to end**: listed existing experiments
  -> started a brand-new live experiment via `POST` -> streamed it to
  completion over SSE -> confirmed it now appears first in the experiment
  list -> pulled its summary (and confirmed the numbers match the CLI's
  independently-verified redesign results: heavy detection_recovery
  `deadlock_episodes_mean` ~3.0, `recovery_actions_mean` ~6.0; heavy
  prevention `unnecessary_denials_mean` ~22) -> pulled its full 180-row
  aggregate -> pulled one individual raw run -> fetched one presentation
  plot -> ran a single simulation through the single-run endpoint. Every
  step used real data with no discrepancy from the CLI-verified baseline.
- Cleaned up the `results/` directory afterward to a small, meaningful set
  (the original pre-redesign baseline, the final post-redesign baseline,
  and one fresh live-web-generated run demonstrating the dashboard
  actually works) rather than leaving a dozen redundant test artifacts.

## Workload-generator redesign (prior session, unchanged this session)

### Why
The original generator (one recurring "grab-then-cross pair" template)
produced technically valid but weakly differentiated results -- under
Light, Avoidance and Detection+Recovery were indistinguishable from each
other (`avg_waiting_time == 0.0`, `unnecessary_denials == 0`, every run).

### What changed
Only `workloads/generator.py`. Replaced the single conflated pattern with
three separated, purpose-built pressure types mixed with ordinary
background processes: ordering-violation processes (Prevention pressure,
modest almost-always-available descending requests), Banker-trap groups
(Avoidance pressure, a general N-process construction guaranteeing an
available-but-unsafe state), and deadlock cycles (Detection+Recovery
pressure, varied 2-process cycles across arbitrary resource pairs plus a
genuine 3-process cycle in Heavy).

### Result (Heavy, before -> after)
throughput (prevention/avoidance/detection): 10.82/10.72/10.60 ->
9.62/8.30/9.16. `avg_waiting_time`: 12.27/30.26/8.93 -> 10.69/22.62/10.89.
`unnecessary_denials` (prevention/avoidance): 8.63/6.53 -> 22.07/22.87.
Light's Avoidance/Detection+Recovery went from exactly 0.0 waiting time and
0 denials in every single run to a real, broadly-distributed signal (18/30
seeds show it). See git history (commits around the "Redesign workload
generation" message) for the full mathematical reasoning and iteration
story.

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
`generate_heavy(101..130)`. Three separated pressure patterns (see redesign
section above) mixed with ordinary background processes.

### Phase 7: Metrics + experiment framework
`core/result.py` (`SimulationResult`, `to_flat_dict`/`to_json_dict`),
`experiment/metrics.py` (pandas aggregation + mean/std summary),
`experiment/plots.py` (8 required Matplotlib plots), `experiment/runner.py`
(`run_single`, `run_experiment`, now with an optional progress callback).

### Phase 8: CLI
`cli/main.py`: `experiment` (`--output`, `--quiet`) and `single-run`
(`--condition`, `--seed`, `--strategy`, `--output`) subcommands.

### Phase 9: Web dashboard
See above.

## Known, deliberate scope decisions (not gaps)

- No real-browser (Playwright/Selenium) screenshot verification was
  possible in this build environment (see "Verification performed" above
  for exactly what substituted for it and why each substitute is a
  meaningful check, not a shortcut).
- The web backend's in-memory job registry (`web/backend/app/jobs.py`) does
  not persist across a server restart -- an in-progress live run started
  just before a restart would be lost. This is an appropriate scope
  boundary for a local demo/coursework tool, not a production job queue;
  completed experiments are always safely on disk regardless.
- `blocked_processes`'s "instantaneous waiting counts over time" remains
  explicitly optional in the spec and unimplemented as a separate time
  series (unchanged from before this session).
- No `CHANGELOG.md` -- the spec marks it optional and git history + this
  file already give full continuity.

## Commands verified in this environment

```bash
# core project
pip install -e .
python -m pytest tests/ -q                                    # 207 passed
python -m deadlock_sim.cli.main experiment
python -m deadlock_sim.cli.main single-run --condition heavy --seed 101 --strategy detection_recovery
python -m pyflakes src/deadlock_sim tests web/backend/app      # clean

# web dashboard
pip install -r web/backend/requirements.txt
cd web/frontend && npm install
npx tsc -b --noEmit          # clean
npm run test                 # 7 passed (Vitest + RTL)
npx oxlint                   # clean
npm run build                # succeeds, dist/ produced
cd ../..
uvicorn web.backend.app.main:app --port 8000   # serves API + built frontend on one port
```

## Repository layout

```
README.md / ARCHITECTURE.md / INTEGRATION_CONTRACT.md / IMPLEMENTATION_STATUS.md
pyproject.toml / requirements.txt / .gitignore
src/deadlock_sim/   core/, strategies/, workloads/, experiment/, cli/
tests/              207 tests, all passing
web/
  README.md         web-layer-specific setup/architecture documentation
  backend/          FastAPI app (app/main.py, jobs.py, results_store.py) + requirements.txt
  frontend/         React + TypeScript + Tailwind v4 dashboard (Vite), 7 component tests
results/            a few real, meaningful pre-generated experiments (gitignored)
```

## Session update (2026-09-25)

The previous session ended mid-edit: `api.ts`'s `streamExperiment()` had
been given an optional third `onConnectionError` callback, but its only
caller, `RunExperiment.tsx`, hadn't been updated to pass one -- an SSE
connection dropping mid-run would have left the UI stuck on "Running..."
forever instead of surfacing an error state.

Fixed: `RunExperiment.tsx` now passes an `onConnectionError` callback that
sets `phase` to `'error'` with an explanatory message, mirroring the
existing `startExperiment()` `.catch()` handling just below it. Re-verified
`tsc -b --noEmit`, `npm run test` (7 passed), `oxlint` (clean), and
`npm run build` all still pass, then ran one more full live session against
the combined server -- `POST /api/experiments/run` -> streamed a real
180-run experiment over SSE to a clean `complete` event with no error --
confirming the fix didn't regress the working path. The throwaway results
directory from that test run was deleted afterward; `results/` still holds
only the three pre-existing real experiments.

There is now no known unfinished work.

## If resuming this project in a new session

There is no known unfinished work. Run `python -m pytest tests/ -q`, then
(from `web/frontend/`) `npx tsc -b --noEmit && npm run test && npm run
build`, then a quick `uvicorn web.backend.app.main:app` smoke session, to
re-confirm nothing regressed before treating any new request as an addition
to this baseline.
