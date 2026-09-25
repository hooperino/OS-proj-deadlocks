"""In-memory registry of live ('run now, watch it happen') experiment jobs.

Each job runs `deadlock_sim.experiment.runner.run_experiment` in a
background thread and pushes progress events onto a thread-safe queue,
which an SSE endpoint in main.py drains and forwards to the browser. No
simulation logic lives here -- this module only orchestrates the existing
`run_experiment` (via its `on_run_complete` hook) and reports what it does.
"""

from __future__ import annotations

import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

from deadlock_sim.core.config import DEFAULT_CONFIG
from deadlock_sim.core.result import SimulationResult
from deadlock_sim.experiment.runner import TOTAL_RUNS, run_experiment

# Purely a UI-pacing choice so 180 near-instant runs are visible as genuine,
# individually-reported progress rather than a single flash -- it does not
# alter any simulation, timing, or result data, only how fast already-
# computed events are forwarded to the browser.
_EVENT_PACING_SECONDS = 0.015

RESULTS_DIR = Path(__file__).resolve().parents[3] / "results"


@dataclass
class ExperimentJob:
    job_id: str
    queue: "queue.Queue[dict]" = field(default_factory=queue.Queue)
    done: int = 0
    total: int = TOTAL_RUNS
    finished: bool = False
    output_dir_name: Optional[str] = None
    error: Optional[str] = None


_jobs: Dict[str, ExperimentJob] = {}
_lock = threading.Lock()


def start_job() -> ExperimentJob:
    job_id = uuid.uuid4().hex[:12]
    job = ExperimentJob(job_id=job_id)
    with _lock:
        _jobs[job_id] = job

    def _on_run_complete(result: SimulationResult, done: int, total: int) -> None:
        job.done = done
        job.total = total
        job.queue.put(
            {
                "event": "progress",
                "done": done,
                "total": total,
                "condition": result.condition.value,
                "seed": result.seed,
                "strategy": result.strategy.value,
                "status": result.status.value,
                "deadlock_episodes": result.deadlock_episodes,
                "recovery_actions": result.recovery_actions,
                "unnecessary_denials": result.unnecessary_denials,
                "throughput": result.throughput,
            }
        )
        time.sleep(_EVENT_PACING_SECONDS)

    def _run() -> None:
        try:
            out_dir = run_experiment(
                output_root=RESULTS_DIR,
                config=DEFAULT_CONFIG,
                progress=False,
                on_run_complete=_on_run_complete,
            )
            job.output_dir_name = out_dir.name
        except Exception as exc:  # surfaced to the client, not swallowed
            job.error = str(exc)
        finally:
            job.finished = True
            job.queue.put({"event": "complete", "dir_name": job.output_dir_name, "error": job.error})

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return job


def get_job(job_id: str) -> Optional[ExperimentJob]:
    with _lock:
        return _jobs.get(job_id)
