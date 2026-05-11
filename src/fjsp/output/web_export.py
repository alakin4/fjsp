"""Export the instance and schedule for the React-based web viewer.

The viewer (`web/index.html`) loads `web/data.js`, which sets a single
global `window.SCHEDULE_DATA`. We emit a JS file (not JSON) so the viewer
works from `file://` without needing a local server.

Each op carries a `state` field so the viewer can filter and style by
completed / running / pending.
"""

import json
from pathlib import Path

from ..input.domain import Instance
from ..solver import Schedule, combined_ops, total_makespan


def export_web_data(
    instance: Instance,
    sched: Schedule,
    path: str | Path = "web/data.js",
) -> Path:
    all_ops = combined_ops(instance, sched)
    cmax = total_makespan(instance, sched)

    # Time axis bounds wide enough to cover any past/future op.
    time_min = min((s.start for s in all_ops), default=0)
    time_min = min(0, time_min)
    time_max = max(cmax + 2, max((s.end for s in all_ops), default=0) + 1)

    payload = {
        "name": instance.name,
        "n_machines": instance.n_machines,
        "n_operators": instance.n_operators,
        "n_products": instance.n_products,
        "time_min": time_min,
        "horizon": time_max,
        "machines": [
            {"id": m.machine_id, "name": m.name,
             "stage": instance.stage_of_machine(m.machine_id)}
            for m in instance.machines
        ],
        "stage_machines": (
            [list(s) for s in instance.stage_machines]
            if instance.stage_machines is not None else None
        ),
        "machine_stage_mode": instance.machine_stage_mode,
        "operators": [
            {"id": o.operator_id, "name": o.name}
            for o in instance.operators
        ],
        "products": [
            {"id": p.product_id, "name": p.name}
            for p in instance.products
        ],
        "machine_windows": [
            [list(w) for w in m.availability] for m in instance.machines
        ],
        "operator_windows": [
            [list(w) for w in o.shifts] for o in instance.operators
        ],
        "orders": [
            {
                "job_id": o.job_id,
                "product_id": o.product_id,
                "deadline": o.deadline,
                "completed_stages": sorted(o.status.completed_stage_indices),
                "running_stages": sorted(o.status.running_stage_indices),
            }
            for o in instance.orders
        ],
        "schedule": {
            "makespan": cmax,
            "solver_makespan": sched.makespan,
            "ops": [
                {
                    "job_id": s.op.job_id,
                    "op_idx": s.op.op_idx,
                    "product_id": s.op.product_id,
                    "machine": s.machine,
                    "operator": s.operator,
                    "start": s.start,
                    "setup_duration": s.setup_duration,
                    "proc_start": s.proc_start,
                    "end": s.end,
                    "state": s.state,
                }
                for s in all_ops
            ],
        },
    }
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("window.SCHEDULE_DATA = " + json.dumps(payload, indent=2) + ";\n")
    return p
