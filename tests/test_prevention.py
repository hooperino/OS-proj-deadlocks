from deadlock_sim.core.enums import RunStatus
from deadlock_sim.core.simulator import Simulator
from deadlock_sim.core.workload import ProcessWorkload
from deadlock_sim.strategies.prevention import PreventionStrategy

from .helpers import rel, req, workload


def test_descending_request_is_blocked_as_unnecessary_denial_when_available(config):
    # P0 holds Memory (rank 1) then requests CPU (rank 0) -- a descending
    # request. Nothing else in the system, so CPU is fully available: the
    # WAIT must be flagged unnecessary_denial (policy, not availability).
    pw = ProcessWorkload(
        pid=0,
        total_work=5,
        max_claim=(2, 2, 0, 0, 0),
        events=(
            req(0, 0, 0, (0, 2, 0, 0, 0), duration=1000),
            req(0, 1, 1, (2, 0, 0, 0, 0), duration=1000),
        ),
    )
    wl = workload([pw])
    sim = Simulator(config, wl, PreventionStrategy())
    for t in range(2):
        sim.state.current_tick = t
        sim._step1_expirations(t)
        due = sim._pop_due_events(t)
        from deadlock_sim.core.events import ReleaseEvent, RequestEvent

        releases = [(pid, ev) for _, pid, ev in due if isinstance(ev, ReleaseEvent)]
        requests = [(pid, ev) for _, pid, ev in due if isinstance(ev, RequestEvent)]
        sim._step2_releases(t, releases)
        sim._step3_recovery(t)
        sim._step4_requests(t, requests)
        sim._step5_pending(t)
        sim._step6_work()
        sim._step7_completion()
    assert sim._unnecessary_denials == 1
    assert 0 in sim.state.pending


def test_ascending_request_is_allowed(config):
    pw = ProcessWorkload(
        pid=0,
        total_work=3,
        max_claim=(2, 2, 0, 0, 0),
        events=(
            req(0, 0, 0, (2, 0, 0, 0, 0), duration=1000),  # CPU (rank 0)
            req(0, 1, 1, (0, 2, 0, 0, 0), duration=1000),  # Memory (rank 1) -- ascending
        ),
    )
    wl = workload([pw])
    result = Simulator(config, wl, PreventionStrategy()).run()
    assert result.status == RunStatus.COMPLETE
    assert result.unnecessary_denials == 0
    assert result.blocked_processes == 0


def test_blocked_descending_request_resolves_once_higher_rank_resource_is_released(config):
    pw = ProcessWorkload(
        pid=0,
        total_work=5,
        max_claim=(2, 2, 0, 0, 0),
        events=(
            req(0, 0, 0, (0, 2, 0, 0, 0), duration=1000),  # holds Memory (rank 1)
            req(0, 1, 1, (2, 0, 0, 0, 0), duration=1000),  # blocked: wants CPU (rank 0)
            rel(0, 4, 2),  # releases Memory -- highest_held_rank becomes -1
        ),
    )
    wl = workload([pw])
    result = Simulator(config, wl, PreventionStrategy()).run()
    assert result.status == RunStatus.COMPLETE
    assert result.blocked_processes == 1
    assert len(result.waiting_times) == 1
    # the pending CPU request could only be granted once Memory was released at tick 4
    assert result.waiting_times[0] >= 3
