"""SimulationResult: the stable, structured output of a single simulation
run. This is the contract between the core simulator and everything
downstream (experiment runner, metrics, CSV/JSON serialization, plotting).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

from deadlock_sim.core.enums import Condition, RunStatus, StrategyName


@dataclass(frozen=True)
class SimulationResult:
    condition: Condition
    seed: int
    strategy: StrategyName
    status: RunStatus
    ticks_elapsed: int

    total_useful_work: int
    throughput: float

    waiting_times: Tuple[int, ...]
    avg_waiting_time: float
    blocked_processes: int

    resource_utilization: Dict[str, float]
    overall_utilization: float

    deadlock_episodes: int
    recovery_actions: int
    distinct_restarted_processes: int
    useful_work_lost: int

    resources_wasted: Dict[str, float]
    total_resources_wasted: float

    unnecessary_denials: int

    algorithm_overhead: Dict[str, int]

    def to_flat_dict(self) -> dict:
        """A single flat row suitable for the aggregate CSV / DataFrame."""
        row = {
            "condition": self.condition.value,
            "seed": self.seed,
            "strategy": self.strategy.value,
            "status": self.status.value,
            "ticks_elapsed": self.ticks_elapsed,
            "total_useful_work": self.total_useful_work,
            "throughput": self.throughput,
            "avg_waiting_time": self.avg_waiting_time,
            "blocked_processes": self.blocked_processes,
            "overall_utilization": self.overall_utilization,
            "deadlock_episodes": self.deadlock_episodes,
            "recovery_actions": self.recovery_actions,
            "distinct_restarted_processes": self.distinct_restarted_processes,
            "useful_work_lost": self.useful_work_lost,
            "total_resources_wasted": self.total_resources_wasted,
            "unnecessary_denials": self.unnecessary_denials,
        }
        for res_name, util in self.resource_utilization.items():
            row[f"utilization_{res_name}"] = util
        for res_name, wasted in self.resources_wasted.items():
            row[f"wasted_{res_name}"] = wasted
        for key, val in self.algorithm_overhead.items():
            row[f"overhead_{key}"] = val
        return row

    def to_json_dict(self) -> dict:
        """A nested, fully-detailed dict suitable for raw JSON output."""
        d = self.to_flat_dict()
        d["waiting_times"] = list(self.waiting_times)
        return d
