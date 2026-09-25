"""Reads already-written experiment output directories (the same
`results/experiment_<timestamp>/` layout `run_experiment` has always
produced: aggregate.csv, summary.csv, raw_all.json, raw/*.json,
run_report.txt, plots/*.png). Whether a directory was produced by the CLI
or by a live web-triggered run makes no difference here -- they share one
format, so this module is the single reader for both.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

import pandas as pd

from .jobs import RESULTS_DIR

_DIR_RE = re.compile(r"^experiment_(\d{8})_(\d{6})$")


def _parse_timestamp(dir_name: str) -> Optional[str]:
    m = _DIR_RE.match(dir_name)
    if not m:
        return None
    date_part, time_part = m.groups()
    return (
        f"{date_part[0:4]}-{date_part[4:6]}-{date_part[6:8]}"
        f"T{time_part[0:2]}:{time_part[2:4]}:{time_part[4:6]}"
    )


def _df_to_records(df: pd.DataFrame) -> list:
    # pandas' own to_json turns NaN into null correctly; json.dumps on a
    # raw .to_dict() would choke on NaN, which every strategy-specific
    # overhead/utilization column legitimately contains for other strategies.
    return json.loads(df.to_json(orient="records"))


def list_experiments() -> list:
    if not RESULTS_DIR.exists():
        return []
    entries = []
    for d in sorted(RESULTS_DIR.iterdir(), reverse=True):
        if not d.is_dir():
            continue
        timestamp = _parse_timestamp(d.name)
        if timestamp is None:
            continue
        report_path = d / "run_report.txt"
        total_runs = incomplete_runs = None
        if report_path.exists():
            text = report_path.read_text()
            total_match = re.search(r"Total runs:\s*(\d+)", text)
            incomplete_match = re.search(r"Incomplete runs:\s*(\d+)", text)
            total_runs = int(total_match.group(1)) if total_match else None
            incomplete_runs = int(incomplete_match.group(1)) if incomplete_match else None
        has_summary = (d / "summary.csv").exists()
        if not has_summary:
            continue  # a job still in progress (or one that failed early) -- not browsable yet
        entries.append(
            {
                "id": d.name,
                "timestamp": timestamp,
                "total_runs": total_runs,
                "incomplete_runs": incomplete_runs,
            }
        )
    return entries


def _experiment_dir(experiment_id: str) -> Path:
    # experiment_id is validated against the exact directory-name pattern
    # before ever touching the filesystem, so this can't escape RESULTS_DIR.
    if not _DIR_RE.match(experiment_id):
        raise ValueError("invalid experiment id")
    return RESULTS_DIR / experiment_id


def get_summary(experiment_id: str) -> dict:
    d = _experiment_dir(experiment_id)
    summary_path = d / "summary.csv"
    if not summary_path.exists():
        raise FileNotFoundError(experiment_id)
    summary = _df_to_records(pd.read_csv(summary_path))
    return {"id": experiment_id, "timestamp": _parse_timestamp(experiment_id), "summary": summary}


def get_aggregate(experiment_id: str) -> list:
    d = _experiment_dir(experiment_id)
    path = d / "aggregate.csv"
    if not path.exists():
        raise FileNotFoundError(experiment_id)
    return _df_to_records(pd.read_csv(path))


def get_raw_run(experiment_id: str, condition: str, seed: int, strategy: str) -> dict:
    d = _experiment_dir(experiment_id)
    path = d / "raw" / f"{condition}_seed{seed}_{strategy}.json"
    if not path.exists():
        raise FileNotFoundError(str(path))
    return json.loads(path.read_text())


def get_plot_path(experiment_id: str, filename: str) -> Path:
    d = _experiment_dir(experiment_id)
    # filename must be a bare name (no path traversal) and must exist among
    # the plots this experiment actually generated.
    if "/" in filename or "\\" in filename or not filename.endswith(".png"):
        raise ValueError("invalid plot filename")
    path = (d / "plots" / filename).resolve()
    if not str(path).startswith(str((d / "plots").resolve())) or not path.exists():
        raise FileNotFoundError(filename)
    return path
