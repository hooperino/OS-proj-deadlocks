import numpy as np

from deadlock_sim.core.enums import ProcessState, RequestDecision, RunStatus
from deadlock_sim.core.events import ReleaseEvent, RequestEvent
from deadlock_sim.core.process import Process
from deadlock_sim.core.resources import ResourcePool
from deadlock_sim.core.simulator import Simulator
from deadlock_sim.core.state import SimulationState
from deadlock_sim.core.workload import ProcessWorkload
from deadlock_sim.strategies.banker import BankerAvoidanceStrategy

from .helpers import req, workload


def test_unsafe_request_is_refused_but_system_is_not_actually_deadlocked(config):
    # P0's max_claim is 10 but it only ever actually holds 5 (it never issues
    # a second request), so its remaining Need is 5, not 0. P1 wants 5 CPU
    # as its first step toward a max_claim of 10. Available(5) covers the
    # raw request, but tentatively granting it leaves zero slack while BOTH
    # P0's and P1's remaining Need (5 each) sit unmet -- genuinely unsafe.
    # Banker must refuse (WAIT), yet the system is not deadlocked: P0
    # completes on its own (total_work=5) and its completion auto-releases
    # its 5 CPU, after which P1's pending request succeeds normally.
    p0 = ProcessWorkload(
        pid=0, total_work=5, max_claim=(10, 0, 0, 0, 0), events=(req(0, 0, 0, (5, 0, 0, 0, 0), duration=1000),)
    )
    p1 = ProcessWorkload(
        pid=1,
        total_work=5,
        max_claim=(10, 0, 0, 0, 0),
        events=(req(1, 0, 1, (5, 0, 0, 0, 0), duration=1000),),
    )
    wl = workload([p0, p1])
    sim = Simulator(config, wl, BankerAvoidanceStrategy())
    result = sim.run()
    assert result.status == RunStatus.COMPLETE
    assert result.recovery_actions == 0  # Banker never needed recovery
    assert result.unnecessary_denials >= 1  # the refused-but-available request was flagged
    assert result.blocked_processes == 1
    # P1 could only proceed once P0 completed and released -- a real wait
    assert result.waiting_times[0] >= 1


def test_ordinary_unavailable_wait_is_not_flagged_unnecessary(config):
    p0 = ProcessWorkload(
        pid=0, total_work=5, max_claim=(5, 0, 0, 0, 0), events=(req(0, 0, 0, (5, 0, 0, 0, 0), duration=1000),)
    )
    p1 = ProcessWorkload(
        pid=1,
        total_work=5,
        max_claim=(10, 0, 0, 0, 0),
        events=(req(1, 0, 1, (8, 0, 0, 0, 0), duration=1000),),  # more than the 5 available -- raw shortage
    )
    wl = workload([p0, p1])
    sim = Simulator(config, wl, BankerAvoidanceStrategy())
    sim.state.current_tick = 0
    sim._step1_expirations(0)
    due = sim._pop_due_events(0)
    requests = [(pid, ev) for _, pid, ev in due if isinstance(ev, RequestEvent)]
    sim._step2_releases(0, [])
    sim._step3_recovery(0)
    sim._step4_requests(0, requests)
    assert 1 in sim.state.pending
    assert sim._unnecessary_denials == 0  # raw shortage, never reached the safety check


def _bare_state(config, processes):
    resources = ResourcePool(names=config.resource_names, capacity=config.capacities_array())
    return SimulationState(config=config, resources=resources, processes={p.pid: p for p in processes})


def test_multiple_safe_sequences_use_lowest_pid_tie_break(config):
    # Three processes with identical, simultaneously-satisfiable Need at
    # every step: every scan must pick the lowest remaining pid.
    processes = [
        Process(pid=pid, total_work=1, max_claim=np.array([1, 0, 0, 0, 0]))
        for pid in (2, 0, 1)  # deliberately out of order in the dict
    ]
    state = _bare_state(config, processes)
    strategy = BankerAvoidanceStrategy()
    safe, order = strategy.predicted_safe_sequence(state)
    assert safe
    assert order == [0, 1, 2]


def test_tentative_grant_never_touches_real_state_when_unsafe(config):
    p0 = Process(pid=0, total_work=5, max_claim=np.array([10, 0, 0, 0, 0]))
    p0.allocation = np.array([5, 0, 0, 0, 0])
    p1 = Process(pid=1, total_work=5, max_claim=np.array([10, 0, 0, 0, 0]))
    state = _bare_state(config, [p0, p1])
    state.resources.available = state.resources.capacity - p0.allocation

    before_available = state.resources.available.copy()
    before_alloc0 = p0.allocation.copy()
    before_alloc1 = p1.allocation.copy()

    strategy = BankerAvoidanceStrategy()
    evaluation = strategy.evaluate_request(state, 1, np.array([5, 0, 0, 0, 0]))
    assert evaluation.decision == RequestDecision.WAIT
    assert evaluation.unnecessary_denial is True
    # nothing about real state changed -- there was never a mutation to roll back
    assert list(state.resources.available) == list(before_available)
    assert list(p0.allocation) == list(before_alloc0)
    assert list(p1.allocation) == list(before_alloc1)


def test_predicted_safe_sequence_matches_actual_completion_order(config):
    # Three processes each need their whole claim (4 CPU) in a single
    # request; only two of ten CPU units' worth can run at once, so the
    # third must wait for one of the first two to finish and release.
    processes_wl = [
        ProcessWorkload(
            pid=pid,
            total_work=3,
            max_claim=(4, 0, 0, 0, 0),
            events=(req(pid, 0, pid, (4, 0, 0, 0, 0), duration=1000),),
        )
        for pid in (0, 1, 2)
    ]
    wl = workload(processes_wl)

    # Predicted order on the untouched initial state.
    init_state = _bare_state(
        config, [Process(pid=pid, total_work=3, max_claim=np.array([4, 0, 0, 0, 0])) for pid in (0, 1, 2)]
    )
    strategy_for_prediction = BankerAvoidanceStrategy()
    safe, predicted_order = strategy_for_prediction.predicted_safe_sequence(init_state)
    assert safe

    sim = Simulator(config, wl, BankerAvoidanceStrategy())
    completion_tick = {}
    for t in range(200):
        sim.state.current_tick = t
        sim._step1_expirations(t)
        due = sim._pop_due_events(t)
        releases = [(pid, ev) for _, pid, ev in due if isinstance(ev, ReleaseEvent)]
        requests = [(pid, ev) for _, pid, ev in due if isinstance(ev, RequestEvent)]
        sim._step2_releases(t, releases)
        sim._step3_recovery(t)
        sim._step4_requests(t, requests)
        sim._step5_pending(t)
        sim._step6_work()
        sim._step7_completion()
        for pid, p in sim.state.processes.items():
            if p.state == ProcessState.COMPLETED and pid not in completion_tick:
                completion_tick[pid] = t
        if len(completion_tick) == 3:
            break

    actual_order = sorted(completion_tick, key=lambda pid: completion_tick[pid])
    assert actual_order == predicted_order
