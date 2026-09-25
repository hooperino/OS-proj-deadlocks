"""Static Matplotlib plots for the experiment pipeline.

Every plot is saved to disk (never plt.show()), has a title, axis labels,
and a legend. All plots compare the three strategies grouped by condition,
using the mean +/- standard deviation computed in metrics.summarize.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from deadlock_sim.experiment import metrics

_STRATEGIES = ["prevention", "avoidance", "detection_recovery"]
_STRATEGY_LABELS = {
    "prevention": "Prevention",
    "avoidance": "Avoidance (Banker)",
    "detection_recovery": "Detection+Recovery",
}
_CONDITIONS = ["light", "heavy"]
_COLORS = {"prevention": "#4C72B0", "avoidance": "#55A868", "detection_recovery": "#C44E52"}


def _grouped_bar(summary: pd.DataFrame, mean_col: str, title: str, ylabel: str, out_path: Path) -> None:
    std_col = mean_col.replace("_mean", "_std")
    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(_CONDITIONS))
    width = 0.25
    for i, strat in enumerate(_STRATEGIES):
        means, stds = [], []
        for cond in _CONDITIONS:
            row = summary[(summary["condition"] == cond) & (summary["strategy"] == strat)]
            means.append(float(row[mean_col].values[0]) if len(row) else 0.0)
            std_val = float(row[std_col].values[0]) if len(row) and std_col in row.columns else 0.0
            stds.append(0.0 if pd.isna(std_val) else std_val)
        ax.bar(
            x + (i - 1) * width,
            means,
            width,
            yerr=stds,
            label=_STRATEGY_LABELS[strat],
            color=_COLORS[strat],
            capsize=4,
        )
    ax.set_xticks(x)
    ax.set_xticklabels([c.capitalize() for c in _CONDITIONS])
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def generate_all_plots(df: pd.DataFrame, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = metrics.summarize(df)

    _grouped_bar(
        summary, "throughput_mean", "Throughput by Strategy and Condition",
        "Useful work completed / tick", out_dir / "throughput.png",
    )
    _grouped_bar(
        summary, "avg_waiting_time_mean", "Average Waiting Time by Strategy and Condition",
        "Ticks", out_dir / "avg_waiting_time.png",
    )
    _grouped_bar(
        summary, "overall_utilization_mean", "Resource Utilization by Strategy and Condition",
        "Utilization (fraction of capacity x time)", out_dir / "resource_utilization.png",
    )
    _grouped_bar(
        summary, "blocked_processes_mean", "Blocked Processes by Strategy and Condition",
        "Distinct processes that ever waited", out_dir / "blocked_processes.png",
    )
    _grouped_bar(
        summary, "deadlock_episodes_mean", "Deadlock Episodes by Strategy and Condition",
        "Episodes (no-deadlock -> deadlock transitions)", out_dir / "deadlock_episodes.png",
    )
    _grouped_bar(
        summary, "recovery_actions_mean", "Recovery Cost (Victim Terminations) by Strategy and Condition",
        "Recovery actions", out_dir / "recovery_cost.png",
    )
    _grouped_bar(
        summary, "useful_work_lost_mean", "Useful Work Lost to Recovery by Strategy and Condition",
        "Work units lost", out_dir / "useful_work_lost.png",
    )
    _grouped_bar(
        summary, "distinct_restarted_processes_mean", "Terminated/Restarted Processes by Strategy and Condition",
        "Distinct processes restarted at least once", out_dir / "terminated_restarted_processes.png",
    )
