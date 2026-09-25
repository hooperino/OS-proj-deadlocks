# Deadlock Lab -- web dashboard

A dark-themed dashboard for running the deadlock experiments live and
exploring their results in the browser, built directly on top of the
`deadlock_sim` package documented in the repository root. It does not
reimplement, duplicate, or approximate any simulation or metric logic --
every number shown in the browser is produced by the same `Simulator`,
`run_experiment`, and `SimulationResult` the CLI uses.

```
web/
  backend/    FastAPI app -- thin HTTP/SSE layer over deadlock_sim
  frontend/   React + TypeScript + Tailwind dashboard (Vite)
```

## Quick start (production-style: one process, one port)

```bash
# from the repository root
pip install -e .                            # the deadlock_sim package itself
pip install -r web/backend/requirements.txt  # fastapi + uvicorn

cd web/frontend
npm install
npm run build                                # writes web/frontend/dist/

cd ../..
uvicorn web.backend.app.main:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000` -- the FastAPI app serves both the API
(`/api/*`) and the built frontend from one process. This repository already
ships a built `web/frontend/dist/` and a few real experiment results under
`results/`, so this works immediately without a fresh `npm run build` if you
just want to look around; rebuild after any frontend source change.

## Development mode (hot reload)

Run the two dev servers side by side (Vite's dev server proxies `/api/*` to
FastAPI -- see `web/frontend/vite.config.ts`):

```bash
# terminal 1
uvicorn web.backend.app.main:app --reload --port 8123

# terminal 2
cd web/frontend
npm install
npm run dev
```

Open the URL Vite prints (typically `http://localhost:5173`).

## What the backend actually does

`web/backend/app/main.py` is a thin FastAPI layer:

- `GET /api/config` -- static config (resource names/capacities, seed
  ranges, strategy list) read straight from `SimulationConfig`.
- `GET /api/single-run` -- calls `deadlock_sim.experiment.runner.run_single`
  and returns `SimulationResult.to_json_dict()`.
- `GET /api/experiments` / `/api/experiments/{id}` /
  `/api/experiments/{id}/aggregate` / `/api/experiments/{id}/raw/...` --
  read the exact `results/experiment_<timestamp>/` output
  `run_experiment()` has always produced (`web/backend/app/results_store.py`
  is the only reader; whether a directory came from the CLI or a live
  web-triggered run makes no difference).
- `POST /api/experiments/run` + `GET /api/experiments/run/{job_id}/stream`
  -- starts `run_experiment()` in a background thread and streams its
  genuine per-run progress to the browser over Server-Sent Events, via the
  `on_run_complete` callback hook added to `run_experiment()` for exactly
  this purpose (see `deadlock_sim/experiment/runner.py` and
  `web/backend/app/jobs.py`). The only artificial element anywhere in this
  path is a ~15ms pacing delay between forwarded events, purely so 180
  near-instant simulations are visible as genuine, individually-reported
  progress in the UI rather than a single flash -- it changes nothing about
  the simulation, timing, or results themselves.

## What the frontend actually does

`web/frontend/src/lib/api.ts` is the only place HTTP calls are made; every
page reads real data through it (or through `EventSource` for live runs)
and renders it with Recharts. No page hardcodes, precomputes, or fakes a
metric -- utilization breakdowns, algorithm-overhead counters, and
per-resource figures are all read dynamically by key prefix
(`utilization_*`, `overhead_*`, `wasted_*`) from whatever the backend
actually returns for that strategy, since the exact set of those columns is
strategy-specific.

Pages: Dashboard (KPIs + latest-experiment glance), Compare strategies
(every required metric, grouped by condition, plus a normalized cost-profile
radar), Run experiment (live SSE-driven progress with a per-strategy running
tally and log feed), Single run (one workload/strategy, run live, full
result), Explore results (sortable/filterable table of all 180 runs, a
run-detail drill-down, and the actual Matplotlib-generated presentation
plots the CLI produces).

## Testing

```bash
cd web/frontend
npx tsc -b --noEmit   # typecheck
npm run test          # Vitest + React Testing Library component smoke tests
npx oxlint             # lint
npm run build          # production build
```

The backend has no separate test file of its own -- it is a thin,
directly-inspectable pass-through over `deadlock_sim`, which already has its
own full pytest suite at the repository root (`python -m pytest tests/ -q`,
including a test for the `on_run_complete` callback the web layer depends
on). It was verified end-to-end for this project with `curl`/SSE sessions
against a running server rather than a dedicated test file, since no
real browser was available in the build environment -- see
`IMPLEMENTATION_STATUS.md` for exactly what was exercised.
