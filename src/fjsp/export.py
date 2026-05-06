"""Export the instance and schedule for the React-based web viewer.

The viewer (web/index.html) loads `web/data.js`, which sets a single
global `window.SCHEDULE_DATA`. We write a JS file rather than a JSON
file so the viewer works from `file://` (no local server needed).
"""

import json
from pathlib import Path

from .data import FJSPInstance
from .solver import Schedule


def export_web_data(
    instance: FJSPInstance,
    sched: Schedule,
    path: str | Path = "web/data.js",
) -> Path:
    horizon = sched.makespan + 2
    payload = {
        "n_machines": instance.n_machines,
        "n_operators": instance.n_operators,
        "n_products": instance.n_products,
        "horizon": horizon,
        "machine_windows": [
            [list(w) for w in wins] for wins in instance.machine_windows
        ],
        "operator_windows": [
            [list(w) for w in wins] for wins in instance.operator_windows
        ],
        "schedule": {
            "makespan": sched.makespan,
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
                }
                for s in sched.ops
            ],
        },
    }
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("window.SCHEDULE_DATA = " + json.dumps(payload, indent=2) + ";\n")
    return p
