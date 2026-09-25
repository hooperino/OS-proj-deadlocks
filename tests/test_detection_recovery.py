from deadlock_sim.core.enums import ProcessState, RunStatus
from deadlock_sim.core.events import ReleaseEvent, RequestEvent
from deadlock_sim.core.simulator import Simulator
from deadlock_sim.core.workload import ProcessWorkload
from deadlock_sim.strategies.detection_recovery import DetectionRecoveryStrategy

from .helpers import rel, req, workload


def _cyclic_pair(pid_a, pid_b, res_a, res_b, cap_a, cap_b, t0, total_work=200, far_release=500):
    """Two processes that fully claim each other's resource, guaranteeing a
    genuine cyclic wait once both cross-request (see the generator module
    for the general form of this pattern)."""
    pa = ProcessWorkload(
        pid=pid_a,
        total_work=total_work,
        max_claim=tuple(cap_a if i == res_a else (cap_b if i == res_b else 0) for i in range(5)),
        events=(
            req(pid_a, t0, 10 * pid_a, tuple(cap_a if i == res_a else 0 for i in range(5)), duration=100),
            req(pid_a, t0 + 1, 10 * pid_a + 2, tuple(cap_b if i == res_b else 0 for i in range(5)), duration=100),
            rel(pid_a, t0 + far_release, 10 * pid_a + 4),
        ),
    )
    pb = ProcessWorkload(
        pid=pid_b,
        total_work=total_work,
        max_claim=tuple(cap_a if i == res_a else (cap_b if i == res_b else 0) for i in range(5)),
        events=(
            req(pid_b, t0, 10 * pid_a + 1, tuple(cap_b if i == res_b else 0 for i in range(5)), duration=100),
            req(pid_b, t0 + 1, 10 * pid_a + 3, tuple(cap_a if i == res_a else 0 for i in range(5)), duration=100),
            rel(pid_b, t0 + far_release, 10 * pid_a + 5),
        ),
    )
    return pa, pb


def test_genuine_deadlock_is_detected_and_recovered(config):
    p0, p1 = _cyclic_pair(0, 1, res_a=1, res_b=0, cap_a=8, cap_b=10, t0=1)
    wl = workload([p0, p1])
    result = Simulator(config, wl, DetectionRecoveryStrategy()).run()
    assert result.status == RunStatus.COMPLETE
    assert result.deadlock_episodes >= 1
    assert result.recovery_actions >= 1
    assert result.useful_work_lost >= 0
    assert result.ticks_elapsed < 500  # recovery must have preempted the far-future natural release


def test_episode_counted_once_even_when_two_independent_groups_need_two_victims(config):
    # Group A: P0/P1 cycle on CPU/Memory. Group B: P2/P3 cycle on GPU/Disk.
    # Both formed by the same detection tick -- one detection tick, one
    # episode, but two separate victim terminations (one per group).
    p0, p1 = _cyclic_pair(0, 1, res_a=1, res_b=0, cap_a=8, cap_b=10, t0=1)
    p2, p3 = _cyclic_pair(2, 3, res_a=3, res_b=2, cap_a=12, cap_b=6, t0=1)
    wl = workload([p0, p1, p2, p3])
    result = Simulator(config, wl, DetectionRecoveryStrategy()).run()
    assert result.status == RunStatus.COMPLETE
    assert result.deadlock_episodes == 1
    assert result.recovery_actions == 2


def test_victim_selection_prefers_lowest_completed_work_over_lowest_pid(config):
    # Symmetric cyclic pair (see test_detection_recovery for the general
    # shape). Right before the deadlock forms, we directly set pid 1's
    # completed_work lower than pid 0's. If selection used pid alone, pid 0
    # (lowest pid) would be picked -- but completed_work is checked first,
    # so pid 1 must be the victim despite its higher pid.
    p0 = ProcessWorkload(
        pid=0,
        total_work=200,
        max_claim=(10, 8, 0, 0, 0),
        events=(
            req(0, 1, 0, (0, 8, 0, 0, 0), duration=100),
            req(0, 2, 2, (10, 0, 0, 0, 0), duration=100),
            rel(0, 500, 4),
        ),
    )
    p1 = ProcessWorkload(
        pid=1,
        total_work=200,
        max_claim=(10, 8, 0, 0, 0),
        events=(
            req(1, 1, 1, (10, 0, 0, 0, 0), duration=100),
            req(1, 2, 3, (0, 8, 0, 0, 0), duration=100),
            rel(1, 500, 5),
        ),
    )
    wl = workload([p0, p1])
    sim = Simulator(config, wl, DetectionRecoveryStrategy())

    for t in range(3):
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
    # both now WAITING on each other (0 wants CPU held by 1; 1 wants Memory held by 0)
    assert sim.state.processes[0].state == ProcessState.WAITING
    assert sim.state.processes[1].state == ProcessState.WAITING
    sim.state.processes[0].completed_work = 50
    sim.state.processes[1].completed_work = 5  # artificially lower -- must be picked despite higher pid

    # force the detection tick regardless of the real interval/tick value
    sim.state.current_tick = 10
    result = sim.strategy.periodic_check(sim.state)
    assert result.deadlock_detected
    assert [a.pid for a in result.actions] == [1]


