"""The single authoritative, immutable simulation configuration.

Every SimulationState, process/workload definition, strategy, and experiment
run must reference the resource names/order/capacities defined here. No other
module may define an independent or conflicting resource-index mapping.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np

from deadlock_sim.core.enums import Condition

# Fixed resource index order. This order IS the Prevention resource ordering
# (CPU -> Memory -> GPU -> Disk -> Network), so "rank" of a resource is
# simply its index in this tuple.
RESOURCE_NAMES: Tuple[str, ...] = ("CPU", "Memory", "GPU", "Disk", "Network")
RESOURCE_CAPACITIES: Tuple[int, ...] = (10, 8, 6, 12, 5)

NUM_PROCESSES = 20

DETECTION_INTERVAL = 10

MAX_TICKS_LIGHT = 5000
MAX_TICKS_HEAVY = 15000

LIGHT_SEEDS: Tuple[int, ...] = tuple(range(1, 31))  # 1..30
HEAVY_SEEDS: Tuple[int, ...] = tuple(range(101, 131))  # 101..130


@dataclass(frozen=True)
class SimulationConfig:
    """Immutable, authoritative configuration shared by every run.

    Frozen dataclass with only immutable (tuple/int) fields, so instances are
    safe to share across strategies, workloads, and experiment runs without
    risk of accidental mutation.
    """

    resource_names: Tuple[str, ...] = RESOURCE_NAMES
    capacities: Tuple[int, ...] = RESOURCE_CAPACITIES
    num_processes: int = NUM_PROCESSES
    detection_interval: int = DETECTION_INTERVAL
    max_ticks_light: int = MAX_TICKS_LIGHT
    max_ticks_heavy: int = MAX_TICKS_HEAVY

    def __post_init__(self) -> None:
        if len(self.resource_names) != len(self.capacities):
            raise ValueError("resource_names and capacities must be the same length")
        if any(c <= 0 for c in self.capacities):
            raise ValueError("all resource capacities must be positive")

    @property
    def num_resources(self) -> int:
        return len(self.resource_names)

    def capacities_array(self) -> np.ndarray:
        """A fresh int array of total capacities (safe to mutate by caller)."""
        return np.array(self.capacities, dtype=np.int64)

    def max_ticks_for(self, condition: Condition) -> int:
        if condition is Condition.LIGHT:
            return self.max_ticks_light
        if condition is Condition.HEAVY:
            return self.max_ticks_heavy
        raise ValueError(f"unknown condition: {condition!r}")

    def resource_index(self, name: str) -> int:
        return self.resource_names.index(name)


DEFAULT_CONFIG = SimulationConfig()
