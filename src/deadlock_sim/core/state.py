"""The single authoritative, mutable SimulationState.

Only the Simulator mutates this. Strategies receive it read-only (by
convention/discipline — Python cannot enforce true immutability on a mutable
graph of objects, but no strategy in this project ever assigns into it).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

from deadlock_sim.core.config import SimulationConfig
from deadlock_sim.core.enums import ProcessState
from deadlock_sim.core.holdings import Holding, PendingRequest
from deadlock_sim.core.process import Process
from deadlock_sim.core.resources import ResourcePool


@dataclass(eq=False)
class SimulationState:
    config: SimulationConfig
    resources: ResourcePool
    processes: Dict[int, Process]
    current_tick: int = 0
    holdings: Dict[int, Holding] = field(default_factory=dict)
    pending: Dict[int, PendingRequest] = field(default_factory=dict)
    next_holding_id: int = 0
    deadlock_active: bool = False

    def active_processes(self):
        """Processes not yet COMPLETED (excludes the transient TERMINATED
        state, which never persists between simulator steps)."""
        return [p for p in self.processes.values() if p.state != ProcessState.COMPLETED]

    def active_pids_sorted(self):
        return sorted(p.pid for p in self.active_processes())

    def highest_held_rank(self, pid: int) -> int:
        """Highest resource-index (rank) currently held by pid, or -1 if the
        process holds nothing. Resource rank == resource index, since the
        fixed resource order IS the Prevention ordering."""
        allocation = self.processes[pid].allocation
        held_indices = [i for i, amount in enumerate(allocation) if amount > 0]
        return max(held_indices) if held_indices else -1

    def new_holding_id(self) -> int:
        holding_id = self.next_holding_id
        self.next_holding_id += 1
        return holding_id
