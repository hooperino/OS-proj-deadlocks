"""The Simulator: the single authoritative execution engine.

Owns all state mutation, event scheduling, and metric accumulation.
Strategies are consulted for decisions only; every mutation described in the
project spec (resource accounting, timer expiration, completion, recovery
execution, work progression) happens here and only here.

Every tick executes in exactly this locked order (see project spec section
11):
    1. automatic holding-duration expirations
    2. explicit RELEASE events
    3. recovery actions
    4. REQUEST events
    5. pending-request reconsideration
    6. useful-work progression
    7. immediate process completion
"""

from __future__ import annotations

import dataclasses
import heapq
from typing import Dict, List, Tuple

import numpy as np

from deadlock_sim.core.actions import Strategy
from deadlock_sim.core.config import SimulationConfig
from deadlock_sim.core.enums import ProcessState, RequestDecision, RunStatus
from deadlock_sim.core.events import ReleaseEvent, RequestEvent, WorkloadEvent
from deadlock_sim.core.holdings import Holding, PendingRequest
from deadlock_sim.core.process import Process
from deadlock_sim.core.resources import ResourcePool
from deadlock_sim.core.result import SimulationResult
from deadlock_sim.core.state import SimulationState
from deadlock_sim.core.workload import Workload


class Simulator:
    """Runs exactly one (workload, strategy) pair to completion (or to
    max_ticks) from fresh state. Deterministic given config + workload +
    strategy."""

    def __init__(self, config: SimulationConfig, workload: Workload, strategy: Strategy):
        self.config = config
        self.workload = workload
        self.strategy = strategy
        self.max_ticks = config.max_ticks_for(workload.condition)
        self._events_by_pid: Dict[int, Tuple[WorkloadEvent, ...]] = {
            pw.pid: pw.events for pw in workload.processes
        }
        self._build_initial_state()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------
    def _build_initial_state(self) -> None:
        resources = ResourcePool(
            names=self.config.resource_names, capacity=self.config.capacities_array()
        )
        processes: Dict[int, Process] = {}
        for pw in self.workload.processes:
            processes[pw.pid] = Process(
                pid=pw.pid,
                total_work=pw.total_work,
                max_claim=np.array(pw.max_claim, dtype=np.int64),
            )
        self.state = SimulationState(config=self.config, resources=resources, processes=processes)

        self._heap: List[tuple] = []
        for pw in self.workload.processes:
            for event in pw.events:
                heapq.heappush(
                    self._heap, (event.timestamp, event.sequence_number, pw.pid, 0, event)
                )
        self._next_seq = self.workload.next_sequence_number

        # Metrics accumulators
        n = self.config.num_resources
        self._util_accum = np.zeros(n, dtype=np.float64)
        self._wasted_accum = np.zeros(n, dtype=np.float64)
        self._waiting_times: List[int] = []
        self._deadlock_episodes = 0
        self._recovery_actions = 0
        self._useful_work_lost = 0
        self._unnecessary_denials = 0
        self._restarted_pids: set = set()

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    def run(self) -> SimulationResult:
        status = RunStatus.INCOMPLETE
        ticks_elapsed = 0

        for t in range(self.max_ticks):
            self.state.current_tick = t

            self._step1_expirations(t)

            due = self._pop_due_events(t)
            release_events = [(pid, ev) for _, pid, ev in due if isinstance(ev, ReleaseEvent)]
            request_events = [(pid, ev) for _, pid, ev in due if isinstance(ev, RequestEvent)]

            self._step2_releases(t, release_events)
            self._step3_recovery(t)
            self._step4_requests(t, request_events)
            self._step5_pending(t)
            self._step6_work()
            self._step7_completion()

            self._util_accum += self.state.resources.held()
            ticks_elapsed = t + 1

            if all(p.state == ProcessState.COMPLETED for p in self.state.processes.values()):
                status = RunStatus.COMPLETE
                break

        return self._build_result(status, ticks_elapsed)

    # ------------------------------------------------------------------
    # Event popping
    # ------------------------------------------------------------------
    def _pop_due_events(self, t: int) -> List[tuple]:
        due = []
        while self._heap and self._heap[0][0] == t:
            _, seq, pid, generation, event = heapq.heappop(self._heap)
            process = self.state.processes[pid]
            if process.generation != generation:
                continue  # stale event from a life that has since restarted
            due.append((seq, pid, event))
        due.sort(key=lambda item: item[0])
        return due

    # ------------------------------------------------------------------
    # Step 1: holding-duration expirations
    # ------------------------------------------------------------------
    def _step1_expirations(self, t: int) -> None:
        expiring_ids = sorted(
            hid for hid, h in self.state.holdings.items() if h.expiration_tick == t
        )
        for hid in expiring_ids:
            holding = self.state.holdings.pop(hid)
            process = self.state.processes[holding.pid]
            process.allocation = process.allocation - holding.resources
            self.state.resources.release(holding.resources)

    # ------------------------------------------------------------------
    # Step 2: explicit RELEASE events
    # ------------------------------------------------------------------
    def _step2_releases(self, t: int, release_events: List[tuple]) -> None:
        # RELEASE fires on its scheduled tick regardless of whether the
        # process currently has an unresolved pending REQUEST -- the spec
        # models release as independent of the request/grant protocol (only
        # REQUEST is restricted to "at most one pending at a time", see
        # _step4_requests), and Prevention's own semantics explicitly rely on
        # a process being able to give up what it holds ("may become valid
        # later after higher-ranked resources are released") even while a
        # lower-ranked request it made remains blocked.
        for pid, _event in release_events:
            process = self.state.processes[pid]
            if process.state == ProcessState.COMPLETED:
                continue  # this life already finished before its own scheduled release
            self._release_all_holdings_and_allocation(pid)

    def _release_all_holdings_and_allocation(self, pid: int) -> None:
        process = self.state.processes[pid]
        if np.any(process.allocation):
            self.state.resources.release(process.allocation)
            process.allocation = np.zeros_like(process.allocation)
        stale_ids = [hid for hid, h in self.state.holdings.items() if h.pid == pid]
        for hid in stale_ids:
            del self.state.holdings[hid]

    # ------------------------------------------------------------------
    # Step 3: recovery actions
    # ------------------------------------------------------------------
    def _step3_recovery(self, t: int) -> None:
        result = self.strategy.periodic_check(self.state)
        if result.deadlock_detected:
            self._deadlock_episodes += 1
        for action in result.actions:
            self._terminate_and_restart(action.pid, t)

    def _terminate_and_restart(self, pid: int, t: int) -> None:
        process = self.state.processes[pid]

        # Resources-wasted accounting must happen before releasing.
        victim_holdings = [h for h in self.state.holdings.values() if h.pid == pid]
        for h in victim_holdings:
            self._wasted_accum += h.resources * (t - h.grant_tick)

        self._useful_work_lost += process.completed_work
        self._recovery_actions += 1
        self._restarted_pids.add(pid)

        self.state.pending.pop(pid, None)  # discard pending request
        self._release_all_holdings_and_allocation(pid)  # also cancels timers

        # Complete restart.
        process.generation += 1
        process.completed_work = 0
        process.allocation = np.zeros_like(process.max_claim)
        process.state = ProcessState.RUNNING
        process.times_restarted += 1

        for event in self._events_by_pid[pid]:
            shifted = self._shift_event(event, t)
            heapq.heappush(
                self._heap,
                (shifted.timestamp, shifted.sequence_number, pid, process.generation, shifted),
            )

    def _shift_event(self, event: WorkloadEvent, restart_tick: int) -> WorkloadEvent:
        new_seq = self._next_seq
        self._next_seq += 1
        return dataclasses.replace(
            event, timestamp=event.timestamp + restart_tick, sequence_number=new_seq
        )

    # ------------------------------------------------------------------
    # Step 4: REQUEST events
    # ------------------------------------------------------------------
    def _step4_requests(self, t: int, request_events: List[tuple]) -> None:
        for pid, event in request_events:
            process = self.state.processes[pid]

            if process.state == ProcessState.COMPLETED:
                continue  # this life already finished before this scheduled request

            if process.state == ProcessState.WAITING:
                # Process already has an unresolved pending request (at most
                # one allowed at a time). Defer this scheduled request until
                # the process is free again.
                deferred = dataclasses.replace(event, timestamp=t + 1)
                heapq.heappush(
                    self._heap,
                    (deferred.timestamp, deferred.sequence_number, pid, process.generation, deferred),
                )
                continue

            request_vec = np.array(event.request, dtype=np.int64)
            evaluation = self.strategy.evaluate_request(self.state, pid, request_vec)
            if evaluation.unnecessary_denial:
                self._unnecessary_denials += 1

            if evaluation.decision == RequestDecision.GRANT:
                self._apply_grant(pid, request_vec, event.duration, t)
            else:
                process.state = ProcessState.WAITING
                process.ever_waited = True
                self.state.pending[pid] = PendingRequest(
                    pid=pid,
                    request=request_vec,
                    waiting_start_tick=t,
                    sequence_number=event.sequence_number,
                    duration=event.duration,
                    generation=process.generation,
                )

    def _apply_grant(self, pid: int, request_vec: np.ndarray, duration: int, t: int) -> None:
        process = self.state.processes[pid]
        self.state.resources.allocate(request_vec)
        process.allocation = process.allocation + request_vec
        if np.any(request_vec):
            holding_id = self.state.new_holding_id()
            self.state.holdings[holding_id] = Holding(
                holding_id=holding_id,
                pid=pid,
                resources=request_vec.copy(),
                grant_tick=t,
                expiration_tick=t + duration,
                generation=process.generation,
            )
        process.state = ProcessState.RUNNING

    # ------------------------------------------------------------------
    # Step 5: pending-request reconsideration (FCFS)
    # ------------------------------------------------------------------
    def _step5_pending(self, t: int) -> None:
        items = sorted(
            self.state.pending.values(), key=lambda pr: (pr.waiting_start_tick, pr.sequence_number)
        )
        for pending in items:
            pid = pending.pid
            evaluation = self.strategy.evaluate_request(self.state, pid, pending.request)
            if evaluation.decision == RequestDecision.GRANT:
                self._apply_grant(pid, pending.request, pending.duration, t)
                del self.state.pending[pid]
                self._waiting_times.append(t - pending.waiting_start_tick)
            # else: remains WAITING; pending entry unchanged.

    # ------------------------------------------------------------------
    # Step 6: useful-work progression
    # ------------------------------------------------------------------
    def _step6_work(self) -> None:
        for process in self.state.processes.values():
            if process.state == ProcessState.RUNNING:
                process.completed_work += 1

    # ------------------------------------------------------------------
    # Step 7: immediate process completion
    # ------------------------------------------------------------------
    def _step7_completion(self) -> None:
        for process in self.state.processes.values():
            if process.state == ProcessState.RUNNING and process.completed_work >= process.total_work:
                self._release_all_holdings_and_allocation(process.pid)
                process.state = ProcessState.COMPLETED

    # ------------------------------------------------------------------
    # Result assembly
    # ------------------------------------------------------------------
    def _build_result(self, status: RunStatus, ticks_elapsed: int) -> SimulationResult:
        names = self.config.resource_names
        capacities = self.config.capacities_array().astype(np.float64)
        ticks = max(ticks_elapsed, 1)

        total_useful_work = int(sum(p.completed_work for p in self.state.processes.values()))
        throughput = total_useful_work / ticks

        resource_utilization = {
            names[i]: float(self._util_accum[i] / (capacities[i] * ticks)) for i in range(len(names))
        }
        overall_utilization = float(self._util_accum.sum() / (capacities.sum() * ticks))

        resources_wasted = {names[i]: float(self._wasted_accum[i]) for i in range(len(names))}
        total_resources_wasted = float(self._wasted_accum.sum())

        blocked_processes = sum(1 for p in self.state.processes.values() if p.ever_waited)
        avg_waiting_time = (
            float(sum(self._waiting_times) / len(self._waiting_times)) if self._waiting_times else 0.0
        )

        return SimulationResult(
            condition=self.workload.condition,
            seed=self.workload.seed,
            strategy=self.strategy.name,
            status=status,
            ticks_elapsed=ticks_elapsed,
            total_useful_work=total_useful_work,
            throughput=throughput,
            waiting_times=tuple(self._waiting_times),
            avg_waiting_time=avg_waiting_time,
            blocked_processes=blocked_processes,
            resource_utilization=resource_utilization,
            overall_utilization=overall_utilization,
            deadlock_episodes=self._deadlock_episodes,
            recovery_actions=self._recovery_actions,
            distinct_restarted_processes=len(self._restarted_pids),
            useful_work_lost=self._useful_work_lost,
            resources_wasted=resources_wasted,
            total_resources_wasted=total_resources_wasted,
            unnecessary_denials=self._unnecessary_denials,
            algorithm_overhead=self.strategy.overhead_stats(),
        )
