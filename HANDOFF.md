# Handoff

Short pointer document for the next session. Full detail lives in
`IMPLEMENTATION_STATUS.md`, `ARCHITECTURE.md`, `INTEGRATION_CONTRACT.md`,
`README.md`, `web/README.md`, and git history -- read those, don't ask the
user to re-explain the project.

## Current implementation state

Core simulator, strategies, workload generator, experiment pipeline, CLI,
and full pytest suite (207 tests) are complete, tested, and committed
(see git log up to `b8c8ead`). A full web dashboard (`web/`, FastAPI +
React/TypeScript/Tailwind) has been built on top of it this session and is
functionally complete and passing every automated check; it is committed
as a work-in-progress checkpoint (see the most recent commit) with one
small item left mid-edit, described below.

Right now, as of this exact moment:
- `python -m pytest tests/ -q` -> 207 passed
- `cd web/frontend && npx tsc -b --noEmit` -> clean
- `npx vitest run` -> 7 passed
- `npx oxlint` -> clean
- `npm run build` -> succeeds

## What was completed this session

- Built `web/backend/` (FastAPI: config, single-run, experiment
  listing/detail/aggregate/raw-run/plot endpoints, POST-to-start +
  SSE-stream live experiment runs) and `web/frontend/` (5 pages: Dashboard,
  Compare, Run experiment, Single run, Explore) -- see `web/README.md`.
- Added an optional `on_run_complete` callback to
  `deadlock_sim.experiment.runner.run_experiment` (backward-compatible,
  tested) so the web backend can stream real progress without
  reimplementing the run loop.
- Verified everything exhaustively given no real browser was available in
  this sandbox: full curl/SSE sessions against a running server (including
  security checks -- path traversal, `/api/*` 404 handling), Vitest +
  React Testing Library component smoke tests, and a genuine (if
  ultimately unsuccessful past ES5) attempt to get real pixel screenshots
  via `wkhtmltoimage` -- documented in `IMPLEMENTATION_STATUS.md` under
  "Verification performed."
- Fixed several real bugs found along the way (SPA catch-all swallowing
  unmatched `/api/*` 404s, favicon/static files not resolving, a
  `Omit<...>` TypeScript quirk, JSDoc comment closing early, etc.) --
  full list in `IMPLEMENTATION_STATUS.md`.
- Updated `README.md`, `ARCHITECTURE.md`, `INTEGRATION_CONTRACT.md`,
  `IMPLEMENTATION_STATUS.md` for the web layer.

## What is currently being worked on (incomplete, mid-edit)

Improving SSE robustness in the Run Experiment page: if the live-progress
connection drops before a `complete` event arrives, the UI should show an
error instead of appearing stuck on "Running...". `streamExperiment()` in
`web/frontend/src/lib/api.ts` was already updated to accept and call an
`onConnectionError` callback -- **but `web/frontend/src/pages/
RunExperiment.tsx` has not been updated to pass that callback yet.** This
is the very next thing to do (see below). It's a small, additive, low-risk
change; nothing is broken in the meantime (the app works correctly, it
just won't surface this one specific failure mode yet).

## Known issues / blockers

None that block progress. The only open item is the incomplete wiring
above. No failing tests, no broken builds.

## Exact next steps

1. In `RunExperiment.tsx`, find `stopRef.current = streamExperiment(job_id, (evt) => { ... })`
   and add a third argument -- an `onConnectionError` handler that sets
   `phase` to `'error'` and `error` to a clear message (mirror the
   existing `catch` block a few lines below it that handles
   `startExperiment()` failing).
2. Rebuild/retest: `npx tsc -b --noEmit && npx vitest run && npm run
   build` (all currently pass; confirm they still do).
3. Do one more full end-to-end curl/SSE session against a running combined
   server (pattern is in `IMPLEMENTATION_STATUS.md`'s "Verification
   performed" section) to sanity-check nothing regressed.
4. Update `IMPLEMENTATION_STATUS.md` (remove this item from "being worked
   on", fold it into "what was completed"), commit everything in `web/`
   (it's all staged already -- just needs a commit message), and re-check
   `results/` doesn't have test clutter accumulated during this session's
   verification.
5. Package the final repository as a ZIP (see "Final completion
   requirements" below) and deliver it.

After that: there is no other known unfinished work. Treat any further
request as new scope on top of a complete baseline.

## Important files/directories to inspect first

- `IMPLEMENTATION_STATUS.md` -- the authoritative, detailed project log.
  Read this fully before doing anything else.
- `web/frontend/src/pages/RunExperiment.tsx` and `web/frontend/src/lib/
  api.ts` -- the two files involved in the incomplete item above.
- `web/README.md` -- how to run/test the web dashboard (dev mode and
  production/single-port mode).
- `git status` / `git diff --stat` -- confirms the entire `web/` tree is
  new, staged, uncommitted work from this session.

## Commands to run first

```bash
cd /path/to/repo
python -m pytest tests/ -q                 # expect 207 passed
cd web/frontend
npx tsc -b --noEmit                        # expect clean
npx vitest run                             # expect 7 passed
npx oxlint                                 # expect clean
npm run build                              # expect success
```

## Final completion requirements

Per the master project requirements already recorded in
`IMPLEMENTATION_STATUS.md`: full pytest suite green, full 180-run
experiment actually executed and inspected, web dashboard functionally
complete and verified, all docs current, repository clean and committed.
**The very last step of any session that reaches a fully-verified state is
to package the complete repository (source, docs, config, the built
`web/frontend/dist/`, and a small set of real `results/` data -- not
`node_modules/`, not `.git/`) into a downloadable ZIP and deliver it.** Do
not consider the work "done" until that ZIP exists and has been handed to
the user.
