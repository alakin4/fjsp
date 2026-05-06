"""GRASP solver for FJSP with availability windows and setup times.

Two phases per iteration (Resende & Ribeiro 2016, ch. 5):
  1) Greedy randomized construction with a Restricted Candidate List (RCL).
  2) Local search to a local optimum.

Convention used in the RCL (minimization, Resende & Ribeiro eq. on p. 60):

    RCL = { c in F : g(c) <= g_min + alpha * (g_max - g_min) }

so alpha = 0 is pure greedy, alpha = 1 is uniformly random.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .data import FJSPInstance, Operation


# ----------------------------- schedule types -----------------------------

@dataclass
class ScheduledOp:
    op: Operation
    machine: int
    operator: int
    start: int            # beginning of the (setup + processing) block
    setup_duration: int   # may be 0
    end: int              # = start + setup_duration + processing_time

    @property
    def proc_start(self) -> int:
        return self.start + self.setup_duration


@dataclass
class Schedule:
    ops: list[ScheduledOp] = field(default_factory=list)

    @property
    def makespan(self) -> int:
        return max((s.end for s in self.ops), default=0)


# ----------------------------- timing helper ------------------------------

def _earliest_feasible_start(
    t0: int,
    duration: int,
    m_windows: list[tuple[int, int]],
    o_windows: list[tuple[int, int]],
) -> int | None:
    """Smallest t >= t0 such that [t, t + duration] fits inside one window
    of the machine *and* one window of the operator simultaneously."""
    best: int | None = None
    for ma, mb in m_windows:
        if mb - ma < duration or mb <= t0:
            continue
        for oa, ob in o_windows:
            if ob - oa < duration or ob <= t0:
                continue
            lo = max(ma, oa, t0)
            hi = min(mb, ob)
            if hi - lo >= duration and (best is None or lo < best):
                best = lo
    return best


# ----------------------- Phase 1: semi-greedy construction ----------------

def construct(instance: FJSPInstance, alpha: float, rng: random.Random) -> Schedule:
    machine_end = [0] * instance.n_machines
    machine_last_product: list[int | None] = [None] * instance.n_machines
    operator_end = [0] * instance.n_operators
    job_ready = [0] * instance.n_jobs
    next_op = [0] * instance.n_jobs
    sched = Schedule()

    while any(idx < len(instance.jobs[j]) for j, idx in enumerate(next_op)):
        candidates: list[tuple[Operation, int, int, int, int, int]] = []
        # tuple = (op, machine, operator, start, setup, end)
        for j in range(instance.n_jobs):
            k = next_op[j]
            if k >= len(instance.jobs[j]):
                continue
            op = instance.jobs[j][k]
            for m, p in op.machine_options.items():
                setup = instance.setup(m, machine_last_product[m], op.product_id)
                block = setup + p
                for o in op.operator_options:
                    t0 = max(machine_end[m], operator_end[o], job_ready[j])
                    start = _earliest_feasible_start(
                        t0, block,
                        instance.machine_windows[m],
                        instance.operator_windows[o],
                    )
                    if start is None:
                        continue
                    end = start + block
                    candidates.append((op, m, o, start, setup, end))

        if not candidates:
            raise RuntimeError("infeasible: no (op, machine, operator) fits any window")

        g_min = min(c[5] for c in candidates)
        g_max = max(c[5] for c in candidates)
        threshold = g_min + alpha * (g_max - g_min)
        rcl = [c for c in candidates if c[5] <= threshold]

        op, m, o, start, setup, end = rng.choice(rcl)
        sched.ops.append(ScheduledOp(op, m, o, start, setup, end))
        machine_end[m] = end
        machine_last_product[m] = op.product_id
        operator_end[o] = end
        job_ready[op.job_id] = end
        next_op[op.job_id] += 1

    return sched


# --------------------------- replay a solution ---------------------------

def simulate(
    instance: FJSPInstance,
    sequence: list[tuple[int, int]],
    machine_assign: dict[tuple[int, int], int],
    operator_assign: dict[tuple[int, int], int],
) -> Schedule | None:
    """Recompute a schedule from a fixed operation order + assignments.
    Returns None if no time slot satisfies all windows for some op."""
    machine_end = [0] * instance.n_machines
    machine_last_product: list[int | None] = [None] * instance.n_machines
    operator_end = [0] * instance.n_operators
    job_ready = [0] * instance.n_jobs
    sched = Schedule()
    for (j, k) in sequence:
        op = instance.jobs[j][k]
        m = machine_assign[(j, k)]
        o = operator_assign[(j, k)]
        p = op.machine_options[m]
        setup = instance.setup(m, machine_last_product[m], op.product_id)
        block = setup + p
        t0 = max(machine_end[m], operator_end[o], job_ready[j])
        start = _earliest_feasible_start(
            t0, block,
            instance.machine_windows[m],
            instance.operator_windows[o],
        )
        if start is None:
            return None
        end = start + block
        sched.ops.append(ScheduledOp(op, m, o, start, setup, end))
        machine_end[m] = end
        machine_last_product[m] = op.product_id
        operator_end[o] = end
        job_ready[op.job_id] = end
    return sched


# --------------------------- Phase 2: local search ------------------------

def local_search(instance: FJSPInstance, sched: Schedule) -> Schedule:
    """First-improvement on two neighborhoods, applied until no improvement:
        N_M: change one operation's machine
        N_O: change one operation's operator
    """
    sequence = [(s.op.job_id, s.op.op_idx) for s in sched.ops]
    machine_assign = {(s.op.job_id, s.op.op_idx): s.machine for s in sched.ops}
    operator_assign = {(s.op.job_id, s.op.op_idx): s.operator for s in sched.ops}
    best = sched

    improved = True
    while improved:
        improved = False
        for (j, k), m_curr in list(machine_assign.items()):
            for m_alt in instance.jobs[j][k].machine_options:
                if m_alt == m_curr:
                    continue
                trial = simulate(
                    instance, sequence,
                    {**machine_assign, (j, k): m_alt},
                    operator_assign,
                )
                if trial is not None and trial.makespan < best.makespan:
                    best = trial
                    machine_assign[(j, k)] = m_alt
                    improved = True
                    break
            if improved:
                break
        if improved:
            continue
        for (j, k), o_curr in list(operator_assign.items()):
            for o_alt in instance.jobs[j][k].operator_options:
                if o_alt == o_curr:
                    continue
                trial = simulate(
                    instance, sequence,
                    machine_assign,
                    {**operator_assign, (j, k): o_alt},
                )
                if trial is not None and trial.makespan < best.makespan:
                    best = trial
                    operator_assign[(j, k)] = o_alt
                    improved = True
                    break
            if improved:
                break
    return best


# ----------------------------- top-level GRASP ----------------------------

def grasp(
    instance: FJSPInstance,
    max_iter: int = 100,
    alpha: float = 0.3,
    seed: int | None = None,
) -> Schedule:
    rng = random.Random(seed)
    best: Schedule | None = None
    for _ in range(max_iter):
        sol = construct(instance, alpha, rng)
        sol = local_search(instance, sol)
        if best is None or sol.makespan < best.makespan:
            best = sol
    assert best is not None
    return best
