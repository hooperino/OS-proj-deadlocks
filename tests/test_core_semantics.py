from deadlock_sim.core.config import SimulationConfig
from deadlock_sim.core.enums import Condition, RunStatus
from deadlock_sim.core.events import ReleaseEvent, RequestEvent
from deadlock_sim.core.simulator import Simulator
from deadlock_sim.core.workload import ProcessWorkload
from deadlock_sim.strategies.prevention import PreventionStrategy

from .helpers import rel, req, workload


def test_zero_resource_request_grants_immediately_with_no_holding(config):
    pw = ProcessWorkload(
        pid=0,
        total_work=3,
        max_claim=(0, 0, 0, 0, 0),
        events=(req(0, 0, 0, (0, 0, 0, 0, 0), duration=5),),
    )
    wl = workload([pw])
    sim = Simulator(config, wl, PreventionStrategy())
    result = sim.run()
    assert result.status == RunStatus.COMPLETE
    assert result.ticks_elapsed == 3
    assert result.unnecessary_denials == 0
    # a zero-resource grant must not create a holding (no timer per spec)
    assert len(sim.state.holdings) == 0


def test_single_instance_resource_mutual_exclusion():
    # A custom config with capacity 1 for every resource models classic
    # single-instance (mutex-like) resources.
    cfg = SimulationConfig(capacities=(1, 1, 1, 1, 1))
    p0 = ProcessWorkload(
        pid=0,
        total_work=10,
        max_claim=(1, 0, 0, 0, 0),
        events=(req(0, 0, 0, (1, 0, 0, 0, 0), duration=3), rel(0, 5, 2)),
    )
    p1 = ProcessWorkload(
        pid=1,
        total_work=10,
        max_claim=(1, 0, 0, 0, 0),
        events=(req(1, 0, 1, (1, 0, 0, 0, 0), duration=3),),
    )
    wl = workload([p0, p1])
    sim = Simulator(cfg, wl, PreventionStrategy())
    result = sim.run()
    assert result.status == RunStatus.COMPLETE
    # P1 must have waited (only one unit exists; P0 held it first)
    assert result.blocked_processes == 1
    assert len(result.waiting_times) == 1
    assert result.waiting_times[0] > 0


def test_max_ticks_reached_marks_incomplete():
    cfg = SimulationConfig(max_ticks_light=5)
    pw = ProcessWorkload(
        pid=0,
        total_work=100,  # cannot possibly finish in 5 ticks
        max_claim=(0, 0, 0, 0, 0),
        events=(req(0, 0, 0, (0, 0, 0, 0, 0), duration=1),),
    )
    wl = workload([pw], condition=Condition.LIGHT)
    sim = Simulator(cfg, wl, PreventionStrategy())
    result = sim.run()
    assert result.status == RunStatus.INCOMPLETE
    assert result.ticks_elapsed == 5
    assert result.total_useful_work < 100


def test_holding_expiration_releases_only_that_holding(config):
    # P0 grabs CPU for 3 ticks (expires tick 3), then grabs Memory for 100
    # ticks (while still holding CPU) at tick 1.
    pw = ProcessWorkload(
        pid=0,
        total_work=20,
        max_claim=(4, 4, 0, 0, 0),
        events=(
            req(0, 0, 0, (4, 0, 0, 0, 0), duration=3),
            req(0, 1, 1, (0, 4, 0, 0, 0), duration=100),
        ),
    )
    wl = workload([pw])
    sim = Simulator(config, wl, PreventionStrategy())

    for t in range(4):
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
        p0 = sim.state.processes[0]
        if t == 2:
            assert list(p0.allocation) == [4, 4, 0, 0, 0]
            assert sim.state.resources.available[0] == 6  # CPU still held
        if t == 3:
            # CPU holding (duration=3, granted tick 0) expires exactly at tick 3
            assert list(p0.allocation) == [0, 4, 0, 0, 0]
            assert sim.state.resources.available[0] == 10  # CPU fully released
            assert sim.state.resources.available[1] == 4  # Memory still held


