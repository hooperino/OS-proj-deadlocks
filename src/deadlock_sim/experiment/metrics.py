"""Aggregation of raw per-run results into tabular form.

This module is the only place in the project that imports pandas -- the
core simulation layer stays free of it (see ARCHITECTURE.md).
"""

from __future__ import annotations

from typing import List

import pandas as pd

from deadlock_sim.core.result import SimulationResult

_GROUP_COLS = ["condition", "strategy"]
_NON_NUMERIC_COLS = _GROUP_COLS + ["seed", "status"]


def results_to_dataframe(results: List[SimulationResult]) -> pd.DataFrame:
    """One row per run -- the full "raw individual results" / aggregate CSV
    table, with strategy-specific overhead_* / per-resource columns filled
    with NaN for strategies where they don't apply."""
    return pd.DataFrame([r.to_flat_dict() for r in results])


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    """Group by (condition, strategy); mean +/- standard deviation for every
    numeric column, plus a run count for sanity-checking completeness."""
    numeric_cols = [c for c in df.columns if c not in _NON_NUMERIC_COLS]
    grouped = df.groupby(_GROUP_COLS, sort=False)
    agg = grouped[numeric_cols].agg(["mean", "std"])
    agg.columns = [f"{col}_{stat}" for col, stat in agg.columns]
    agg = agg.reset_index()
    counts = grouped.size().reset_index(name="n_runs")
    return agg.merge(counts, on=_GROUP_COLS)
