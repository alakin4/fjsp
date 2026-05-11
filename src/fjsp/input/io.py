"""JSON serialization for FJSP instances.

The on-disk format is one JSON object per instance. JSON object keys are
always strings, so any int-keyed dict (processing times, setup times)
gets `str` keys in the file and is converted back to `int` here on load.
"""

import json
from pathlib import Path

from .domain import (
    Instance,
    Machine,
    Operator,
    Order,
    OrderStatus,
    Product,
    Stage,
    StageHistory,
    StageMode,
)


# -------------------------------- save -----------------------------------

def _stage_to_json(s: Stage) -> dict:
    return {
        "stage_idx": s.stage_idx,
        "name": s.name,
        "eligible_machines": {str(m): p for m, p in s.eligible_machines.items()},
    }


def _product_to_json(p: Product) -> dict:
    return {
        "id": p.product_id,
        "name": p.name,
        "stages": [_stage_to_json(s) for s in p.stages],
    }


def _machine_to_json(m: Machine) -> dict:
    return {
        "id": m.machine_id,
        "name": m.name,
        "availability": [list(w) for w in m.availability],
        "setup_times": {
            str(prev): {str(curr): dur for curr, dur in inner.items()}
            for prev, inner in m.setup_times.items()
        },
        "current_product_id": m.current_product_id,
    }


def _operator_to_json(o: Operator) -> dict:
    return {
        "id": o.operator_id,
        "name": o.name,
        "eligible_machines": sorted(o.eligible_machines),
        "shifts": [list(w) for w in o.shifts],
    }


def _stage_history_to_json(h: StageHistory) -> dict:
    return {
        "stage_idx": h.stage_idx,
        "machine_id": h.machine_id,
        "operator_id": h.operator_id,
        "start": h.start,
        "end": h.end,
        "setup_duration": h.setup_duration,
    }


def _order_to_json(o: Order) -> dict:
    return {
        "job_id": o.job_id,
        "product_id": o.product_id,
        "deadline": o.deadline,
        "status": {
            "completed": [_stage_history_to_json(h) for h in o.status.completed],
            "running": [_stage_history_to_json(h) for h in o.status.running],
        },
    }


def save_instance(instance: Instance, path: str | Path) -> Path:
    payload = {
        "name": instance.name,
        "horizon": instance.horizon,
        "machine_stage_mode": instance.machine_stage_mode,
        "stage_machines": (
            [list(s) for s in instance.stage_machines]
            if instance.stage_machines is not None else None
        ),
        "products": [_product_to_json(p) for p in instance.products],
        "machines": [_machine_to_json(m) for m in instance.machines],
        "operators": [_operator_to_json(o) for o in instance.operators],
        "orders": [_order_to_json(o) for o in instance.orders],
    }
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2) + "\n")
    return p


# -------------------------------- load -----------------------------------

def _stage_from_json(d: dict) -> Stage:
    return Stage(
        stage_idx=d["stage_idx"],
        name=d["name"],
        eligible_machines={int(m): int(p) for m, p in d["eligible_machines"].items()},
    )


def _product_from_json(d: dict) -> Product:
    return Product(
        product_id=d["id"],
        name=d["name"],
        stages=tuple(_stage_from_json(s) for s in d["stages"]),
    )


def _machine_from_json(d: dict) -> Machine:
    setup_times = {
        int(prev): {int(curr): int(dur) for curr, dur in inner.items()}
        for prev, inner in d.get("setup_times", {}).items()
    }
    return Machine(
        machine_id=d["id"],
        name=d["name"],
        availability=tuple(tuple(w) for w in d["availability"]),
        setup_times=setup_times,
        current_product_id=d.get("current_product_id"),
    )


def _operator_from_json(d: dict) -> Operator:
    return Operator(
        operator_id=d["id"],
        name=d["name"],
        eligible_machines=frozenset(d["eligible_machines"]),
        shifts=tuple(tuple(w) for w in d["shifts"]),
    )


def _stage_history_from_json(d: dict) -> StageHistory:
    return StageHistory(
        stage_idx=d["stage_idx"],
        machine_id=d["machine_id"],
        operator_id=d["operator_id"],
        start=d["start"],
        end=d["end"],
        setup_duration=d.get("setup_duration", 0),
    )


def _order_from_json(d: dict) -> Order:
    s = d.get("status", {})
    status = OrderStatus(
        completed=[_stage_history_from_json(h) for h in s.get("completed", [])],
        running=[_stage_history_from_json(h) for h in s.get("running", [])],
    )
    return Order(
        job_id=d["job_id"],
        product_id=d["product_id"],
        deadline=d["deadline"],
        status=status,
    )


def load_instance(path: str | Path) -> Instance:
    payload = json.loads(Path(path).read_text())
    sm = payload.get("stage_machines")
    instance = Instance(
        name=payload["name"],
        horizon=payload["horizon"],
        products=[_product_from_json(p) for p in payload["products"]],
        machines=[_machine_from_json(m) for m in payload["machines"]],
        operators=[_operator_from_json(o) for o in payload["operators"]],
        orders=[_order_from_json(o) for o in payload["orders"]],
        stage_machines=([list(s) for s in sm] if sm is not None else None),
        machine_stage_mode=payload.get("machine_stage_mode", StageMode.SHARED),
    )
    validate_instance(instance)
    return instance


# ------------------------------ validation -------------------------------

def validate_instance(instance: Instance) -> None:
    """Internal-consistency checks (raises ValueError on the first problem).

    Catches:
      - per_stage layout with overlapping machine assignments;
      - stage_machines pointing at machine ids that don't exist;
      - product stages whose eligible machines escape the shop's per-stage
        whitelist.
    """
    sm = instance.stage_machines
    if sm is None:
        return

    n_m = instance.n_machines
    for s_idx, machines in enumerate(sm):
        for m in machines:
            if not (0 <= m < n_m):
                raise ValueError(
                    f"stage_machines[{s_idx}] references machine {m} "
                    f"but instance has only {n_m} machines"
                )

    if instance.machine_stage_mode == StageMode.PER_STAGE:
        seen: dict[int, int] = {}
        for s_idx, machines in enumerate(sm):
            for m in machines:
                if m in seen:
                    raise ValueError(
                        f"per_stage mode: machine {m} appears in stage "
                        f"{seen[m]} and stage {s_idx} (must be exclusive)"
                    )
                seen[m] = s_idx

    for product in instance.products:
        for stage in product.stages:
            if not (0 <= stage.stage_idx < len(sm)):
                raise ValueError(
                    f"P{product.product_id} stage_idx={stage.stage_idx} "
                    f"is out of range (shop has {len(sm)} stages)"
                )
            allowed = set(sm[stage.stage_idx])
            actual = set(stage.eligible_machines.keys())
            extras = actual - allowed
            if extras:
                raise ValueError(
                    f"P{product.product_id} stage {stage.stage_idx} "
                    f"lists machines {sorted(extras)} that are not "
                    f"in shop's stage_machines[{stage.stage_idx}] = "
                    f"{sorted(allowed)}"
                )
