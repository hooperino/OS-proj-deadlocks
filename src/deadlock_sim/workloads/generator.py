"""Light and Heavy workload generators.

Redesign rationale
-------------------
An earlier version of this generator used a single recurring template
(process A grabs a big share of resource X then crosses to Y; process B
mirrors it) for all strategic pressure at once. That pattern happened to
touch all three strategies simultaneously, but it *conflated* them: a
Prevention "unnecessary denial" and a Banker "unnecessary denial" were both
mostly just artifacts of raw two-party resource overflow, so Banker's
unique contribution (refusing a request that is *currently available* but
would make the system unsafe) rarely showed up on its own, and Light's
weaker intensity made Avoidance and Detection+Recovery behave identically
to each other (0 waiting, 0 denials, 0 episodes) -- no signal at all.

This version builds three *separate* pattern types, each engineered to
isolate exactly one strategy's distinguishing cost, and mixes them with
plain ordinary background processes so the workload still reads as a
controlled experimental mix rather than a wall-to-wall adversarial
benchmark:

1. **Ordering-violation processes** (`_build_ordering_violation`) --
   Prevention pressure. A single process holds a higher-ranked resource
   then requests a *modest* amount of a lower-ranked one. The amount is
   deliberately kept small relative to capacity so it is almost always
   genuinely available -- the WAIT this produces under Prevention is
   attributable to the ordering rule itself, not to raw scarcity, so it
   reliably registers as `unnecessary_denial`. Needs no partner process, so
   it is cheap to sprinkle across many otherwise-ordinary processes.

2. **Banker-trap groups** (`_build_banker_trap_group`) -- Avoidance
   pressure. N processes are given claims on one shared resource sized so
   that after N-1 of them make their first (modest, non-blocking) grab, the
   last process's request is *currently satisfiable from Available* but
   would leave *every* process (including the requester) with positive
   remaining Need and zero slack -- the textbook unsafe state. This is
   solved generally: pick the per-process cap M = floor(capacity *
   intensity_cap), target each process's post-grant allocation at M-1 (so
   Need stays positive), and use enough processes that those allocations
   can sum to exactly `capacity` (so Available after the grant is exactly
   0, which alone is sufficient for every positive-Need process to fail the
   safety check). Detection+Recovery and Prevention both just grant this
   (it's available, and nothing here violates ordering) and carry on --
   only Avoidance pays a cost here, which is exactly the point.

3. **Deadlock cycles** (`_build_deadlock_pair` / `_build_deadlock_triple`)
   -- Detection+Recovery pressure, now genuinely varied. 2-process cycles
   pick an arbitrary (not just adjacent) resource pair each time, and Heavy
   additionally includes a real 3-process cycle (P0 holds A wants B, P1
   holds B wants C, P2 holds C wants A) -- three distinct resources, three
   distinct bilateral-overflow relationships, one detection+recovery
   episode that the algorithm must resolve by walking the chain, not just
   flipping a coin. As before, claim intensity is sized so bilateral
   overflow (and hence a genuine, unavoidable cyclic wait) is *guaranteed*
   under Heavy's 70% cap and only *possible-with-help-from-other-processes*
   under Light's 40% cap, matching the spec's "Light: lower deadlock
   frequency" requirement -- this piece of the design is carried over
   unchanged from the previous generator.

Both Light and Heavy get at least one instance of each of the three
patterns (Light: smaller/fewer; Heavy: bigger/more), and the remainder of
each seed's 20 processes are plain ordinary background load, so no seed is
"all adversarial, no realism". See `_plan_for` for the exact per-role pid
budget.

All randomness is drawn from a single `random.Random` seeded from
`(condition, seed)`, in a fixed, seed-independent order of operations, so
generation is fully deterministic: the same seed + condition always
produces byte-for-byte the same Workload.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from itertools import combinations
from typing import Dict, List, Optional, Sequence, Tuple

from deadlock_sim.core.config import DEFAULT_CONFIG, SimulationConfig
from deadlock_sim.core.enums import Condition
from deadlock_sim.core.events import ReleaseEvent, RequestEvent, WorkloadEvent
from deadlock_sim.core.workload import ProcessWorkload, Workload

_TOTAL_WORK_RANGE = (50, 150)

# All C(5,2)=10 distinct resource-index pairs, used for varied deadlock
# cycles and ordering-violation choices (instead of only adjacent ranks).
_ALL_PAIRS: Tuple[Tuple[int, int], ...] = tuple(combinations(range(5), 2))
_ALL_TRIPLES: Tuple[Tuple[int, int, int], ...] = tuple(combinations(range(5), 3))


@dataclass(frozen=True)
class _ConditionParams:
    num_requests_range: Tuple[int, int]
    duration_range: Tuple[int, int]
    ordinary_intensity: float
    pair_intensity: float
    cap_fraction: float
    max_ticks: int


@dataclass(frozen=True)
class _ProcessPlan:
    """The per-role pid budget for one condition. Every pid in
    `0..num_processes-1` is assigned to exactly one role."""

    banker_groups: Tuple[Tuple[int, ...], ...]  # each inner tuple = one group's pids
    deadlock_pairs: Tuple[Tuple[int, int], ...]
    deadlock_triples: Tuple[Tuple[int, int, int], ...]
    ordering_violation: Tuple[int, ...]
    background: Tuple[int, ...]


def _params_for(condition: Condition, config: SimulationConfig) -> _ConditionParams:
    if condition is Condition.LIGHT:
        return _ConditionParams(
            num_requests_range=(3, 5),
            duration_range=(1, 5),
            ordinary_intensity=0.40,
            pair_intensity=0.35,
            cap_fraction=0.40,
            max_ticks=config.max_ticks_light,
        )
    return _ConditionParams(
        num_requests_range=(6, 8),
        duration_range=(5, 10),
        ordinary_intensity=0.70,
        pair_intensity=0.65,
        cap_fraction=0.70,
        max_ticks=config.max_ticks_heavy,
    )


def _plan_for(condition: Condition) -> _ProcessPlan:
    if condition is Condition.LIGHT:
        # 4 (banker) + 2 (one 2-cycle) + 3 (ordering bonus) + 11 (background) = 20
        return _ProcessPlan(
            banker_groups=((0, 1, 2, 3),),
            deadlock_pairs=((4, 5),),
            deadlock_triples=(),
            ordering_violation=(6, 7, 8),
            background=tuple(range(9, 20)),
        )
    # 3+3 (two banker groups) + 4 (two 2-cycles) + 3 (3-cycle) + 5 (ordering bonus) + 2 (background) = 20
    return _ProcessPlan(
        banker_groups=((0, 1, 2), (3, 4, 5)),
        deadlock_pairs=((6, 7), (8, 9)),
        deadlock_triples=((10, 11, 12),),
        ordering_violation=(13, 14, 15, 16, 17),
        background=(18, 19),
    )


# A draft event is a plain tuple, sequence-number-free, so we can assign
# final global sequence numbers only after every process's events exist:
#   ("REQUEST", pid, timestamp, request_tuple, duration)
#   ("RELEASE", pid, timestamp)
_DraftEvent = tuple


def generate_light(seed: int, config: SimulationConfig = DEFAULT_CONFIG) -> Workload:
    return _generate(Condition.LIGHT, seed, config)


def generate_heavy(seed: int, config: SimulationConfig = DEFAULT_CONFIG) -> Workload:
    return _generate(Condition.HEAVY, seed, config)


def _vec(num_resources: int, spec: Dict[int, int]) -> Tuple[int, ...]:
    values = [0] * num_resources
    for r, amount in spec.items():
        values[r] = amount
    return tuple(values)


def _bilateral_overflow_amount(capacity: int, pair_intensity: float, cap_fraction: float) -> int:
    """An amount that, claimed by two parties on the same resource,
    guarantees combined demand exceeds capacity (amount > capacity/2),
    while respecting the condition's hard intensity cap."""
    over_half = capacity // 2 + 1
    target = max(1, int(capacity * pair_intensity))
    capped = max(1, int(capacity * cap_fraction))
    return min(max(over_half, target), capped)


