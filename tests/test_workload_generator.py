import pytest

from deadlock_sim.core.config import DEFAULT_CONFIG, HEAVY_SEEDS, LIGHT_SEEDS
from deadlock_sim.core.enums import Condition, RunStatus
from deadlock_sim.core.events import ReleaseEvent, RequestEvent
from deadlock_sim.core.simulator import Simulator
from deadlock_sim.strategies.detection_recovery import DetectionRecoveryStrategy
from deadlock_sim.workloads.generator import generate_heavy, generate_light


def _validate_structure(workload, condition):
    config = DEFAULT_CONFIG
    assert len(workload.processes) == config.num_processes
    seen_seq = set()
    cap_frac = 0.42 if condition == Condition.LIGHT else 0.72  # small slack for int-rounding
    for pw in workload.processes:
        assert len(pw.max_claim) == config.num_resources
        assert 50 <= pw.total_work <= 150
        assert any(isinstance(e, RequestEvent) for e in pw.events), f"pid {pw.pid} has no REQUEST"
        assert any(isinstance(e, ReleaseEvent) for e in pw.events), f"pid {pw.pid} has no RELEASE"

        timestamps = [e.timestamp for e in pw.events]
        assert timestamps == sorted(timestamps), f"pid {pw.pid} events out of order"

        for r, amount in enumerate(pw.max_claim):
            assert amount <= config.capacities[r] * cap_frac + 1, (
                f"pid {pw.pid} resource {r} claims {amount}, exceeding the intensity cap"
            )

        requested_total = [0] * config.num_resources
        for e in pw.events:
            if isinstance(e, RequestEvent):
                for r, amount in enumerate(e.request):
                    requested_total[r] += amount
        for r in range(config.num_resources):
            assert requested_total[r] <= pw.max_claim[r], (
                f"pid {pw.pid} resource {r} requests {requested_total[r]} total, exceeding max_claim {pw.max_claim[r]}"
            )

        for e in pw.events:
            assert e.sequence_number not in seen_seq, "duplicate global sequence number"
            seen_seq.add(e.sequence_number)

        n_requests = sum(1 for e in pw.events if isinstance(e, RequestEvent))
        lo, hi = (3, 5) if condition == Condition.LIGHT else (6, 8)
        assert lo <= n_requests <= hi, (
            f"pid {pw.pid} has {n_requests} REQUEST events, outside the {condition.value} range [{lo},{hi}]"
        )


@pytest.mark.parametrize("seed", list(LIGHT_SEEDS))
def test_light_workload_structure(seed):
    _validate_structure(generate_light(seed), Condition.LIGHT)


@pytest.mark.parametrize("seed", list(HEAVY_SEEDS))
def test_heavy_workload_structure(seed):
    _validate_structure(generate_heavy(seed), Condition.HEAVY)


def test_seed_ranges_match_spec():
    assert list(LIGHT_SEEDS) == list(range(1, 31))
    assert list(HEAVY_SEEDS) == list(range(101, 131))


def test_light_and_heavy_determinism():
    assert generate_light(3).processes == generate_light(3).processes
    assert generate_light(3).next_sequence_number == generate_light(3).next_sequence_number
    assert generate_heavy(110).processes == generate_heavy(110).processes


@pytest.mark.parametrize("seed", list(HEAVY_SEEDS))
def test_every_heavy_seed_guarantees_a_detected_and_recovered_deadlock(seed):
    # This is the spec's explicit requirement: Heavy must *guarantee*
    # meaningful deadlock-prone cases, not merely make them probable.
    wl = generate_heavy(seed)
    result = Simulator(DEFAULT_CONFIG, wl, DetectionRecoveryStrategy()).run()
    assert result.status == RunStatus.COMPLETE
    assert result.deadlock_episodes >= 1
    assert result.recovery_actions >= 1


