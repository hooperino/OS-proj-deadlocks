"""The Process model.

Processes are mutated only by the Simulator, never by strategies.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from deadlock_sim.core.enums import ProcessState


@dataclass(eq=False)
class Process:
    """A single process's live simulation state.

    `generation` increments on every restart and is used by the simulator to
    invalidate stale (pre-restart) scheduled workload events without having
    to search and remove them from the event queue.
    """

    pid: int
    total_work: int
    max_claim: np.ndarray
    state: ProcessState = ProcessState.RUNNING
    completed_work: int = 0
    allocation: np.ndarray = field(default=None)  # set in __post_init__
    generation: int = 0

    # Diagnostics (auditability only; not used for control flow)
    ever_waited: bool = False
    times_restarted: int = 0

    def __post_init__(self) -> None:
        if self.allocation is None:
            self.allocation = np.zeros_like(self.max_claim)

    def need(self) -> np.ndarray:
        """Need = max_claim - allocation. Computed on demand; not stored."""
        return self.max_claim - self.allocation
