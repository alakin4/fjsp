from .data import HORIZON, FJSPInstance, Operation, toy_instance
from .export import export_web_data
from .solver import Schedule, ScheduledOp, construct, grasp, local_search, simulate
from .visualization import plot_gantt


def main() -> None:
    """`uv run fjsp` — solve the toy instance, print, and write outputs."""
    inst = toy_instance()
    sched = grasp(inst, max_iter=200, alpha=0.3, seed=0)
    print(f"Cmax = {sched.makespan}")
    print(f"{'op':<14} {'mach':<5} {'op#':<5} {'setup':<6} "
          f"{'proc_start':<11} {'end':<5}")
    for s in sched.ops:
        print(f"{repr(s.op):<14} M{s.machine:<4} "
              f"Op{s.operator:<3} {s.setup_duration:<6} "
              f"{s.proc_start:<11} {s.end:<5}")
    plot_gantt(sched, inst, save_path="gantt.png")
    web_path = export_web_data(inst, sched, "web/data.js")
    print(f"Static Gantt:        gantt.png")
    print(f"Interactive viewer:  open web/index.html  (data: {web_path})")


__all__ = [
    "FJSPInstance",
    "HORIZON",
    "Operation",
    "Schedule",
    "ScheduledOp",
    "construct",
    "export_web_data",
    "grasp",
    "local_search",
    "main",
    "plot_gantt",
    "simulate",
    "toy_instance",
]