@pytest.mark.parametrize("seed", list(LIGHT_SEEDS) + list(HEAVY_SEEDS))
def test_all_seeds_complete_under_every_strategy(seed):
    from deadlock_sim.strategies.banker import BankerAvoidanceStrategy
    from deadlock_sim.strategies.prevention import PreventionStrategy

    condition = Condition.LIGHT if seed in LIGHT_SEEDS else Condition.HEAVY
    wl = generate_light(seed) if condition == Condition.LIGHT else generate_heavy(seed)
    for strategy_cls in (PreventionStrategy, BankerAvoidanceStrategy, DetectionRecoveryStrategy):
        result = Simulator(DEFAULT_CONFIG, wl, strategy_cls()).run()
        assert result.status == RunStatus.COMPLETE, (seed, strategy_cls.__name__, result.ticks_elapsed)


def test_workloads_do_not_pre_enforce_prevention_ordering():
    # The generator must not sanitize workloads to obey resource ordering --
    # otherwise Prevention would never have anything to actually prevent.
    found_descending_pattern = False
    for seed in HEAVY_SEEDS:
        wl = generate_heavy(seed)
        for pw in wl.processes:
            held_ranks = set()
            for e in pw.events:
                if isinstance(e, RequestEvent):
                    requested_ranks = [i for i, amt in enumerate(e.request) if amt > 0]
                    if held_ranks and any(r < max(held_ranks) for r in requested_ranks):
                        found_descending_pattern = True
                    held_ranks.update(requested_ranks)
                else:
                    held_ranks = set()
    assert found_descending_pattern


# ---------------------------------------------------------------------
# Pattern-specific correctness: each pressure type isolates its target
# strategy's cost cleanly, and none of them are confounded with the others.
# ---------------------------------------------------------------------

def test_banker_trap_group_is_mathematically_available_but_unsafe():
    from deadlock_sim.workloads.generator import _build_banker_trap_group, _params_for
    import random

    params = _params_for(Condition.HEAVY, DEFAULT_CONFIG)
    rng = random.Random("test-banker-trap")
    result = _build_banker_trap_group(rng, (0, 1, 2), resource=1, capacities=DEFAULT_CONFIG.capacities,
                                       num_resources=5, params=params, t0=5)
    assert result is not None
    events_by_pid, claim_by_pid, _ = result
    requester = 2  # last pid in the group
    others_total = sum(events_by_pid[p][0][3][1] for p in (0, 1) if events_by_pid[p])
    requester_amount = events_by_pid[requester][0][3][1]
    assert requester_amount > 0  # the requester's own request must be meaningful, not zero
    capacity = DEFAULT_CONFIG.capacities[1]
    # The requester's grant must exactly zero out Available...
    assert others_total + requester_amount == capacity
    # ...while every process still has positive remaining Need.
    for pid in (0, 1, 2):
        held = events_by_pid[pid][0][3][1] if events_by_pid[pid] else 0
        assert claim_by_pid[pid][1] - held > 0


def test_ordering_violation_amount_is_modest_and_descending():
    from deadlock_sim.workloads.generator import _build_ordering_violation, _params_for
    import random

    params = _params_for(Condition.HEAVY, DEFAULT_CONFIG)
    rng = random.Random("test-ordering-violation")
    events, claim, _ = _build_ordering_violation(rng, pid=0, capacities=DEFAULT_CONFIG.capacities,
                                                  num_resources=5, params=params, t0=3)
    first_resource = [i for i, v in enumerate(events[0][3]) if v > 0][0]
    second_resource = [i for i, v in enumerate(events[1][3]) if v > 0][0]
    assert second_resource < first_resource  # descending -- an ordering violation
    for resource, amount in claim.items():
        assert amount <= DEFAULT_CONFIG.capacities[resource] * 0.30  # well under the 70% cap


@pytest.mark.parametrize("seed", [101, 110, 120, 130])
def test_heavy_prevention_shows_unnecessary_denials_with_zero_deadlocks(seed):
    from deadlock_sim.strategies.prevention import PreventionStrategy

    result = Simulator(DEFAULT_CONFIG, generate_heavy(seed), PreventionStrategy()).run()
    assert result.status == RunStatus.COMPLETE
    assert result.unnecessary_denials > 0
    assert result.deadlock_episodes == 0
    assert result.recovery_actions == 0


