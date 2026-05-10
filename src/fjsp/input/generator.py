"""Builders for FJSP instances.

`toy_instance()` returns the fixed 2-job/2-machine instance used in the
README examples. `random_instance(...)` produces parametric synthetic
instances for benchmarking and testing.
"""

import random
from dataclasses import replace

from .domain import (
    HORIZON,
    Instance,
    Machine,
    Operator,
    Order,
    Product,
    Stage,
)


# ------------------------------- toy --------------------------------------

def toy_instance() -> Instance:
    """Canonical 2-job, 2-machine, 2-operator, 2-product instance."""
    products = [
        Product(0, "P0", (
            Stage(0, "stage-0", {0: 3, 1: 2}),
            Stage(1, "stage-1", {0: 2, 1: 4}),
        )),
        Product(1, "P1", (
            Stage(0, "stage-0", {0: 4, 1: 3}),
            Stage(1, "stage-1", {0: 3, 1: 5}),
        )),
    ]
    base_setup = {
        -1: {0: 0, 1: 0},          # initial setup is free
        0:  {0: 0, 1: 1},          # P0 -> P0 / P0 -> P1
        1:  {0: 2, 1: 0},          # P1 -> P0 / P1 -> P1
    }
    machines = [
        Machine(0, "M0", ((0, HORIZON),), setup_times=base_setup),
        # M1 is unavailable [3, 5)
        Machine(1, "M1", ((0, 3), (5, HORIZON)), setup_times=base_setup),
    ]
    operators = [
        # Op0 lunch break [4, 7)
        Operator(0, "Op0", frozenset({0, 1}), ((0, 4), (7, HORIZON))),
        # Op1 lunch break [5, 7)
        Operator(1, "Op1", frozenset({0, 1}), ((0, 5), (7, HORIZON))),
    ]
    orders = [
        Order(0, product_id=0, deadline=12),
        Order(1, product_id=1, deadline=12),
    ]
    return Instance(
        name="toy",
        horizon=HORIZON,
        products=products,
        machines=machines,
        operators=operators,
        orders=orders,
    )


# ---------------------------- random instance -----------------------------

def random_instance(
    name: str = "rand",
    n_products: int = 4,
    n_machines: int = 5,
    n_operators: int = 4,
    n_orders: int = 10,
    horizon: int = 200,
    stages_per_product: tuple[int, int] = (2, 4),
    proc_time: tuple[int, int] = (2, 8),
    setup_machines_fraction: float = 0.5,
    setup_time: tuple[int, int] = (1, 3),
    operator_machine_coverage: float = 0.7,
    seed: int = 0,
) -> Instance:
    """Generate a synthetic FJSP instance with reasonable defaults.

    Parameters
    ----------
    setup_machines_fraction : float in [0, 1]
        Fraction of machines that require product-dependent setup.
        The rest have an empty setup matrix (setup = 0 for any switch).
    operator_machine_coverage : float in [0, 1]
        Probability that any (operator, machine) pair is allowed.
        Coverage is repaired so every machine has at least one operator.
    """
    rng = random.Random(seed)

    # ---- products -----------------------------------------------------
    products: list[Product] = []
    for pid in range(n_products):
        n_stages = rng.randint(*stages_per_product)
        stages = []
        for sidx in range(n_stages):
            n_eligible = rng.randint(1, max(1, n_machines // 2 + 1))
            chosen = rng.sample(range(n_machines), min(n_eligible, n_machines))
            elig = {m: rng.randint(*proc_time) for m in chosen}
            stages.append(Stage(sidx, f"stage-{sidx}", elig))
        products.append(Product(pid, f"P{pid}", tuple(stages)))

    # ---- machines -----------------------------------------------------
    machines: list[Machine] = []
    setup_machine_ids = set(rng.sample(
        range(n_machines), int(round(n_machines * setup_machines_fraction))
    ))
    for mid in range(n_machines):
        # Build a list of available windows by alternating uptime/downtime.
        windows: list[tuple[int, int]] = []
        t = 0
        while t < horizon:
            up_len = rng.randint(20, 50)
            end = min(horizon, t + up_len)
            if end > t:
                windows.append((t, end))
            t = end + rng.randint(2, 8)  # downtime
        if not windows:
            windows.append((0, horizon))

        if mid in setup_machine_ids:
            setup = {-1: {p: 0 for p in range(n_products)}}
            for p1 in range(n_products):
                setup[p1] = {
                    p2: 0 if p1 == p2 else rng.randint(*setup_time)
                    for p2 in range(n_products)
                }
        else:
            setup = {}

        machines.append(Machine(
            machine_id=mid,
            name=f"M{mid}",
            availability=tuple(windows),
            setup_times=setup,
            current_product_id=None,
        ))

    # ---- operators ----------------------------------------------------
    operators: list[Operator] = []
    for oid in range(n_operators):
        elig = {m for m in range(n_machines) if rng.random() < operator_machine_coverage}
        if not elig:                      # ensure at least one machine
            elig = {rng.randrange(n_machines)}

        # Shifts: alternating work/break
        shifts: list[tuple[int, int]] = []
        t = 0
        while t < horizon:
            shift_len = rng.randint(25, 60)
            end = min(horizon, t + shift_len)
            if end > t:
                shifts.append((t, end))
            t = end + rng.randint(8, 16)  # break
        if not shifts:
            shifts.append((0, horizon))
        operators.append(Operator(
            operator_id=oid,
            name=f"Op{oid}",
            eligible_machines=frozenset(elig),
            shifts=tuple(shifts),
        ))

    # Repair: every machine must have at least one operator who can run it.
    for mid in range(n_machines):
        if not any(mid in op.eligible_machines for op in operators):
            i = rng.randrange(n_operators)
            old = operators[i]
            operators[i] = replace(old, eligible_machines=frozenset(old.eligible_machines | {mid}))

    # ---- orders -------------------------------------------------------
    orders: list[Order] = []
    for jid in range(n_orders):
        pid = rng.randrange(n_products)
        product = products[pid]
        # Estimate "average" total processing time across all stages,
        # taking the per-stage average over its eligible machines.
        avg_total = sum(
            sum(s.eligible_machines.values()) / len(s.eligible_machines)
            for s in product.stages
        )
        deadline = int(avg_total * rng.uniform(1.5, 3.0)) + jid * 4
        orders.append(Order(job_id=jid, product_id=pid, deadline=deadline))

    return Instance(
        name=name,
        horizon=horizon,
        products=products,
        machines=machines,
        operators=operators,
        orders=orders,
    )
