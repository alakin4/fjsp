"""Builders for FJSP instances.

`toy_instance()` returns a fixed 2-product, 4-machine, 2-stage instance
that demonstrates per-stage machine partitioning. `random_instance(...)`
produces parametric synthetic instances driven by a `ProblemConfig`.
"""

import random
from dataclasses import replace

from .config import ProblemConfig
from .domain import (
    HORIZON,
    Instance,
    Machine,
    Operator,
    Order,
    Product,
    Stage,
    StageMode,
)


# ------------------------------- toy --------------------------------------

def toy_instance() -> Instance:
    """Canonical toy: 2 products, 4 machines split 2-per-stage across 2 stages.

    Layout (per_stage mode):
        stage 0 → M0, M1
        stage 1 → M2, M3
    """
    base_setup = {
        -1: {0: 0, 1: 0},      # initial setup is free
        0:  {0: 0, 1: 1},      # P0 → P0 / P0 → P1
        1:  {0: 2, 1: 0},      # P1 → P0 / P1 → P1
    }
    products = [
        Product(0, "P0", (
            Stage(0, "stage-0", {0: 3, 1: 2}),
            Stage(1, "stage-1", {2: 2, 3: 4}),
        )),
        Product(1, "P1", (
            Stage(0, "stage-0", {0: 4, 1: 3}),
            Stage(1, "stage-1", {2: 3, 3: 5}),
        )),
    ]
    machines = [
        Machine(0, "M0", ((0, HORIZON),), setup_times=base_setup),
        # M1 is unavailable [3, 5) — maintenance during stage-0 work.
        Machine(1, "M1", ((0, 3), (5, HORIZON)), setup_times=base_setup),
        Machine(2, "M2", ((0, HORIZON),), setup_times=base_setup),
        # M3 has a brief maintenance gap [4, 6).
        Machine(3, "M3", ((0, 4), (6, HORIZON)), setup_times=base_setup),
    ]
    operators = [
        # Op0 lunch break [4, 7).
        Operator(0, "Op0", frozenset({0, 1, 2, 3}), ((0, 4), (7, HORIZON))),
        # Op1 lunch break [5, 7).
        Operator(1, "Op1", frozenset({0, 1, 2, 3}), ((0, 5), (7, HORIZON))),
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
        stage_machines=[[0, 1], [2, 3]],
        machine_stage_mode=StageMode.PER_STAGE,
    )


# ---------------------------- random instance -----------------------------

def _resolve_stage_machines(cfg: ProblemConfig, rng: random.Random) -> list[list[int]]:
    """Return the per-stage machine lists, either from the explicit config
    or auto-generated according to `machine_stage_mode`."""
    if cfg.stage_machines is not None:
        return [list(s) for s in cfg.stage_machines]

    if cfg.machine_stage_mode == StageMode.PER_STAGE:
        # Partition n_machines evenly across n_stages.
        if cfg.n_machines < cfg.n_stages:
            raise ValueError(
                f"per_stage with n_stages={cfg.n_stages} needs at least "
                f"{cfg.n_stages} machines (got {cfg.n_machines})"
            )
        result = [[] for _ in range(cfg.n_stages)]
        for m in range(cfg.n_machines):
            result[m % cfg.n_stages].append(m)
        return result

    # shared: each machine independently joins each stage.
    result = [[] for _ in range(cfg.n_stages)]
    for m in range(cfg.n_machines):
        joined = False
        for s in range(cfg.n_stages):
            if rng.random() < cfg.stage_share:
                result[s].append(m)
                joined = True
        if not joined:
            result[rng.randrange(cfg.n_stages)].append(m)
    # Make sure every stage has at least one machine.
    for s in range(cfg.n_stages):
        if not result[s]:
            result[s].append(rng.randrange(cfg.n_machines))
    return result