def test_full_restart_resets_process_state_and_replays_original_events(config):
    p0, p1 = _cyclic_pair(0, 1, res_a=1, res_b=0, cap_a=8, cap_b=10, t0=1)
    wl = workload([p0, p1])
    sim = Simulator(config, wl, DetectionRecoveryStrategy())
    result = sim.run()
    assert result.recovery_actions >= 1
    victim_pid = 0 if sim.state.processes[0].times_restarted >= 1 else 1
    victim = sim.state.processes[victim_pid]
    assert victim.times_restarted >= 1
    assert victim.generation >= 1
    # a fully restarted (or completed-after-restart) process must show no
    # leftover pending request and, if still active, zero allocation
    assert victim_pid not in sim.state.pending


def test_repeated_recovery_losses_accumulate_across_multiple_terminations(config):
    pw = ProcessWorkload(
        pid=0, total_work=1000, max_claim=(0, 0, 0, 0, 0), events=(req(0, 0, 0, (0, 0, 0, 0, 0), duration=1),)
    )
    wl = workload([pw])
    sim = Simulator(config, wl, DetectionRecoveryStrategy())

    # Let it accumulate some work, then manually terminate it (white-box
    # test of the accumulation invariant itself).
    for t in range(5):
        sim.state.current_tick = t
        sim._step1_expirations(t)
        sim._step2_releases(t, [])
        sim._step3_recovery(t)
        sim._step4_requests(t, [])
        sim._step5_pending(t)
        sim._step6_work()
        sim._step7_completion()
    assert sim.state.processes[0].completed_work == 5
    sim._terminate_and_restart(0, 5)
    assert sim._useful_work_lost == 5

    for t in range(6, 9):
        sim.state.current_tick = t
        sim._step1_expirations(t)
        sim._step2_releases(t, [])
        sim._step3_recovery(t)
        sim._step4_requests(t, [])
        sim._step5_pending(t)
        sim._step6_work()
        sim._step7_completion()
    assert sim.state.processes[0].completed_work == 3
    sim._terminate_and_restart(0, 9)
    assert sim._useful_work_lost == 5 + 3  # accumulated, not overwritten


def test_completion_eventually_frees_resources_for_a_waiting_process(config):
    p0 = ProcessWorkload(
        pid=0, total_work=3, max_claim=(10, 0, 0, 0, 0), events=(req(0, 0, 0, (10, 0, 0, 0, 0), duration=1000),)
    )
    p1 = ProcessWorkload(
        pid=1, total_work=1, max_claim=(10, 0, 0, 0, 0), events=(req(1, 0, 1, (10, 0, 0, 0, 0), duration=1000),)
    )
    wl = workload([p0, p1])
    result = Simulator(config, wl, DetectionRecoveryStrategy()).run()
    assert result.status == RunStatus.COMPLETE
    assert result.blocked_processes == 1
    assert result.deadlock_episodes == 0  # ordinary contention, not a cycle
    assert result.recovery_actions == 0


def test_all_active_processes_can_be_simultaneously_waiting(config):
    p0, p1 = _cyclic_pair(0, 1, res_a=1, res_b=0, cap_a=8, cap_b=10, t0=1)
    wl = workload([p0, p1])
    sim = Simulator(config, wl, DetectionRecoveryStrategy())
    saw_all_waiting = False
    for t in range(10):
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
        active = [p for p in sim.state.processes.values() if p.state != ProcessState.COMPLETED]
        if active and all(p.state == ProcessState.WAITING for p in active):
            saw_all_waiting = True
    assert saw_all_waiting
