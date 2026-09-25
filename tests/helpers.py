"""Helpers for building small, hand-crafted workloads in tests.

These are deliberately NOT the Light/Heavy generators -- the spec asks for
small (2-5 process) scenarios purpose-built to exercise specific correctness
guarantees, not a duplicate of the 180-run experiment.
"""

from __future__ import annotations

from typing import Sequence

from deadlock_sim.core.enums import Condition
from deadlock_sim.core.events import ReleaseEvent, RequestEvent
from deadlock_sim.core.workload import ProcessWorkload, Workload


def req(pid: int, t: int, seq: int, request: Sequence[int], duration: int) -> RequestEvent:
    return RequestEvent(pid=pid, timestamp=t, sequence_number=seq, request=tuple(request), duration=duration)


def rel(pid: int, t: int, seq: int) -> ReleaseEvent:
    return ReleaseEvent(pid=pid, timestamp=t, sequence_number=seq)


def workload(processes: Sequence[ProcessWorkload], condition=Condition.LIGHT, seed: int = 0) -> Workload:
    max_seq = -1
    for pw in processes:
        for e in pw.events:
            max_seq = max(max_seq, e.sequence_number)
    return Workload(
        condition=condition, seed=seed, processes=tuple(processes), next_sequence_number=max_seq + 1
    )