def random_instance(
    config: ProblemConfig | None = None,
    **overrides,
) -> Instance:
    """Generate a synthetic FJSP instance.

    If `config` is None, defaults from `ProblemConfig()` are used. Any
    keyword argument matching a `ProblemConfig` field overrides that field
    (handy from the CLI or tests).
    """
    cfg = replace(config) if config is not None else ProblemConfig()
    for k, v in overrides.items():
        if v is not None:
            setattr(cfg, k, v)

    rng = random.Random(cfg.seed)
    stage_machines = _resolve_stage_machines(cfg, rng)

    # ---- products -----------------------------------------------------
    products: list[Product] = []
    for pid in range(cfg.n_products):
        stages = []
        for sidx in range(cfg.n_stages):
            allowed = stage_machines[sidx]
            if not allowed:
                raise ValueError(f"stage {sidx} has no machines")
            n_eligible = rng.randint(1, len(allowed))
            chosen = rng.sample(allowed, n_eligible)
            elig = {m: rng.randint(cfg.proc_time_min, cfg.proc_time_max)
                    for m in chosen}
            stages.append(Stage(sidx, f"stage-{sidx}", elig))
        products.append(Product(pid, f"P{pid}", tuple(stages)))

    # ---- machines -----------------------------------------------------
    setup_machine_ids = set(rng.sample(
        range(cfg.n_machines),
        int(round(cfg.n_machines * cfg.setup_machines_fraction))
    ))
    machines: list[Machine] = []
    for mid in range(cfg.n_machines):
        windows: list[tuple[int, int]] = []
        t = 0
        while t < cfg.horizon:
            up_len = rng.randint(20, 50)
            end = min(cfg.horizon, t + up_len)
            if end > t:
                windows.append((t, end))
            t = end + rng.randint(2, 8)
        if not windows:
            windows.append((0, cfg.horizon))

        if mid in setup_machine_ids:
            setup = {-1: {p: 0 for p in range(cfg.n_products)}}
            for p1 in range(cfg.n_products):
                setup[p1] = {
                    p2: 0 if p1 == p2 else rng.randint(cfg.setup_time_min,
                                                       cfg.setup_time_max)
                    for p2 in range(cfg.n_products)
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
    for oid in range(cfg.n_operators):
        elig = {m for m in range(cfg.n_machines)
                if rng.random() < cfg.operator_machine_coverage}
        if not elig:
            elig = {rng.randrange(cfg.n_machines)}

        shifts: list[tuple[int, int]] = []
        t = 0
        while t < cfg.horizon:
            shift_len = rng.randint(25, 60)
            end = min(cfg.horizon, t + shift_len)
            if end > t:
                shifts.append((t, end))
            t = end + rng.randint(8, 16)
        if not shifts:
            shifts.append((0, cfg.horizon))
        operators.append(Operator(
            operator_id=oid,
            name=f"Op{oid}",
            eligible_machines=frozenset(elig),
            shifts=tuple(shifts),
        ))

    # Repair: every machine must have at least one operator.
    for mid in range(cfg.n_machines):
        if not any(mid in op.eligible_machines for op in operators):
            i = rng.randrange(cfg.n_operators)
            old = operators[i]
            operators[i] = replace(old,
                eligible_machines=frozenset(old.eligible_machines | {mid}))

    # ---- orders -------------------------------------------------------
    orders: list[Order] = []
    for jid in range(cfg.n_orders):
        pid = rng.randrange(cfg.n_products)
        product = products[pid]
        avg_total = sum(
            sum(s.eligible_machines.values()) / len(s.eligible_machines)
            for s in product.stages
        )
        deadline = int(avg_total * rng.uniform(1.5, 3.0)) + jid * 4
        orders.append(Order(job_id=jid, product_id=pid, deadline=deadline))

    return Instance(
        name=cfg.name,
        horizon=cfg.horizon,
        products=products,
        machines=machines,
        operators=operators,
        orders=orders,
        stage_machines=stage_machines,
        machine_stage_mode=cfg.machine_stage_mode,
    )
