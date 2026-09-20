"""Per-grant holding-duration tracking and pending-request bookkeeping.

Each granted REQUEST creates an independent active Holding with its own
expiration tick. Multiple holdings may overlap for the same process.
Expiration releases only that holding, never the process's other resources.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(eq=False)
class Holding:
    holding_id: int
    pid: int
    resources: np.ndarray
    grant_tick: int
    expiration_tick: int
    generation: int  # process generation this holding belongs to


@dataclass(eq=False)
class PendingRequest:
    """A process may have at most one pending request at a time."""

    pid: int
    request: np.ndarray
    waiting_start_tick: int
    sequence_number: int
    duration: int
    generation: int  # process generation this pending request belongs to
