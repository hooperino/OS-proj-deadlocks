import pytest

from deadlock_sim.core.config import SimulationConfig


@pytest.fixture
def config() -> SimulationConfig:
    return SimulationConfig()
