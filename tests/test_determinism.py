from deadlock_sim.core.simulator import Simulator
from deadlock_sim.strategies.banker import BankerAvoidanceStrategy
from deadlock_sim.strategies.detection_recovery import DetectionRecoveryStrategy
from deadlock_sim.strategies.prevention import PreventionStrategy
from deadlock_sim.workloads.generator import generate_heavy, generate_light


def test_same_seed_and_condition_produces_byte_identical_workload():
    assert generate_light(7).processes == generate_light(7).processes
    assert generate_heavy(105).processes == generate_heavy(105).processes


def test_different_seeds_produce_different_workloads():
    assert generate_light(1).processes != generate_light(2).processes


def test_identical_config_workload_strategy_produces_identical_results(config):
    wl = generate_heavy(101)
    for strategy_cls in (PreventionStrategy, BankerAvoidanceStrategy, DetectionRecoveryStrategy):
        r1 = Simulator(config, wl, strategy_cls()).run()
        r2 = Simulator(config, wl, strategy_cls()).run()
        assert r1.to_json_dict() == r2.to_json_dict()
