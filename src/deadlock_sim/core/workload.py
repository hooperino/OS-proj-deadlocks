"""Immutable workload schema.

This module defines the *shape* of a workload — what the Simulator consumes.
Random generation logic (the Light/Heavy generators, seeds, RNG) is
deliberately kept out of core and lives in `deadlock_sim.workloads.generator`,
so the core simulation layer has no dependency on workload-generation
concerns. A Workload, once built, is immutable and replayable: the same
Workload object is fed to all three strategies from fresh SimulationState.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from deadlock_sim.core.enums import Condition
from deadlock_sim.core.events import WorkloadEvent


@dataclass(frozen=True)
class ProcessWorkload:
    """One process's immutable definition: its total work, its maximum
    simultaneous resource claim, and its chronological (from tick 0) list of
    REQUEST/RELEASE events. Events are absolute timestamps as authored; the
    Simulator shifts them at restart time."""

    pid: int
    total_work: int
    max_claim: Tuple[int, ...]
    events: Tuple[WorkloadEvent, ...]  # sorted by (timestamp, sequence_number)


@dataclass(frozen=True)
class Workload:
    """A complete, immutable, replayable workload for one seed/condition."""

    condition: Condition
    seed: int
    processes: Tuple[ProcessWorkload, ...]  # indexed 0..num_processes-1 by pid
    next_sequence_number: int  # first sequence number safe to use for
    # dynamically-scheduled events (restart replays), guaranteed greater
    # than every sequence_number used anywhere in this workload.
