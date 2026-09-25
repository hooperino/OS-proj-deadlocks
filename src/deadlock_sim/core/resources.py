"""The shared resource pool.

Resource quantities must never become negative — allocate()/release() assert
this invariant on every call. This is an essential correctness check, not a
large validation framework.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple

import numpy as np


@dataclass(eq=False)
class ResourcePool:
    names: Tuple[str, ...]
    capacity: np.ndarray
    available: np.ndarray = field(default=None)

    def __post_init__(self) -> None:
        if self.available is None:
            self.available = self.capacity.copy()

    def allocate(self, amounts: np.ndarray) -> None:
        new_available = self.available - amounts
        if np.any(new_available < 0):
            raise ValueError(
                f"allocation would drive available negative: "
                f"available={self.available}, amounts={amounts}"
            )
        self.available = new_available

    def release(self, amounts: np.ndarray) -> None:
        new_available = self.available + amounts
        if np.any(new_available > self.capacity):
            raise ValueError(
                f"release would exceed capacity: "
                f"available={self.available}, capacity={self.capacity}, amounts={amounts}"
            )
        self.available = new_available

    def held(self) -> np.ndarray:
        """Currently held (in-use) amount per resource."""
        return self.capacity - self.available
