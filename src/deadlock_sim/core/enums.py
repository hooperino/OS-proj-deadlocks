"""Enumerations shared across the simulation core, strategies, and experiment layers.

There is exactly one authoritative definition of each enum in the whole project.
No module should redefine or shadow these.
"""

from __future__ import annotations

from enum import Enum


class ProcessState(Enum):
    """Lifecycle state of a process.

    TERMINATED is a transient/internal state used only while a recovery
    termination is being applied inside a single tick. A successfully
    completed simulation must never end with a process left in TERMINATED —
    every terminated process is restarted back to RUNNING within the same
    tick, or the run is still in progress.
    """

    RUNNING = "RUNNING"
    WAITING = "WAITING"
    COMPLETED = "COMPLETED"
    TERMINATED = "TERMINATED"


class RequestDecision(Enum):
    """Binary decision a strategy makes about a resource request."""

    GRANT = "GRANT"
    WAIT = "WAIT"


class StrategyName(Enum):
    """The three strategies compared by this project."""

    PREVENTION = "prevention"
    AVOIDANCE = "avoidance"
    DETECTION_RECOVERY = "detection_recovery"


class Condition(Enum):
    """The two contention conditions workloads are generated under."""

    LIGHT = "light"
    HEAVY = "heavy"


class RunStatus(Enum):
    """Final status of a single simulation run."""

    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"


class WorkloadEventType(Enum):
    """The two workload event types. There is no START or COMPLETE event."""

    REQUEST = "REQUEST"
    RELEASE = "RELEASE"
