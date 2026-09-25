import json

import pandas as pd

from deadlock_sim.core.config import DEFAULT_CONFIG
from deadlock_sim.core.enums import Condition, RunStatus, StrategyName
from deadlock_sim.experiment import metrics, plots
from deadlock_sim.experiment.runner import TOTAL_RUNS, run_experiment, run_single


def test_run_single_matches_direct_simulator_call():
    result = run_single(Condition.LIGHT, 5, StrategyName.PREVENTION)
    assert result.status == RunStatus.COMPLETE
    assert result.condition == Condition.LIGHT
    assert result.seed == 5
    assert result.strategy == StrategyName.PREVENTION


def test_metrics_dataframe_and_summary_shape():
    results = [
        run_single(Condition.LIGHT, 1, StrategyName.PREVENTION),
        run_single(Condition.LIGHT, 1, StrategyName.AVOIDANCE),
        run_single(Condition.HEAVY, 101, StrategyName.DETECTION_RECOVERY),
    ]
    df = metrics.results_to_dataframe(results)
    assert len(df) == 3
    assert "throughput" in df.columns
    assert "overhead_ordering_checks" in df.columns  # prevention-only column
    assert pd.isna(df.loc[df["strategy"] == "avoidance", "overhead_ordering_checks"]).all()

    summary = metrics.summarize(df)
    assert "throughput_mean" in summary.columns
    assert "throughput_std" in summary.columns
    assert "n_runs" in summary.columns


def test_plots_are_written_for_every_required_metric(tmp_path):
    results = [
        run_single(Condition.LIGHT, 1, StrategyName.PREVENTION),
        run_single(Condition.LIGHT, 1, StrategyName.AVOIDANCE),
        run_single(Condition.LIGHT, 1, StrategyName.DETECTION_RECOVERY),
        run_single(Condition.HEAVY, 101, StrategyName.PREVENTION),
        run_single(Condition.HEAVY, 101, StrategyName.AVOIDANCE),
        run_single(Condition.HEAVY, 101, StrategyName.DETECTION_RECOVERY),
    ]
    df = metrics.results_to_dataframe(results)
    plots.generate_all_plots(df, tmp_path)
    expected = {
        "throughput.png", "avg_waiting_time.png", "resource_utilization.png",
        "blocked_processes.png", "deadlock_episodes.png", "recovery_cost.png",
        "useful_work_lost.png", "terminated_restarted_processes.png",
    }
    produced = {p.name for p in tmp_path.iterdir()}
    assert expected <= produced
    for name in expected:
        assert (tmp_path / name).stat().st_size > 0


def test_full_experiment_produces_180_runs_and_all_expected_files(tmp_path):
    out_dir = run_experiment(output_root=tmp_path, config=DEFAULT_CONFIG, progress=False)
    assert out_dir.exists()

    raw_files = list((out_dir / "raw").glob("*.json"))
    assert len(raw_files) == TOTAL_RUNS == 180

    raw_all = json.loads((out_dir / "raw_all.json").read_text())
    assert len(raw_all) == 180

    df = pd.read_csv(out_dir / "aggregate.csv")
    assert len(df) == 180
    assert (df["status"] == "COMPLETE").all()

    summary = pd.read_csv(out_dir / "summary.csv")
    assert len(summary) == 6  # 2 conditions x 3 strategies
    assert (summary["n_runs"] == 30).all()

    report = (out_dir / "run_report.txt").read_text()
    assert "Total runs: 180" in report
    assert "Incomplete runs: 0" in report

    plot_files = list((out_dir / "plots").glob("*.png"))
    assert len(plot_files) == 8


def test_on_run_complete_callback_fires_for_every_run_with_correct_progress(tmp_path):
    seen = []
    out_dir = run_experiment(
        output_root=tmp_path,
        config=DEFAULT_CONFIG,
        progress=False,
        on_run_complete=lambda result, done, total: seen.append((result, done, total)),
    )
    assert len(seen) == TOTAL_RUNS == 180
    # progress counters are correct and strictly increasing
    assert [done for _, done, _ in seen] == list(range(1, 181))
    assert all(total == 180 for _, _, total in seen)
    # the callback receives the exact same results that ended up in the output
    raw_all = json.loads((out_dir / "raw_all.json").read_text())
    assert [r.to_json_dict() for r, _, _ in seen] == raw_all
