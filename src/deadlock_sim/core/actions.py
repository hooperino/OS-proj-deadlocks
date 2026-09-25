"""Structured decisions/actions returned by strategies, and the common
strategy interface.

Strategies inspect SimulationState (read-only) and return structured
decisions/actions. They never mutate shared simulation state directly — the
Simulator owns all state mutation and event execution.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np

from deadlock_sim.core.enums import RequestDecision, StrategyName
from deadlock_sim.core.state import SimulationState


@dataclass(frozen=True)
class RequestEvaluation:
    """The result of evaluate_request(): a binary decision plus diagnostics.

    unnecessary_denial is True only when the request was WAITed despite all
    requested resources being currently physically available, and the wait
    was caused by strategy policy (Prevention ordering, Banker unsafe-state
    rollback) rather than ordinary resource unavailability.
    """

    decision: RequestDecision
    unnecessary_denial: bool = False


@dataclass(frozen=True)
class TerminateVictimAction:
    """Instructs the simulator to terminate-and-restart a deadlocked victim."""

    pid: int


@dataclass(frozen=True)
class PeriodicCheckResult:
    """The result of periodic_check() for a single tick.

    `actions` is the full ordered list of victim terminations the simulator
    should apply this tick (computed by the strategy via a read-only local
    simulation of the detect -> pick-victim -> release -> re-detect loop).
    `deadlock_detected` records whether the very first detection pass this
    tick (before any victim was virtually removed) found a deadlock — this is
    what the simulator uses for "no deadlock -> deadlock" episode counting.
    """

    actions: Tuple[TerminateVictimAction, ...] = ()
    deadlock_detected: bool = False


class Strategy(ABC):
    """Common interface implemented by Prevention, Avoidance, and
    Detection+Recovery.

    Strategies must not directly mutate shared SimulationState. They may
    freely maintain their own private, per-run diagnostic counters (algorithm
    overhead accounting) as instance attributes — that bookkeeping is
    strategy-local, not shared simulation state.
    """

    name: StrategyName

    @abstractmethod
    def evaluate_request(
        self, state: SimulationState, pid: int, request: np.ndarray
    ) -> RequestEvaluation:
        """Decide GRANT or WAIT for a (re)considered request. Read-only."""
        raise NotImplementedError

    @abstractmethod
    def periodic_check(self, state: SimulationState) -> PeriodicCheckResult:
        """Called once per tick. Prevention and Avoidance always return an
        empty result. Detection+Recovery performs detection on its interval
        and returns the ordered victim-termination actions, if any."""
        raise NotImplementedError

    @abstractmethod
    def overhead_stats(self) -> Dict[str, int]:
        """Return this strategy's accumulated algorithm-overhead counters."""
        raise NotImplementedError