def test_multiple_overlapping_holdings_expire_independently(config):
    pw = ProcessWorkload(
        pid=0,
        total_work=20,
        max_claim=(3, 3, 0, 0, 0),
        events=(
            req(0, 0, 0, (3, 0, 0, 0, 0), duration=2),   # expires tick 2
            req(0, 0, 1, (0, 3, 0, 0, 0), duration=5),   # expires tick 5, same tick as the CPU grab
        ),
    )
    wl = workload([pw])
    sim = Simulator(config, wl, PreventionStrategy())
    for t in range(6):
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
        if t == 0:
            assert len(sim.state.holdings) == 2
        if t == 2:
            assert len(sim.state.holdings) == 1  # only the CPU holding expired
            assert list(sim.state.processes[0].allocation) == [0, 3, 0, 0, 0]
        if t == 5:
            assert len(sim.state.holdings) == 0
            assert list(sim.state.processes[0].allocation) == [0, 0, 0, 0, 0]


def test_explicit_release_releases_all_current_holdings_at_once(config):
    pw = ProcessWorkload(
        pid=0,
        total_work=20,
        max_claim=(3, 3, 0, 0, 0),
        events=(
            req(0, 0, 0, (3, 0, 0, 0, 0), duration=1000),
            req(0, 1, 1, (0, 3, 0, 0, 0), duration=1000),
            rel(0, 5, 2),
        ),
    )
    wl = workload([pw])
    sim = Simulator(config, wl, PreventionStrategy())
    for t in range(6):
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
    assert list(sim.state.processes[0].allocation) == [0, 0, 0, 0, 0]
    assert len(sim.state.holdings) == 0
    assert list(sim.state.resources.available) == list(config.capacities)


def test_release_of_nothing_held_is_a_valid_no_op(config):
    pw = ProcessWorkload(
        pid=0, total_work=5, max_claim=(0, 0, 0, 0, 0), events=(rel(0, 0, 0),)
    )
    wl = workload([pw])
    result = Simulator(config, wl, PreventionStrategy()).run()
    assert result.status == RunStatus.COMPLETE


def test_tick_order_release_before_request_lets_same_tick_handoff_succeed(config):
    # P0 releases CPU at the exact tick P1 requests all of it. Because
    # explicit RELEASE (step 2) precedes REQUEST evaluation (step 4) within
    # the same tick, P1's request must succeed immediately, not wait a tick.
    p0 = ProcessWorkload(
        pid=0,
        total_work=10,
        max_claim=(10, 0, 0, 0, 0),
        events=(req(0, 0, 0, (10, 0, 0, 0, 0), duration=1000), rel(0, 3, 1)),
    )
    p1 = ProcessWorkload(
        pid=1,
        total_work=10,
        max_claim=(10, 0, 0, 0, 0),
        events=(req(1, 3, 2, (10, 0, 0, 0, 0), duration=1000),),
    )
    wl = workload([p0, p1])
    sim = Simulator(config, wl, PreventionStrategy())
    result = sim.run()
    assert result.status == RunStatus.COMPLETE
    assert result.blocked_processes == 0  # P1 never had to wait a single tick


def test_completion_and_coincident_holding_expiration_leave_consistent_state(config):
    # total_work=3 completes P0 at the end of tick 2 (step 7). Its own grant
    # also happens to have expiration_tick=2 (step 1 of the same tick).
    # Either path must leave a fully consistent end state: no leftover
    # holdings, zero allocation, resources fully returned.
    pw = ProcessWorkload(
        pid=0,
        total_work=3,
        max_claim=(5, 0, 0, 0, 0),
        events=(req(0, 0, 0, (5, 0, 0, 0, 0), duration=2),),
    )
    wl = workload([pw])
    sim = Simulator(config, wl, PreventionStrategy())
    result = sim.run()
    assert result.status == RunStatus.COMPLETE
    assert len(sim.state.holdings) == 0
    assert list(sim.state.resources.available) == list(config.capacities)


def test_grant_at_tick_t_contributes_work_at_tick_t(config):
    # A request granted at tick t must let the process do useful work in
    # that same tick (not only from t+1 onward).
    pw = ProcessWorkload(
        pid=0,
        total_work=1,
        max_claim=(1, 0, 0, 0, 0),
        events=(req(0, 0, 0, (1, 0, 0, 0, 0), duration=5),),
    )
    wl = workload([pw])
    result = Simulator(config, wl, PreventionStrategy()).run()
    assert result.status == RunStatus.COMPLETE
    assert result.ticks_elapsed == 1
