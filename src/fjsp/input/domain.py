"""Domain types for the FJSP instance.

Modeled as a relational schema, mirroring the database tables a real
shop floor would expose:

    products(id, name)
    stages(product_id, stage_idx, name)              -- via Product.stages
    stage_machines(product_id, stage_idx, machine_id, processing_time)
                                                     -- via Stage.eligible_machines
    machines(id, name, current_product_id)
    machine_availability(machine_id, start, end)     -- via Machine.availability
    machine_setup(machine_id, prev_product, curr_product, duration)
                                                     -- via Machine.setup_times
    operators(id, name)
    operator_machines(operator_id, machine_id)       -- via Operator.eligible_machines
    operator_shifts(operator_id, start, end)         -- via Operator.shifts
    orders(job_id, product_id, deadline)
    order_completed_stages(job_id, stage_idx, machine_id, operator_id,
                           start, end, setup_duration)
                                                     -- via OrderStatus.completed
    order_running_stages(job_id, stage_idx, machine_id, operator_id,
                         start, end, setup_duration)
                                                     -- via OrderStatus.running

Order state is *per stage*, not per order.  Each stage of a job is in
exactly one of three buckets:

    completed   already finished — has actual times in the past.
    running     mid-flight — actual start in the past, expected end in
                the future. The solver pins its (machine, operator)
                until that expected end.
    pending     not yet started — the solver will schedule it. Pending
                is the *complement* of completed ∪ running, so it is
                derived, not stored.
"""

from dataclasses import dataclass, field
from typing import Optional

HORIZON = 10_000


# --------------------------- product / stages ----------------------------

@dataclass(frozen=True)
class Stage:
    """One step in a product's production mode."""
    stage_idx: int
    name: str
    eligible_machines: dict[int, int]   # machine_id -> processing time


@dataclass(frozen=True)
class Product:
    """A product type with an ordered sequence of stages."""
    product_id: int
    name: str
    stages: tuple[Stage, ...]

    @property
    def n_stages(self) -> int:
        return len(self.stages)


# ------------------------------- machines --------------------------------

@dataclass(frozen=True)
class Machine:
    """A machine with availability windows and a (possibly empty) setup matrix.

    `current_product_id` records the product most recently processed on this
    machine if there is no order-level history that overrides it. The seed in
    the solver is::

        machine_last_product[m] = m.current_product_id
        # then, for each completed/running stage on m (in time order):
        #     machine_last_product[m] = order.product_id of that stage
    """
    machine_id: int
    name: str
    availability: tuple[tuple[int, int], ...]   # closed intervals [a, b]
    setup_times: dict[int, dict[int, int]] = field(default_factory=dict)
    current_product_id: Optional[int] = None

    def setup(self, prev_product: Optional[int], curr_product: int) -> int:
        if not self.setup_times:
            return 0
        key = -1 if prev_product is None else prev_product
        return self.setup_times.get(key, {}).get(curr_product, 0)


# ------------------------------ operators --------------------------------

@dataclass(frozen=True)
class Operator:
    """A worker who can run a subset of machines, with shift-based availability."""
    operator_id: int
    name: str
    eligible_machines: frozenset[int]
    shifts: tuple[tuple[int, int], ...]


# ------------------------ stage-level history -----------------------------

class StageState:
    """String constants for op state in the combined view."""
    COMPLETED = "completed"
    RUNNING = "running"
    PENDING = "pending"


@dataclass(frozen=True)
class StageHistory:
    """An already-known instance of one stage of one order.

    Used for both completed stages (where `end` is the actual finish time)
    and running stages (where `end` is the expected finish time). The
    convention is that the solver clock has t = 0 at the moment scheduling
    starts; completed stages typically have `end <= 0` and running stages
    typically have `start <= 0 <= end`.
    """
    stage_idx: int
    machine_id: int
    operator_id: int
    start: int
    end: int
    setup_duration: int = 0


# ------------------------------- orders ----------------------------------

@dataclass
class OrderStatus:
    """Real-time status snapshot of an order, organized per-stage.

    `completed` holds StageHistory records for stages that are already done.
    `running` holds StageHistory records for stages currently in progress.
    Pending stages are everything else; they are derived, not stored.
    """
    completed: list[StageHistory] = field(default_factory=list)
    running: list[StageHistory] = field(default_factory=list)

    @property
    def completed_stage_indices(self) -> set[int]:
        return {h.stage_idx for h in self.completed}

    @property
    def running_stage_indices(self) -> set[int]:
        return {h.stage_idx for h in self.running}


@dataclass
class Order:
    """A customer order = a job to be scheduled."""
    job_id: int
    product_id: int
    deadline: int
    status: OrderStatus = field(default_factory=OrderStatus)

    def pending_stage_indices(self, n_stages: int) -> set[int]:
        return (set(range(n_stages))
                - self.status.completed_stage_indices
                - self.status.running_stage_indices)


# ------------------------------ instance ---------------------------------

class StageMode:
    """How machines are distributed across stages."""
    PER_STAGE = "per_stage"   # each machine belongs to exactly one stage
    SHARED = "shared"         # a machine may serve multiple stages


@dataclass
class Instance:
    name: str
    horizon: int
    products: list[Product]
    machines: list[Machine]
    operators: list[Operator]
    orders: list[Order]
    # Shop-level stage layout. `stage_machines[stage_idx]` lists the
    # machines eligible for that stage. Each product's
    # `Stage.eligible_machines` for index `k` must be a subset of
    # `stage_machines[k]`.  None ⇒ no shop-level partition.
    stage_machines: Optional[list[list[int]]] = None
    machine_stage_mode: str = StageMode.SHARED

    @property
    def n_products(self) -> int:
        return len(self.products)

    @property
    def n_machines(self) -> int:
        return len(self.machines)

    @property
    def n_operators(self) -> int:
        return len(self.operators)

    @property
    def n_jobs(self) -> int:
        return len(self.orders)

    def product(self, product_id: int) -> Product:
        return self.products[product_id]

    def machine(self, machine_id: int) -> Machine:
        return self.machines[machine_id]

    def operator(self, operator_id: int) -> Operator:
        return self.operators[operator_id]

    @property
    def machine_windows(self) -> list[list[tuple[int, int]]]:
        return [list(m.availability) for m in self.machines]

    @property
    def operator_windows(self) -> list[list[tuple[int, int]]]:
        return [list(o.shifts) for o in self.operators]

    def stage_of_machine(self, machine_id: int) -> Optional[int]:
        """In `per_stage` mode, the unique stage this machine belongs to.
        In `shared` mode, returns the lowest stage that lists it (or None)."""
        if self.stage_machines is None:
            return None
        for s, machines in enumerate(self.stage_machines):
            if machine_id in machines:
                return s
        return None