def _split_into_parts(total: int, num_parts: int, rng: random.Random) -> List[int]:
    """Split `total` into `num_parts` positive integers summing to total.
    If num_parts > total, returns `total` parts of 1 each (can't have more
    positive-integer parts than the total itself)."""
    num_parts = max(1, min(num_parts, total))
    if num_parts <= 1:
        return [total]
    cuts = sorted(rng.sample(range(1, total), num_parts - 1))
    parts = []
    prev = 0
    for c in cuts:
        parts.append(c - prev)
        prev = c
    parts.append(total - prev)
    return parts


def _build_incremental_requests(
    rng: random.Random,
    pid: int,
    eligible_resources: Sequence[int],
    capacities: Sequence[int],
    num_resources: int,
    num_requests: int,
    intensity: float,
    duration_range: Tuple[int, int],
    start_time: int,
) -> Tuple[List[_DraftEvent], Dict[int, int], int]:
    """One process lifecycle block: claim 2-4 resources (or fewer if
    `eligible_resources` is smaller), split the claim into *exactly*
    `num_requests` incremental REQUEST events, followed by exactly one
    RELEASE.

    The split is deterministic-by-construction (`_split_into_parts`) rather
    than hoping random per-draw amounts happen to leave enough remaining
    budget for every requested event -- a claim too small/few to support
    `num_requests` distinct >=1-unit chunks is topped up by claiming
    additional eligible resources (still capped at 4 claimed resources, per
    "most processes claim 2-4 resource types") before falling back to
    however many events the available claim can actually support.

    Returns (draft_events, max_claim_contribution, release_timestamp).
    """
    num_requests = max(1, num_requests)
    num_claimed = min(len(eligible_resources), max(1, rng.randint(2, 4)))
    claimed = sorted(rng.sample(list(eligible_resources), k=num_claimed)) if eligible_resources else []
    max_claim = {r: max(1, int(capacities[r] * intensity)) for r in claimed}

    remaining_pool = [r for r in eligible_resources if r not in claimed]
    while sum(max_claim.values()) < num_requests and remaining_pool and len(claimed) < 4:
        new_r = remaining_pool.pop(rng.randrange(len(remaining_pool)))
        claimed.append(new_r)
        max_claim[new_r] = max(1, int(capacities[new_r] * intensity))
    claimed.sort()

    if not claimed:
        events = [("RELEASE", pid, start_time)]
        return events, {}, start_time

    base = max(1, num_requests // len(claimed))
    parts_per_resource = {r: min(base, max_claim[r]) for r in claimed}
    shortfall = num_requests - sum(parts_per_resource.values())
    cycle = list(claimed)
    i = 0
    while shortfall > 0 and i < 10000:
        r = cycle[i % len(cycle)]
        if parts_per_resource[r] < max_claim[r]:
            parts_per_resource[r] += 1
            shortfall -= 1
        i += 1
        if all(parts_per_resource[r] >= max_claim[r] for r in cycle):
            break  # every claimed resource is fully split into 1-unit chunks; can't add more

    chunks: List[Tuple[int, int]] = []
    for r in claimed:
        for amount in _split_into_parts(max_claim[r], parts_per_resource[r], rng):
            chunks.append((r, amount))
    rng.shuffle(chunks)

    # Exactly num_requests events when the claim has enough chunks; fewer
    # only in the (essentially unreachable, for our real parameter ranges)
    # case where 4 claimed resources still can't muster num_requests units.
    request_specs: List[Dict[int, int]] = [dict() for _ in range(min(num_requests, len(chunks)))]
    for idx, (r, amount) in enumerate(chunks):
        slot = request_specs[idx % len(request_specs)]
        slot[r] = slot.get(r, 0) + amount

    events: List[_DraftEvent] = []
    t = start_time
    for spec in request_specs:
        duration = rng.randint(*duration_range)
        events.append(("REQUEST", pid, t, _vec(num_resources, spec), duration))
        t += rng.randint(1, 4)
    release_t = t + rng.randint(2, 6)
    events.append(("RELEASE", pid, release_t))
    return events, max_claim, release_t


def _pad_to_request_count(
    rng: random.Random,
    pid: int,
    core_requests_used: int,
    exclude_resources: Sequence[int],
    capacities: Sequence[int],
    num_resources: int,
    params: _ConditionParams,
    start_time: int,
) -> Tuple[List[_DraftEvent], Dict[int, int]]:
    """Ordinary incremental activity on resources *other* than the ones a
    structured pattern already used for this pid, bringing its total
    request count up to the condition's required range and supplying its
    required RELEASE."""
    target_total = rng.randint(*params.num_requests_range)
    extra_needed = max(1, target_total - core_requests_used)
    eligible = [r for r in range(num_resources) if r not in exclude_resources]
    if not eligible:
        eligible = list(range(num_resources))
    events, claim, _ = _build_incremental_requests(
        rng, pid, eligible, capacities, num_resources, extra_needed,
        params.ordinary_intensity, params.duration_range, start_time=start_time,
    )
    return events, claim


# ---------------------------------------------------------------------
# Pattern 1: ordering-violation processes (Prevention pressure)
# ---------------------------------------------------------------------
def _build_ordering_violation(
    rng: random.Random,
    pid: int,
    capacities: Sequence[int],
    num_resources: int,
    params: _ConditionParams,
    t0: int,
) -> Tuple[List[_DraftEvent], Dict[int, int], int]:
    """Holds a higher-ranked resource, then requests a *modest* amount of a
    lower-ranked one -- an ordering violation under Prevention. The amount
    is kept small (15-25% of capacity, well under the intensity cap) so it
    is almost always genuinely available, keeping the resulting WAIT
    attributable to policy rather than scarcity."""
    hi, lo = sorted(rng.sample(range(num_resources), 2), reverse=True)

    def _modest(capacity: int) -> int:
        frac = rng.uniform(0.15, 0.25)
        return max(1, min(int(capacity * frac), int(capacity * params.cap_fraction)))

    amt_hi = _modest(capacities[hi])
    amt_lo = _modest(capacities[lo])
    gap = rng.randint(1, 3)
    duration_hi = rng.randint(*params.duration_range)
    duration_lo = rng.randint(*params.duration_range)

    events: List[_DraftEvent] = [
        ("REQUEST", pid, t0, _vec(num_resources, {hi: amt_hi}), duration_hi),
        ("REQUEST", pid, t0 + gap, _vec(num_resources, {lo: amt_lo}), duration_lo),
    ]
    max_claim = {hi: amt_hi, lo: amt_lo}
    return events, max_claim, t0 + gap


# ---------------------------------------------------------------------
# Pattern 2: Banker-trap groups (Avoidance pressure)
# ---------------------------------------------------------------------
def _build_banker_trap_group(
    rng: random.Random,
    pids: Sequence[int],
    resource: int,
    capacities: Sequence[int],
    num_resources: int,
    params: _ConditionParams,
    t0: int,
) -> Optional[Tuple[Dict[int, List[_DraftEvent]], Dict[int, Dict[int, int]], int]]:
    """N processes claim `resource`. All but the last make an initial,
    individually-modest grab; the last (the "requester") then asks for
    enough that -- while still currently *available* -- the resulting
    allocation leaves Available at exactly 0 with every process's Need
    still positive: the classic available-but-unsafe state. Returns None if
    infeasible for this (resource, N, intensity cap) combination (the
    caller should pick a different resource/group size)."""
    capacity = capacities[resource]
    cap = max(2, int(capacity * params.cap_fraction))  # per-process max_claim M
    slack = cap - 1  # target post-grant allocation per process (keeps Need >= 1)
    n = len(pids)
    if n * slack < capacity or slack <= 0:
        return None

    allocs = [slack] * n
    excess = sum(allocs) - capacity
    requester_idx = n - 1
    # Reduce non-requester allocations first -- the requester's own
    # allocation is what gets tentatively evaluated by Banker, so it must
    # stay positive (a zero-amount "request" would trivially grant and test
    # nothing).
    i = 0
    while excess > 0 and i < n:
        if i == requester_idx:
            i += 1
            continue
        reduce = min(allocs[i], excess)
        allocs[i] -= reduce
        excess -= reduce
        i += 1
    if excess > 0:
        reduce = min(allocs[requester_idx], excess)
        allocs[requester_idx] -= reduce
        excess -= reduce
    if sum(allocs) != capacity or allocs[requester_idx] <= 0:
        return None

    requester = pids[-1]
    gap = rng.randint(1, 3)
    duration = rng.randint(*params.duration_range)

    events_by_pid: Dict[int, List[_DraftEvent]] = {}
    max_claim_by_pid: Dict[int, Dict[int, int]] = {}
    for idx, pid in enumerate(pids):
        amount = allocs[idx]
        ts = t0 if pid != requester else t0 + gap
        ev: List[_DraftEvent] = []
        if amount > 0:
            ev.append(("REQUEST", pid, ts, _vec(num_resources, {resource: amount}), duration))
        events_by_pid[pid] = ev
        max_claim_by_pid[pid] = {resource: cap}

    return events_by_pid, max_claim_by_pid, t0 + gap


# ---------------------------------------------------------------------
# Pattern 3: deadlock cycles (Detection+Recovery pressure)
# ---------------------------------------------------------------------
def _build_deadlock_pair(
    rng: random.Random,
    pid_a: int,
    pid_b: int,
    resource_a: int,
    resource_b: int,
    k: int,
    capacities: Sequence[int],
    num_resources: int,
    params: _ConditionParams,
) -> Tuple[Dict[int, List[_DraftEvent]], Dict[int, Dict[int, int]], int]:
    """Two processes cross-claim an arbitrary pair of resources (not
    necessarily adjacent in rank). t0 = 10*k + 1 keeps the pattern far
    below the 50-tick total_work floor and (for Heavy's max duration, 10)
    guarantees the next detection tick lands while the cycle is still
    active. Claim sizing guarantees bilateral overflow under Heavy's cap;
    under Light's cap this is not mathematically guaranteed (see module
    docstring) and that's intentional."""
    amt_a = _bilateral_overflow_amount(capacities[resource_a], params.pair_intensity, params.cap_fraction)
    amt_b = _bilateral_overflow_amount(capacities[resource_b], params.pair_intensity, params.cap_fraction)
    max_duration = params.duration_range[1]
    gap = 1
    t0 = 10 * k + 1

    events_a: List[_DraftEvent] = [
        ("REQUEST", pid_a, t0, _vec(num_resources, {resource_a: amt_a}), max_duration),
        ("REQUEST", pid_a, t0 + gap, _vec(num_resources, {resource_b: amt_b}), rng.randint(*params.duration_range)),
    ]
    events_b: List[_DraftEvent] = [
        ("REQUEST", pid_b, t0, _vec(num_resources, {resource_b: amt_b}), max_duration),
        ("REQUEST", pid_b, t0 + gap, _vec(num_resources, {resource_a: amt_a}), rng.randint(*params.duration_range)),
    ]
    max_claims = {
        pid_a: {resource_a: amt_a, resource_b: amt_b},
        pid_b: {resource_a: amt_a, resource_b: amt_b},
    }
    return {pid_a: events_a, pid_b: events_b}, max_claims, t0 + gap


def _build_deadlock_triple(
    rng: random.Random,
    pids: Tuple[int, int, int],
    resources: Tuple[int, int, int],
    k: int,
    capacities: Sequence[int],
    num_resources: int,
    params: _ConditionParams,
) -> Tuple[Dict[int, List[_DraftEvent]], Dict[int, Dict[int, int]], int]:
    """A genuine 3-process cycle: p0 holds A and wants B (held by p1), p1
    holds B and wants C (held by p2), p2 holds C and wants A (held by p0).
    Each of the 3 resources has exactly one holder and one wanter, so the
    same bilateral-overflow sizing (holder amount == wanter amount, both
    > capacity/2) guarantees each link of the chain is genuinely
    unsatisfiable, without needing every pair to jointly overflow."""
    p0, p1, p2 = pids
    a, b, c = resources
    amt_a = _bilateral_overflow_amount(capacities[a], params.pair_intensity, params.cap_fraction)
    amt_b = _bilateral_overflow_amount(capacities[b], params.pair_intensity, params.cap_fraction)
    amt_c = _bilateral_overflow_amount(capacities[c], params.pair_intensity, params.cap_fraction)
    max_duration = params.duration_range[1]
    gap = 1
    t0 = 10 * k + 1

    events = {
        p0: [
            ("REQUEST", p0, t0, _vec(num_resources, {a: amt_a}), max_duration),
            ("REQUEST", p0, t0 + gap, _vec(num_resources, {b: amt_b}), rng.randint(*params.duration_range)),
        ],
        p1: [
            ("REQUEST", p1, t0, _vec(num_resources, {b: amt_b}), max_duration),
            ("REQUEST", p1, t0 + gap, _vec(num_resources, {c: amt_c}), rng.randint(*params.duration_range)),
        ],
        p2: [
            ("REQUEST", p2, t0, _vec(num_resources, {c: amt_c}), max_duration),
            ("REQUEST", p2, t0 + gap, _vec(num_resources, {a: amt_a}), rng.randint(*params.duration_range)),
        ],
    }
    max_claims = {
        p0: {a: amt_a, b: amt_b},
        p1: {b: amt_b, c: amt_c},
        p2: {c: amt_c, a: amt_a},
    }
    return events, max_claims, t0 + gap


def _generate(condition: Condition, seed: int, config: SimulationConfig) -> Workload:
    rng = random.Random(f"{condition.value}:{seed}")
    params = _params_for(condition, config)
    plan = _plan_for(condition)
    n = config.num_processes
    capacities = config.capacities
    num_resources = config.num_resources

    total_work = {pid: rng.randint(*_TOTAL_WORK_RANGE) for pid in range(n)}

    draft_by_pid: Dict[int, List[_DraftEvent]] = {pid: [] for pid in range(n)}
    max_claim_by_pid: Dict[int, Dict[int, int]] = {pid: {} for pid in range(n)}

    def _pad(pid: int, core_count: int, exclude: Sequence[int], anchor_ts: int) -> None:
        events, claim = _pad_to_request_count(
            rng, pid, core_count, exclude, capacities, num_resources, params,
            start_time=anchor_ts + rng.randint(12, 20),
        )
        draft_by_pid[pid].extend(events)
        for r, amount in claim.items():
            max_claim_by_pid[pid][r] = max_claim_by_pid[pid].get(r, 0) + amount

    # --- Banker-trap groups ---
    # Feasible resources differ by condition (small caps need more slack per
    # process, hence more processes than a given group provides -- see
    # _build_banker_trap_group's feasibility check).
    used_banker_resources: List[int] = []
    for group in plan.banker_groups:
        candidates = [r for r in range(num_resources) if r not in used_banker_resources]
        rng.shuffle(candidates)
        built = None
        chosen_resource = None
        for resource in candidates:
            result = _build_banker_trap_group(rng, group, resource, capacities, num_resources, params, t0=rng.randint(2, 15))
            if result is not None:
                built = result
                chosen_resource = resource
                break
        if built is None:
            continue  # no feasible resource for this group size/cap -- skip gracefully
        used_banker_resources.append(chosen_resource)
        events_by_pid, claim_by_pid, anchor_ts = built
        for pid in group:
            draft_by_pid[pid].extend(events_by_pid[pid])
            for r, amount in claim_by_pid[pid].items():
                max_claim_by_pid[pid][r] = max_claim_by_pid[pid].get(r, 0) + amount
            core_count = 1 if len(events_by_pid[pid]) else 0
            _pad(pid, core_count, exclude=(chosen_resource,), anchor_ts=anchor_ts)

    # --- Deadlock cycles (pairs) ---
    used_cycle_resource_sets: List[frozenset] = []
    for k, (pid_a, pid_b) in enumerate(plan.deadlock_pairs):
        candidates = [pair for pair in _ALL_PAIRS if frozenset(pair) not in used_cycle_resource_sets]
        resource_a, resource_b = candidates[rng.randrange(len(candidates))] if candidates else rng.choice(_ALL_PAIRS)
        used_cycle_resource_sets.append(frozenset((resource_a, resource_b)))
        events_by_pid, claim_by_pid, anchor_ts = _build_deadlock_pair(
            rng, pid_a, pid_b, resource_a, resource_b, k, capacities, num_resources, params
        )
        for pid in (pid_a, pid_b):
            draft_by_pid[pid].extend(events_by_pid[pid])
            for r, amount in claim_by_pid[pid].items():
                max_claim_by_pid[pid][r] = max_claim_by_pid[pid].get(r, 0) + amount
            _pad(pid, core_count=2, exclude=(resource_a, resource_b), anchor_ts=anchor_ts)

    # --- Deadlock cycles (triples) ---
    for k, triple_pids in enumerate(plan.deadlock_triples, start=len(plan.deadlock_pairs)):
        candidates = [t for t in _ALL_TRIPLES if frozenset(t) not in used_cycle_resource_sets]
        resources = candidates[rng.randrange(len(candidates))] if candidates else rng.choice(_ALL_TRIPLES)
        used_cycle_resource_sets.append(frozenset(resources))
        events_by_pid, claim_by_pid, anchor_ts = _build_deadlock_triple(
            rng, triple_pids, resources, k, capacities, num_resources, params
        )
        for pid in triple_pids:
            draft_by_pid[pid].extend(events_by_pid[pid])
            for r, amount in claim_by_pid[pid].items():
                max_claim_by_pid[pid][r] = max_claim_by_pid[pid].get(r, 0) + amount
            _pad(pid, core_count=2, exclude=resources, anchor_ts=anchor_ts)

    # --- Ordering-violation processes ---
    for pid in plan.ordering_violation:
        t0 = rng.randint(2, 15)
        events, claim, anchor_ts = _build_ordering_violation(rng, pid, capacities, num_resources, params, t0)
        draft_by_pid[pid].extend(events)
        for r, amount in claim.items():
            max_claim_by_pid[pid][r] = max_claim_by_pid[pid].get(r, 0) + amount
        exclude = tuple(claim.keys())
        _pad(pid, core_count=2, exclude=exclude, anchor_ts=anchor_ts)

    # --- Pure background processes ---
    for pid in plan.background:
        num_requests = rng.randint(*params.num_requests_range)
        start_time = rng.randint(2, max(3, int(params.max_ticks * 0.15)))
        events, claim, _ = _build_incremental_requests(
            rng, pid, list(range(num_resources)), capacities, num_resources,
            num_requests, params.ordinary_intensity, params.duration_range, start_time=start_time,
        )
        draft_by_pid[pid].extend(events)
        for r, amount in claim.items():
            max_claim_by_pid[pid][r] = max_claim_by_pid[pid].get(r, 0) + amount

    # Global deterministic sequence-number assignment: sort every draft event
    # across the whole workload by (timestamp, pid), then number them 0..N-1.
    flat: List[Tuple[int, int, _DraftEvent]] = []
    for pid, events in draft_by_pid.items():
        for ev in events:
            flat.append((ev[2], pid, ev))
    flat.sort(key=lambda item: (item[0], item[1]))

    events_by_pid: Dict[int, List[WorkloadEvent]] = {pid: [] for pid in range(n)}
    for seq, (_ts, pid, ev) in enumerate(flat):
        if ev[0] == "REQUEST":
            _, _pid, timestamp, request, duration = ev
            events_by_pid[pid].append(
                RequestEvent(
                    pid=pid, timestamp=timestamp, sequence_number=seq, request=request, duration=duration
                )
            )
        else:
            _, _pid, timestamp = ev
            events_by_pid[pid].append(ReleaseEvent(pid=pid, timestamp=timestamp, sequence_number=seq))

    processes = []
    for pid in range(n):
        claim_vec = tuple(max_claim_by_pid[pid].get(r, 0) for r in range(num_resources))
        events_sorted = tuple(sorted(events_by_pid[pid], key=lambda e: e.timestamp))
        processes.append(
            ProcessWorkload(pid=pid, total_work=total_work[pid], max_claim=claim_vec, events=events_sorted)
        )

    return Workload(
        condition=condition,
        seed=seed,
        processes=tuple(processes),
        next_sequence_number=len(flat),
    )
