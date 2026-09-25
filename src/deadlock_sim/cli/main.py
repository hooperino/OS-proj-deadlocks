"""Command-line interface.

    python -m deadlock_sim.cli.main experiment [--output DIR] [--quiet]
    python -m deadlock_sim.cli.main single-run --condition light --seed 5 --strategy prevention [--output FILE]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from deadlock_sim.core.config import HEAVY_SEEDS, LIGHT_SEEDS
from deadlock_sim.core.enums import Condition, StrategyName
from deadlock_sim.experiment.runner import run_experiment, run_single


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="deadlock-sim",
        description="Deadlock Prevention, Avoidance, and Recovery -- quantitative trade-off analysis",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    exp = sub.add_parser("experiment", help="Run the complete 180-run comparison (30 Light + 30 Heavy seeds x 3 strategies)")
    exp.add_argument("--output", type=Path, default=Path("results"), help="Output root directory (default: ./results)")
    exp.add_argument("--quiet", action="store_true", help="Suppress progress output")

    single = sub.add_parser("single-run", help="Run one workload/strategy combination for debugging and inspection")
    single.add_argument("--condition", choices=["light", "heavy"], required=True)
    single.add_argument("--seed", type=int, required=True, help="Light: 1-30. Heavy: 101-130.")
    single.add_argument("--strategy", choices=["prevention", "avoidance", "detection_recovery"], required=True)
    single.add_argument("--output", type=Path, default=None, help="Optional path to also save the result as JSON")

    return parser


def _print_single_run_summary(result) -> None:
    print(f"condition={result.condition.value} seed={result.seed} strategy={result.strategy.value}")
    print(f"status={result.status.value} ticks_elapsed={result.ticks_elapsed}")
    print(f"total_useful_work={result.total_useful_work} throughput={result.throughput:.4f}")
    print(f"avg_waiting_time={result.avg_waiting_time:.2f} blocked_processes={result.blocked_processes}")
    print(f"overall_utilization={result.overall_utilization:.4f}")
    print(
        f"deadlock_episodes={result.deadlock_episodes} recovery_actions={result.recovery_actions} "
        f"distinct_restarted_processes={result.distinct_restarted_processes}"
    )
    print(f"useful_work_lost={result.useful_work_lost} unnecessary_denials={result.unnecessary_denials}")
    print(f"total_resources_wasted={result.total_resources_wasted:.2f}")
    print(f"algorithm_overhead={result.algorithm_overhead}")


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "experiment":
        out_dir = run_experiment(output_root=args.output, progress=not args.quiet)
        print(f"Experiment complete. Output written to: {out_dir}")
        return 0

    if args.command == "single-run":
        condition = Condition.LIGHT if args.condition == "light" else Condition.HEAVY
        valid_seeds = LIGHT_SEEDS if condition is Condition.LIGHT else HEAVY_SEEDS
        if args.seed not in valid_seeds:
            print(
                f"warning: seed {args.seed} is outside the documented "
                f"{'Light (1-30)' if condition is Condition.LIGHT else 'Heavy (101-130)'} range; "
                "the workload will still be generated deterministically.",
                file=sys.stderr,
            )
        strategy_name = StrategyName(args.strategy)
        result = run_single(condition, args.seed, strategy_name)
        _print_single_run_summary(result)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result.to_json_dict(), indent=2))
            print(f"Result written to: {args.output}")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
