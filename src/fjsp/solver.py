"""GRASP solver for the extended FJSP.

Two phases per iteration (Resende & Ribeiro 2016, ch. 5):
  1) Greedy randomized construction with a Restricted Candidate List.
  2) Local search to a local optimum.

Convention used in the RCL (minimization, Resende & Ribeiro p. 60):

    RCL = { c in F : g(c) <= g_min + alpha * (g_max - g_min) }

so alpha = 0 is pure greedy, alpha = 1 is uniformly random.

Real-shop extensions handled here:
  * Machine availability windows (planned downtime).
  * Operator shifts.
  * Operator-machine eligibility.
  * Product-dependent setup times per machine (sparse — empty matrix
    means the machine never needs setup).
  * Per-stage `OrderStatus`: completed and running stages are NOT
    rescheduled. Running stages pin their (machine, operator) until
    their expected end. Completed stages contribute their product to
    the relevant machine's `machine_last_product` so that the first
    newly-scheduled op pays the correct setup.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from .input.domain import Instance, StageState


# -------------------------- solver-internal types -------------------------

@dataclass
class OperationView:
    """Denormalized (job, stage) view used inside the solver and schedules."""
    job_id: int
    op_idx: int
    product_id: int
    machine_options: dict[int, int]

    def __repr__(self) -> str:
        return f"O({self.job_id},{self.op_idx})[P{self.product_id}]"


@dataclass
class ScheduledOp:
    op: OperationView
    machine: int
    operator: int
    start: int             # start of the (setup + processing) block
    setup_duration: int
    end: int               # = start + setup_duration + processing_time
    state: str = StageState.PENDING

    @property
    def proc_start(self) -> int:
        return self.start + self.setup_duration


@dataclass
class Schedule:
    """The solver's output: contains only the ops the solver decided about
    (i.e., previously-pending stages). Use `combined_ops(instance, sched)`
    to merge with completed/running stages from the OrderStatus for output
    or visualization."""
    ops: list[ScheduledOp] = field(default_factory=list)

    @property
    def makespan(self) -> int:
        return max((s.end for s in self.ops), default=0)


# ----------------------------- timing helpers -----------------------------

def _earliest_feasible_start(
    t0: int,
    duration: int,
    m_windows: tuple[tuple[int, int], ...] | list[tuple[int, int]],
    o_windows: tuple[tuple[int, int], ...] | list[tuple[int, int]],
) -> Optional[int]:
    """Smallest t >= t0 such that [t, t + duration] fits inside one window
    of the machine *and* one window of the operator simultaneously."""
    best: Optional[int] = None
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


def _eligible_operators(instance: Instance, machine_id: int) -> list[int]:
    return [op.operator_id for op in instance.operators
            if machine_id in op.eligible_machines]


# ---------------------- initial state from instance ----------------------

@dataclass
class _State:
    machine_end: list[int]
    machine_last_product: list[Optional[int]]
    operator_end: list[int]
    job_ready: list[int]
    next_op_idx: list[int]


def _initial_state(instance: Instance) -> _State:
    """Seed solver clocks from each order's per-stage `OrderStatus`.

    For every order:
      - Walk completed stages: track the most-recently-ended completed
        stage on each machine and overwrite that machine's "last product"
        with the order's product. Completed stages do NOT pin machines or
        operators — they're already done.
      - Walk running stages: pin (machine, operator) busy until
        `expected_end`, mark the machine's last product as the order's
        product, and advance the job's ready time.
      - `next_op_idx` is the smallest stage index NOT in completed
        ∪ running. (For FJSP, completed and running form a prefix.)
    """
    n_m, n_o, n_j = instance.n_machines, instance.n_operators, instance.n_jobs

    machine_end: list[int] = [0] * n_m
    machine_last_product: list[Optional[int]] = [m.current_product_id
                                                 for m in instance.machines]
    machine_last_end: list[int] = [-(10 ** 9)] * n_m
    operator_end: list[int] = [0] * n_o
    job_ready: list[int] = [0] * n_j
    next_op_idx: list[int] = [0] * n_j

    for order in instance.orders:
        product = instance.product(order.product_id)

        # Completed stages: contribute "last product" only.
        for h in order.status.completed:
            if h.end > machine_last_end[h.machine_id]:
                machine_last_end[h.machine_id] = h.end
                machine_last_product[h.machine_id] = order.product_id

        # Running stages: pin resources, advance job clock.
        for h in order.status.running:
            m, o, t_end = h.machine_id, h.operator_id, h.end
            machine_end[m] = max(machine_end[m], t_end)
            operator_end[o] = max(operator_end[o], t_end)
            if t_end > machine_last_end[m]:
                machine_last_end[m] = t_end
                machine_last_product[m] = order.product_id
            job_ready[order.job_id] = max(job_ready[order.job_id], t_end)

        # next_op_idx = first stage not in completed ∪ running.
        done = (order.status.completed_stage_indices
                | order.status.running_stage_indices)
        next_op_idx[order.job_id] = next(
            (k for k in range(product.n_stages) if k not in done),
            product.n_stages,
        )

    return _State(machine_end, machine_last_product, operator_end,
                  job_ready, next_op_idx)


# -------------------- Phase 1: semi-greedy construction ------------------

def construct(instance: Instance, alpha: float, rng: random.Random) -> Schedule:
    s = _initial_state(instance)
    sched = Schedule()

    def _has_pending() -> bool:
        return any(
            s.next_op_idx[j] < instance.product(instance.orders[j].product_id).n_stages
            for j in range(instance.n_jobs)
        )

    while _has_pending():
        candidates: list[tuple[OperationView, int, int, int, int, int]] = []
        for j in range(instance.n_jobs):
            k = s.next_op_idx[j]
            order = instance.orders[j]
            product = instance.product(order.product_id)
            if k >= product.n_stages:
                continue
            # Skip stages already in completed/running — could happen if
            # caller mutates state.
            done = (order.status.completed_stage_indices
                    | order.status.running_stage_indices)
            if k in done:
                s.next_op_idx[j] = next(
                    (kk for kk in range(k + 1, product.n_stages) if kk not in done),
                    product.n_stages,
                )
                continue
            stage = product.stages[k]
            op = OperationView(
                job_id=j, op_idx=k,
                product_id=product.product_id,
                machine_options=dict(stage.eligible_machines),
            )
            for m, p in stage.eligible_machines.items():
                machine = instance.machines[m]
                setup = machine.setup(s.machine_last_product[m], product.product_id)
                block = setup + p
                for o in _eligible_operators(instance, m):
                    t0 = max(s.machine_end[m], s.operator_end[o], s.job_ready[j])
                    start = _earliest_feasible_start(
                        t0, block, machine.availability,
                        instance.operators[o].shifts,
                    )
                    if start is None:
                        continue
                    end = start + block
                    candidates.append((op, m, o, start, setup, end))

        if not candidates:
            raise RuntimeError(
                "infeasible: no (op, machine, operator) fits the available "
                "windows. Check machine / operator availability and "
                "operator-machine eligibility."
            )

        g_min = min(c[5] for c in candidates)
        g_max = max(c[5] for c in candidates)
        threshold = g_min + alpha * (g_max - g_min)
        rcl = [c for c in candidates if c[5] <= threshold]

        op, m, o, start, setup, end = rng.choice(rcl)
        sched.ops.append(ScheduledOp(op, m, o, start, setup, end,
                                     state=StageState.PENDING))
        s.machine_end[m] = end
        s.machine_last_product[m] = op.product_id
        s.operator_end[o] = end
        s.job_ready[op.job_id] = end
        # Advance to the next pending stage of this job.
        order = instance.orders[op.job_id]
        product = instance.product(order.product_id)
        done = (order.status.completed_stage_indices
                | order.status.running_stage_indices)
        s.next_op_idx[op.job_id] = next(
            (k for k in range(op.op_idx + 1, product.n_stages) if k not in done),
            product.n_stages,
        )

    return sched


# -------------------------- replay a solution ----------------------------

def simulate(
    instance: Instance,
    sequence: list[tuple[int, int]],
    machine_assign: dict[tuple[int, int], int],
    operator_assign: dict[tuple[int, int], int],
) -> Optional[Schedule]:
    s = _initial_state(instance)
    sched = Schedule()
    for (j, k) in sequence:
        order = instance.orders[j]
        product = instance.product(order.product_id)
        stage = product.stages[k]
        m = machine_assign[(j, k)]
        o = operator_assign[(j, k)]
        p = stage.eligible_machines[m]
        machine = instance.machines[m]
        setup = machine.setup(s.machine_last_product[m], product.product_id)
        block = setup + p

        t0 = max(s.machine_end[m], s.operator_end[o], s.job_ready[j])
        start = _earliest_feasible_start(
            t0, block, machine.availability,
            instance.operators[o].shifts,
        )
        if start is None:
            return None
        end = start + block

        op = OperationView(
            job_id=j, op_idx=k,
            product_id=product.product_id,
            machine_options=dict(stage.eligible_machines),
        )
        sched.ops.append(ScheduledOp(op, m, o, start, setup, end,
                                     state=StageState.PENDING))
        s.machine_end[m] = end
        s.machine_last_product[m] = product.product_id
        s.operator_end[o] = end
        s.job_ready[j] = end
    return sched


# ------------------------- Phase 2: local search -------------------------

def local_search(instance: Instance, sched: Schedule) -> Schedule:
    sequence = [(s.op.job_id, s.op.op_idx) for s in sched.ops]
    machine_assign = {(s.op.job_id, s.op.op_idx): s.machine for s in sched.ops}
    operator_assign = {(s.op.job_id, s.op.op_idx): s.operator for s in sched.ops}
    best = sched

    improved = True
    while improved:
        improved = False

        # N_M: machine reassignment.
        for (j, k), m_curr in list(machine_assign.items()):
            stage = instance.product(instance.orders[j].product_id).stages[k]
            for m_alt in stage.eligible_machines:
                if m_alt == m_curr:
                    continue
                trial_m = {**machine_assign, (j, k): m_alt}
                op_curr = operator_assign[(j, k)]
                if m_alt not in instance.operators[op_curr].eligible_machines:
                    valid_ops = _eligible_operators(instance, m_alt)
                    if not valid_ops:
                        continue
                    trial_o = {**operator_assign, (j, k): valid_ops[0]}
                else:
                    trial_o = operator_assign
                trial = simulate(instance, sequence, trial_m, trial_o)
                if trial is not None and trial.makespan < best.makespan:
                    best = trial
                    machine_assign = trial_m
                    operator_assign = trial_o
                    improved = True
                    break
            if improved:
                break
        if improved:
            continue

        # N_O: operator reassignment.
        for (j, k), o_curr in list(operator_assign.items()):
            m = machine_assign[(j, k)]
            for o_alt in _eligible_operators(instance, m):
                if o_alt == o_curr:
                    continue
                trial_o = {**operator_assign, (j, k): o_alt}
                trial = simulate(instance, sequence, machine_assign, trial_o)
                if trial is not None and trial.makespan < best.makespan:
                    best = trial
                    operator_assign = trial_o
                    improved = True
                    break
            if improved:
                break

    return best


# ---------------------------- top-level GRASP ----------------------------

def grasp(
    instance: Instance,
    max_iter: int = 100,
    alpha: float = 0.3,
    seed: Optional[int] = None,
) -> Schedule:
    rng = random.Random(seed)
    best: Optional[Schedule] = None
    for _ in range(max_iter):
        sol = construct(instance, alpha, rng)
        sol = local_search(instance, sol)
        if best is None or sol.makespan < best.makespan:
            best = sol
    assert best is not None
    return best


# ----------------------- combined viz/output helper ----------------------

def combined_ops(instance: Instance, sched: Schedule) -> list[ScheduledOp]:
    """Merge OrderStatus history (completed + running) with the solver's
    pending ops into a single list, each tagged with `.state`. This is
    the canonical view for visualization and export."""
    out: list[ScheduledOp] = []
    for order in instance.orders:
        product = instance.product(order.product_id)
        for h in order.status.completed:
            stage = product.stages[h.stage_idx]
            out.append(ScheduledOp(
                op=OperationView(order.job_id, h.stage_idx,
                                 order.product_id, dict(stage.eligible_machines)),
                machine=h.machine_id, operator=h.operator_id,
                start=h.start, setup_duration=h.setup_duration, end=h.end,
                state=StageState.COMPLETED,
            ))
        for h in order.status.running:
            stage = product.stages[h.stage_idx]
            out.append(ScheduledOp(
                op=OperationView(order.job_id, h.stage_idx,
                                 order.product_id, dict(stage.eligible_machines)),
                machine=h.machine_id, operator=h.operator_id,
                start=h.start, setup_duration=h.setup_duration, end=h.end,
                state=StageState.RUNNING,
            ))
    out.extend(sched.ops)
    return out


def total_makespan(instance: Instance, sched: Schedule) -> int:
    """`Cmax` across ALL ops (completed, running, and pending)."""
    return max((op.end for op in combined_ops(instance, sched)), default=0)