@pytest.mark.parametrize("seed", [101, 110, 120, 130])
def test_heavy_avoidance_shows_unnecessary_denials_with_zero_deadlocks(seed):
    from deadlock_sim.strategies.banker import BankerAvoidanceStrategy

    result = Simulator(DEFAULT_CONFIG, generate_heavy(seed), BankerAvoidanceStrategy()).run()
    assert result.status == RunStatus.COMPLETE
    assert result.unnecessary_denials > 0
    assert result.deadlock_episodes == 0
    assert result.recovery_actions == 0


@pytest.mark.parametrize("seed", [101, 110, 120, 130])
def test_heavy_detection_recovery_shows_deadlocks_with_zero_unnecessary_denials(seed):
    result = Simulator(DEFAULT_CONFIG, generate_heavy(seed), DetectionRecoveryStrategy()).run()
    assert result.status == RunStatus.COMPLETE
    assert result.deadlock_episodes >= 1
    assert result.recovery_actions >= 1
    assert result.unnecessary_denials == 0


def test_deadlock_cycles_use_varied_resource_combinations_across_seeds():
    # "Varied cycles and resource combinations rather than one repeated toy
    # pattern": collect which resource pairs/triples actually got used for
    # the deadlock-pair and deadlock-triple slots across every Heavy seed,
    # and require more than one distinct combination to appear.
    from deadlock_sim.core.events import RequestEvent

    pair_signatures = set()
    triple_signatures = set()
    for seed in HEAVY_SEEDS:
        wl = generate_heavy(seed)
        pair_resources = set()
        for pid in (6, 7, 8, 9):
            pw = wl.processes[pid]
            first_request = next(e for e in pw.events if isinstance(e, RequestEvent))
            pair_resources.add(tuple(i for i, v in enumerate(first_request.request) if v > 0))
        pair_signatures.add(frozenset(pair_resources))

        triple_resources = set()
        for pid in (10, 11, 12):
            pw = wl.processes[pid]
            first_request = next(e for e in pw.events if isinstance(e, RequestEvent))
            triple_resources.add(tuple(i for i, v in enumerate(first_request.request) if v > 0))
        triple_signatures.add(frozenset(triple_resources))

    assert len(pair_signatures) > 1, "every Heavy seed used the exact same pair of resource pairs"
    assert len(triple_signatures) > 1, "every Heavy seed used the exact same triple of resources"


def test_heavy_and_light_preserve_heterogeneity_with_background_processes():
    from deadlock_sim.workloads.generator import _plan_for

    light_plan = _plan_for(Condition.LIGHT)
    heavy_plan = _plan_for(Condition.HEAVY)
    assert len(light_plan.background) >= 2
    assert len(heavy_plan.background) >= 2
    # every pid is assigned to exactly one role, covering all 20 processes
    for plan in (light_plan, heavy_plan):
        all_pids = (
            [p for g in plan.banker_groups for p in g]
            + [p for pair in plan.deadlock_pairs for p in pair]
            + [p for t in plan.deadlock_triples for p in t]
            + list(plan.ordering_violation)
            + list(plan.background)
        )
        assert sorted(all_pids) == list(range(20))


def test_heavy_avoidance_waits_noticeably_longer_than_prevention_on_average():
    # A regression guard for the redesign's headline finding: Avoidance's
    # conservative safety refusals cost meaningfully more waiting time than
    # Prevention's ordering refusals under Heavy contention. Uses a subset
    # of seeds to stay fast; the full 180-run experiment confirms this at
    # full scale (see IMPLEMENTATION_STATUS.md).
    from deadlock_sim.strategies.banker import BankerAvoidanceStrategy
    from deadlock_sim.strategies.prevention import PreventionStrategy

    subset = [101, 105, 110, 115, 120, 125, 130]
    prevention_waits = []
    avoidance_waits = []
    for seed in subset:
        wl = generate_heavy(seed)
        prevention_waits.append(Simulator(DEFAULT_CONFIG, wl, PreventionStrategy()).run().avg_waiting_time)
        avoidance_waits.append(Simulator(DEFAULT_CONFIG, wl, BankerAvoidanceStrategy()).run().avg_waiting_time)

    avg_prevention = sum(prevention_waits) / len(prevention_waits)
    avg_avoidance = sum(avoidance_waits) / len(avoidance_waits)
    assert avg_avoidance > avg_prevention * 1.3
