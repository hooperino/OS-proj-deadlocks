"""FastAPI application for the deadlock-sim web dashboard.

This is a thin layer over the existing `deadlock_sim` package: every number
shown in the browser comes from `Simulator.run()`, `run_experiment()`, or
the on-disk output `run_experiment()` already writes. Nothing here
recomputes or reimplements simulation logic, metrics, or aggregation --
see results_store.py (reads existing CSV/JSON output) and jobs.py
(orchestrates the existing `run_experiment` via its progress hook).

Run with:  uvicorn web.backend.app.main:app --reload   (from the repo root)
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from deadlock_sim.core.config import DEFAULT_CONFIG, HEAVY_SEEDS, LIGHT_SEEDS
from deadlock_sim.core.enums import Condition, StrategyName
from deadlock_sim.experiment.runner import run_single

from . import jobs, results_store

app = FastAPI(title="Deadlock Simulation Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # local dev tool; not exposed beyond the machine running it
    allow_methods=["*"],
    allow_headers=["*"],
)

_STRATEGY_LABELS = {
    "prevention": "Prevention",
    "avoidance": "Avoidance (Banker)",
    "detection_recovery": "Detection + Recovery",
}


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/config")
def get_config():
    return {
        "resource_names": list(DEFAULT_CONFIG.resource_names),
        "capacities": list(DEFAULT_CONFIG.capacities),
        "num_processes": DEFAULT_CONFIG.num_processes,
        "detection_interval": DEFAULT_CONFIG.detection_interval,
        "max_ticks_light": DEFAULT_CONFIG.max_ticks_light,
        "max_ticks_heavy": DEFAULT_CONFIG.max_ticks_heavy,
        "light_seeds": list(LIGHT_SEEDS),
        "heavy_seeds": list(HEAVY_SEEDS),
        "strategies": [{"id": k, "label": v} for k, v in _STRATEGY_LABELS.items()],
        "total_runs": jobs.TOTAL_RUNS,
    }


@app.get("/api/single-run")
def single_run(condition: str, seed: int, strategy: str):
    if condition not in ("light", "heavy"):
        raise HTTPException(400, "condition must be 'light' or 'heavy'")
    if strategy not in _STRATEGY_LABELS:
        raise HTTPException(400, f"strategy must be one of {list(_STRATEGY_LABELS)}")
    cond = Condition.LIGHT if condition == "light" else Condition.HEAVY
    result = run_single(cond, seed, StrategyName(strategy))
    return result.to_json_dict()


@app.get("/api/experiments")
def list_experiments():
    return results_store.list_experiments()


@app.get("/api/experiments/{experiment_id}")
def experiment_summary(experiment_id: str):
    try:
        return results_store.get_summary(experiment_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "experiment not found")


@app.get("/api/experiments/{experiment_id}/aggregate")
def experiment_aggregate(experiment_id: str):
    try:
        return results_store.get_aggregate(experiment_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "experiment not found")


@app.get("/api/experiments/{experiment_id}/raw/{condition}/{seed}/{strategy}")
def experiment_raw_run(experiment_id: str, condition: str, seed: int, strategy: str):
    try:
        return results_store.get_raw_run(experiment_id, condition, seed, strategy)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "run not found")


@app.get("/api/experiments/{experiment_id}/plots/{filename}")
def experiment_plot(experiment_id: str, filename: str):
    try:
        path = results_store.get_plot_path(experiment_id, filename)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "plot not found")
    return FileResponse(path, media_type="image/png")


@app.post("/api/experiments/run")
def start_experiment_run():
    job = jobs.start_job()
    return {"job_id": job.job_id, "total": job.total}


@app.get("/api/experiments/run/{job_id}/stream")
async def stream_experiment_run(job_id: str):
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(404, "job not found")

    async def event_source():
        loop = asyncio.get_event_loop()
        while True:
            item = await loop.run_in_executor(None, job.queue.get)
            yield f"data: {json.dumps(item)}\n\n"
            if item.get("event") == "complete":
                break

    return StreamingResponse(event_source(), media_type="text/event-stream")


# --- Serve the built frontend (production: `npm run build` -> dist/) ---
_FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"

if _FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        # An unmatched /api/* path is a genuine 404, not a frontend route,
        # and must not be swallowed by this catch-all.
        if full_path.startswith("api/"):
            raise HTTPException(404, "not found")
        # A real file at the dist root (favicon.svg, icons.svg, etc. --
        # anything Vite's public/ directory copies there) is served
        # directly. Everything else is a client-side (React Router) route:
        # always serve the SPA shell and let the frontend router resolve it.
        candidate = (_FRONTEND_DIST / full_path).resolve()
        if (
            full_path
            and str(candidate).startswith(str(_FRONTEND_DIST.resolve()))
            and candidate.is_file()
        ):
            return FileResponse(candidate)
        index = _FRONTEND_DIST / "index.html"
        if not index.exists():
            raise HTTPException(404)
        return HTMLResponse(index.read_text())
