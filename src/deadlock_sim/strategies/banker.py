"""Deadlock Avoidance using the Banker's safety algorithm.

For a REQUEST: if unavailable, WAIT. Otherwise compute what the system would
look like if it were tentatively granted (using local, read-only copies of
Allocation/Need/Available — never touching real SimulationState), and run
the safety algorithm on that hypothetical state. Grant only if the resulting
state is safe; otherwise WAIT. Because the "tentative grant" only ever
happens on local copies, there is nothing to roll back on the real state —
the real state is simply never touched unless the decision is GRANT.

Safety checks happen only on REQUEST events; there is no periodic Banker
safety check.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np

from deadlock_sim.core.actions import PeriodicCheckResult, RequestEvaluation, Strategy
from deadlock_sim.core.enums import RequestDecision, StrategyName
from deadlock_sim.core.state import SimulationState


class BankerAvoidanceStrategy(Strategy):
    name = StrategyName.AVOIDANCE

    def __init__(self) -> None:
        self.safety_checks = 0
        self.processes_examined = 0
        self.safety_iterations = 0

    def evaluate_request(
        self, state: SimulationState, pid: int, request: np.ndarray
    ) -> RequestEvaluation:
        available = state.resources.available
        if not bool(np.all(request <= available)):
            return RequestEvaluation(RequestDecision.WAIT)

        self.safety_checks += 1
        active_pids = state.active_pids_sorted()
        alloc = {p: state.processes[p].allocation.copy() for p in active_pids}
        alloc[pid] = alloc[pid] + request
        max_claim = {p: state.processes[p].max_claim for p in active_pids}
        need = {p: max_claim[p] - alloc[p] for p in active_pids}
        work_after_grant = available - request

        safe, _order = self._run_safety_algorithm(active_pids, alloc, need, work_after_grant)

        if safe:
            return RequestEvaluation(RequestDecision.GRANT)
        return RequestEvaluation(RequestDecision.WAIT, unnecessary_denial=True)

    def predicted_safe_sequence(
        self, state: SimulationState
    ) -> Tuple[bool, List[int]]:
        """Read-only helper (also used by tests) that reports whether the
        CURRENT state (no hypothetical grant) is safe, and if so, in which
        pid order the safety algorithm would finish every process. Does not
        affect overhead counters."""
        active_pids = state.active_pids_sorted()
        alloc = {p: state.processes[p].allocation.copy() for p in active_pids}
        need = {p: state.processes[p].need() for p in active_pids}
        work = state.resources.available.copy()
        return self._run_safety_algorithm(active_pids, alloc, need, work, count_overhead=False)

    def _run_safety_algorithm(
        self,
        active_pids: List[int],
        alloc: Dict[int, np.ndarray],
        need: Dict[int, np.ndarray],
        work: np.ndarray,
        count_overhead: bool = True,
    ) -> Tuple[bool, List[int]]:
        finish = {p: False for p in active_pids}
        order: List[int] = []
        progressed = True
        while progressed:
            if count_overhead:
                self.safety_iterations += 1
            progressed = False
            for p in active_pids:  # already ascending pid order
                if finish[p]:
                    continue
                if count_overhead:
                    self.processes_examined += 1
                if bool(np.all(need[p] <= work)):
                    work = work + alloc[p]
                    finish[p] = True
                    order.append(p)
                    progressed = True
                    break  # restart scan from the lowest pid, per the tie-break rule
        safe = all(finish.values())
        return safe, order

    def periodic_check(self, state: SimulationState) -> PeriodicCheckResult:
        return PeriodicCheckResult()

    def overhead_stats(self) -> Dict[str, int]:
        return {
            "safety_checks": self.safety_checks,
            "processes_examined": self.processes_examined,
            "safety_iterations": self.safety_iterations,
        }
