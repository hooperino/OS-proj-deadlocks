"""Deadlock Detection + Recovery.

Normal request handling grants whenever all requested resources are
currently available; no safety check is performed before granting.

Every `interval` ticks (10, 20, 30, ...; never tick 0), periodic_check runs
matrix-based deadlock detection using Available/Allocation/PendingRequest
(not Need). If a deadlock is found, it selects victims one at a time (lowest
completed_work, tie-break lowest pid) and repeats detection against the
remaining processes until no deadlock remains.

Because strategies must not mutate shared SimulationState, this entire
detect -> pick-victim -> (locally) release -> re-detect loop is performed
against local, read-only copies of Available/Allocation/PendingRequest.
Only the resulting ordered list of TerminateVictimAction is returned; the
Simulator performs every real mutation (release, timer cancellation, pending
discard, restart) when it applies those actions.
"""

from __future__ import annotations

from typing import Dict, List

import numpy as np

from deadlock_sim.core.actions import (
    PeriodicCheckResult,
    RequestEvaluation,
    Strategy,
    TerminateVictimAction,
)
from deadlock_sim.core.enums import RequestDecision, StrategyName
from deadlock_sim.core.state import SimulationState


class DetectionRecoveryStrategy(Strategy):
    name = StrategyName.DETECTION_RECOVERY

    def __init__(self, interval: int = 10) -> None:
        self.interval = interval
        self.detection_passes = 0
        self.processes_examined = 0
        self.detection_iterations = 0
        self.victim_selections = 0

    def evaluate_request(
        self, state: SimulationState, pid: int, request: np.ndarray
    ) -> RequestEvaluation:
        available = state.resources.available
        if bool(np.all(request <= available)):
            return RequestEvaluation(RequestDecision.GRANT)
        return RequestEvaluation(RequestDecision.WAIT)

    def periodic_check(self, state: SimulationState) -> PeriodicCheckResult:
        tick = state.current_tick
        if tick == 0 or tick % self.interval != 0:
            return PeriodicCheckResult()

        active_pids = state.active_pids_sorted()
        alloc = {p: state.processes[p].allocation.copy() for p in active_pids}
        completed_work = {p: state.processes[p].completed_work for p in active_pids}
        pending_req = {
            p: (state.pending[p].request.copy() if p in state.pending else None)
            for p in active_pids
        }
        available = state.resources.available.copy()

        remaining = list(active_pids)
        victims: List[int] = []
        deadlock_detected_initially = False

        while True:
            self.detection_passes += 1
            work = available.copy()
            finish: Dict[int, bool] = {}
            for p in remaining:
                if pending_req[p] is None:
                    # Not currently blocked -- this process is making
                    # independent progress and is not part of any cycle.
                    # Its held resources must be folded into Work (this is
                    # what the standard matrix algorithm does implicitly: a
                    # process with no outstanding request trivially
                    # satisfies Request <= Work and is processed on the very
                    # first pass). Omitting this step would make every
                    # ordinary RUNNING process's holdings permanently
                    # invisible to the detector, causing false-positive
                    # "deadlocks" for any lone WAITING process whose
                    # resource is simply held by healthy, unblocked
                    # processes that have not released it yet.
                    finish[p] = True
                    work = work + alloc[p]
                else:
                    finish[p] = False
            progressed = True
            while progressed:
                self.detection_iterations += 1
                progressed = False
                for p in remaining:
                    if finish[p]:
                        continue
                    self.processes_examined += 1
                    if bool(np.all(pending_req[p] <= work)):
                        work = work + alloc[p]
                        finish[p] = True
                        progressed = True

            deadlocked = [p for p in remaining if not finish[p]]
            if not deadlocked:
                break

            if not victims:
                deadlock_detected_initially = True

            victim = min(deadlocked, key=lambda p: (completed_work[p], p))
            self.victim_selections += 1
            victims.append(victim)

            # Locally simulate releasing the victim's resources so the next
            # detection pass reflects what the real recovery will do.
            available = available + alloc[victim]
            remaining = [p for p in remaining if p != victim]

        actions = tuple(TerminateVictimAction(pid=v) for v in victims)
        return PeriodicCheckResult(actions=actions, deadlock_detected=deadlock_detected_initially)

    def overhead_stats(self) -> Dict[str, int]:
        return {
            "detection_passes": self.detection_passes,
            "processes_examined": self.processes_examined,
            "detection_iterations": self.detection_iterations,
            "victim_selections": self.victim_selections,
        }
