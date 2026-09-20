"""The experiment runner.

`run_experiment` executes the complete paired comparison: every Light seed
(1-30) and every Heavy seed (101-130), each against all three strategies,
from fresh SimulationState, using the exact same (immutable, replayed)
Workload across all three strategies for a given seed. Writes raw
per-run JSON, a combined raw JSON, an aggregate CSV (one row per run), a
summary CSV (mean +/- std per condition/strategy group), and the required
plots, all into a single timestamped output directory.

`run_single` runs exactly one (condition, seed, strategy) combination, for
the CLI's `single-run` debugging mode.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Type

from deadlock_sim.core.actions import Strategy
from deadlock_sim.core.config import DEFAULT_CONFIG, HEAVY_SEEDS, LIGHT_SEEDS, SimulationConfig
from deadlock_sim.core.enums import Condition, StrategyName
from deadlock_sim.core.result import SimulationResult
from deadlock_sim.core.simulator import Simulator
from deadlock_sim.strategies.banker import BankerAvoidanceStrategy
from deadlock_sim.strategies.detection_recovery import DetectionRecoveryStrategy
from deadlock_sim.strategies.prevention import PreventionStrategy
from deadlock_sim.workloads.generator import generate_heavy, generate_light

from . import metrics, plots

STRATEGY_FACTORIES: Dict[StrategyName, Type[Strategy]] = {
    StrategyName.PREVENTION: PreventionStrategy,
    StrategyName.AVOIDANCE: BankerAvoidanceStrategy,
    StrategyName.DETECTION_RECOVERY: DetectionRecoveryStrategy,
}

TOTAL_RUNS = (len(LIGHT_SEEDS) + len(HEAVY_SEEDS)) * len(STRATEGY_FACTORIES)  # 180


def run_single(
    condition: Condition,
    seed: int,
    strategy_name: StrategyName,
    config: SimulationConfig = DEFAULT_CONFIG,
) -> SimulationResult:
    workload = generate_light(seed, config) if condition is Condition.LIGHT else generate_heavy(seed, config)
    strategy = STRATEGY_FACTORIES[strategy_name]()
    return Simulator(config, workload, strategy).run()


def run_experiment(
    output_root: Path = Path("results"),
    config: SimulationConfig = DEFAULT_CONFIG,
    progress: bool = True,
) -> Path:
    """Runs all 180 combinations and writes the complete output directory.
    Returns the timestamped output directory path."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = output_root / f"experiment_{timestamp}"
    raw_dir = out_dir / "raw"
    plots_dir = out_dir / "plots"
    raw_dir.mkdir(parents=True, exist_ok=True)
    plots_dir.mkdir(parents=True, exist_ok=True)

    results: List[SimulationResult] = []
    done = 0

    for condition, seeds, generate in (
        (Condition.LIGHT, LIGHT_SEEDS, generate_light),
        (Condition.HEAVY, HEAVY_SEEDS, generate_heavy),
    ):
        for seed in seeds:
            workload = generate(seed, config)
            for strategy_name, factory in STRATEGY_FACTORIES.items():
                result = Simulator(config, workload, factory()).run()
                results.append(result)
                done += 1
                if progress and done % 30 == 0:
                    print(f"  {done}/{TOTAL_RUNS} runs complete")

    if progress:
        print(f"  {done}/{TOTAL_RUNS} runs complete")

    for result in results:
        fname = f"{result.condition.value}_seed{result.seed}_{result.strategy.value}.json"
        (raw_dir / fname).write_text(json.dumps(result.to_json_dict(), indent=2))
    (out_dir / "raw_all.json").write_text(json.dumps([r.to_json_dict() for r in results], indent=2))

    df = metrics.results_to_dataframe(results)
    df.to_csv(out_dir / "aggregate.csv", index=False)

    summary = metrics.summarize(df)
    summary.to_csv(out_dir / "summary.csv", index=False)

    plots.generate_all_plots(df, plots_dir)

    n_incomplete = int((df["status"] == "INCOMPLETE").sum())
    (out_dir / "run_report.txt").write_text(
        f"Total runs: {len(results)}\n"
        f"Incomplete runs: {n_incomplete}\n"
        f"Light seeds: {len(LIGHT_SEEDS)} | Heavy seeds: {len(HEAVY_SEEDS)} | Strategies: {len(STRATEGY_FACTORIES)}\n"
    )

    if progress:
        print(f"Output written to: {out_dir}")
        if n_incomplete:
            print(f"WARNING: {n_incomplete} run(s) did not complete within max_ticks.")

    return out_dir
