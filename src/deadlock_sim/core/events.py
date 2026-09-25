"""Typed, immutable workload event dataclasses.

Workload event types are exactly REQUEST and RELEASE. There is no START
event and no COMPLETE event — all 20 processes are present and runnable
from tick 0, and completion is derived from work progression, not an event.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple, Union


@dataclass(frozen=True)
class RequestEvent:
    """An incremental, additional resource request.

    `request` is an immutable per-resource-index amount vector (same length
    and index order as SimulationConfig.resource_names). If granted:
        allocation += request
        available  -= request
    """

    pid: int
    timestamp: int
    sequence_number: int
    request: Tuple[int, ...]
    duration: int

    def __post_init__(self) -> None:
        if self.timestamp < 0:
            raise ValueError("timestamp must be non-negative")
        if self.duration <= 0:
            raise ValueError("duration must be positive")
        if any(amount < 0 for amount in self.request):
            raise ValueError("request amounts must be non-negative")


@dataclass(frozen=True)
class ReleaseEvent:
    """Releases all resources currently held by the process.

    A RELEASE when the process holds nothing is a valid no-op.
    """

    pid: int
    timestamp: int
    sequence_number: int

    def __post_init__(self) -> None:
        if self.timestamp < 0:
            raise ValueError("timestamp must be non-negative")


WorkloadEvent = Union[RequestEvent, ReleaseEvent]
