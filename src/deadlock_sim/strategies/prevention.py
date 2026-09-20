"""Deadlock Prevention using resource ordering.

Fixed order CPU < Memory < GPU < Disk < Network. Since SimulationConfig's
resource index order IS this ordering, "rank" of a resource is simply its
index — no separate rank table is needed.

A process may request a resource only if every requested resource has rank
>= the highest-ranked resource it currently holds. This strategy is
read-only with respect to shared state: it never force-releases resources.
"""

from __future__ import annotations

from typing import Dict

import numpy as np

from deadlock_sim.core.actions import PeriodicCheckResult, RequestEvaluation, Strategy
from deadlock_sim.core.enums import RequestDecision, StrategyName
from deadlock_sim.core.state import SimulationState


class PreventionStrategy(Strategy):
    name = StrategyName.PREVENTION

    def __init__(self) -> None:
        self.ordering_checks = 0
        self.request_evaluations = 0

    def evaluate_request(
        self, state: SimulationState, pid: int, request: np.ndarray
    ) -> RequestEvaluation:
        self.request_evaluations += 1
        available = state.resources.available
        avail_ok = bool(np.all(request <= available))

        self.ordering_checks += 1
        requested_indices = np.nonzero(request)[0]
        if requested_indices.size == 0:
            order_ok = True
        else:
            highest_held = state.highest_held_rank(pid)
            order_ok = bool(requested_indices.min() >= highest_held)

        if avail_ok and order_ok:
            return RequestEvaluation(RequestDecision.GRANT)

        unnecessary = avail_ok and not order_ok
        return RequestEvaluation(RequestDecision.WAIT, unnecessary_denial=unnecessary)

    def periodic_check(self, state: SimulationState) -> PeriodicCheckResult:
        return PeriodicCheckResult()

    def overhead_stats(self) -> Dict[str, int]:
        return {
            "ordering_checks": self.ordering_checks,
            "request_evaluations": self.request_evaluations,
        }
