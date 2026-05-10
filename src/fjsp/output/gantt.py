"""Static matplotlib Gantt chart for an FJSP schedule.

Shows completed, running, and newly-scheduled (pending) ops, each with a
distinct visual style.
"""

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt

from ..input.domain import Instance, StageState
from ..solver import Schedule, combined_ops, total_makespan


def _gaps(windows, lo: int, hi: int) -> list[tuple[int, int]]:
    """Inverted intervals: when the resource is unavailable in [lo, hi]."""
    sorted_w = sorted(windows)
    gaps: list[tuple[int, int]] = []
    cursor = lo
    for a, b in sorted_w:
        if b <= lo:
            continue
        if a >= hi:
            break
        a, b = max(a, lo), min(b, hi)
        if a > cursor:
            gaps.append((cursor, a))
        cursor = max(cursor, b)
    if cursor < hi:
        gaps.append((cursor, hi))
    return gaps


def plot_gantt(
    sched: Schedule,
    instance: Instance,
    save_path: str | None = None,
    title: str = "FJSP schedule",
) -> None:
    n_m, n_o = instance.n_machines, instance.n_operators
    fig, ax = plt.subplots(figsize=(12, 0.8 * (n_m + n_o) + 1.5))
    cmap = plt.get_cmap("tab10")

    all_ops = combined_ops(instance, sched)
    cmax = total_makespan(instance, sched)
    t_min = min(0, min((s.start for s in all_ops), default=0))
    t_max = max(cmax + 2, max((s.end for s in all_ops), default=0) + 1)

    # Unavailability bands (gray, hatched), clipped to chart range.
    for m in range(n_m):
        for a, b in _gaps(instance.machines[m].availability, t_min, t_max):
            ax.barh(m, b - a, left=a, height=0.6,
                    color="lightgray", hatch="///", edgecolor="gray")
    for o in range(n_o):
        for a, b in _gaps(instance.operators[o].shifts, t_min, t_max):
            ax.barh(n_m + o, b - a, left=a, height=0.6,
                    color="lightgray", hatch="///", edgecolor="gray")

    # Style helpers per state.
    def edge(state: str) -> dict:
        if state == StageState.COMPLETED:
            return {"linestyle": "--", "edgecolor": "#1a7f37", "linewidth": 1.5,
                    "alpha": 0.55}
        if state == StageState.RUNNING:
            return {"linestyle": "-", "edgecolor": "#0969da", "linewidth": 2.0,
                    "alpha": 1.0}
        return {"linestyle": "-", "edgecolor": "black", "linewidth": 0.8,
                "alpha": 1.0}

    for s in all_ops:
        color = cmap(s.op.job_id % 10)
        st = edge(s.state)

        if s.setup_duration > 0:
            ax.barh(s.machine, s.setup_duration, left=s.start, height=0.6,
                    color=color, alpha=st["alpha"] * 0.4,
                    edgecolor=st["edgecolor"], linewidth=st["linewidth"],
                    linestyle=st["linestyle"], hatch="//")
        ax.barh(s.machine, s.end - s.proc_start, left=s.proc_start,
                height=0.6, color=color, alpha=st["alpha"],
                edgecolor=st["edgecolor"], linewidth=st["linewidth"],
                linestyle=st["linestyle"])
        ax.text((s.proc_start + s.end) / 2, s.machine,
                f"J{s.op.job_id}-O{s.op.op_idx}",
                ha="center", va="center", fontsize=8, color="white")
        ax.barh(n_m + s.operator, s.end - s.proc_start, left=s.proc_start,
                height=0.6, color=color, alpha=st["alpha"] * 0.85,
                edgecolor=st["edgecolor"], linewidth=st["linewidth"],
                linestyle=st["linestyle"])

    # "now" line at t = 0 if anything is in the past.
    if t_min < 0:
        ax.axvline(0, color="#0969da", linewidth=1.0, linestyle=":")
        ax.text(0, n_m + n_o - 0.5, " now", color="#0969da", fontsize=9, va="top")

    ax.set_yticks(list(range(n_m)) + [n_m + i for i in range(n_o)])
    ax.set_yticklabels([instance.machines[m].name for m in range(n_m)] +
                       [instance.operators[o].name for o in range(n_o)])
    ax.set_xlabel("Time")
    ax.set_xlim(t_min, t_max)
    ax.set_title(f"{title} ({instance.name})  Cmax = {cmax}")
    ax.grid(axis="x", linestyle=":", alpha=0.5)

    legend = [
        mpatches.Patch(facecolor="white", edgecolor="black", label="pending"),
        mpatches.Patch(facecolor="white", edgecolor="#0969da", linewidth=2,
                       label="running"),
        mpatches.Patch(facecolor="white", edgecolor="#1a7f37", linestyle="--",
                       label="completed"),
        mpatches.Patch(facecolor="white", hatch="//", edgecolor="black",
                       label="setup"),
        mpatches.Patch(facecolor="lightgray", hatch="///", label="unavailable"),
    ]
    ax.legend(handles=legend, loc="upper right", fontsize=8)
    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=130)
        plt.close(fig)
    else:
        plt.show()
