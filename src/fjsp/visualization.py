"""Gantt chart for an FJSP schedule with availability gaps and setups."""

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt

from .data import FJSPInstance
from .solver import Schedule


def _gaps(windows: list[tuple[int, int]], horizon: int) -> list[tuple[int, int]]:
    """Inverted intervals: when the resource is *unavailable* up to `horizon`."""
    gaps: list[tuple[int, int]] = []
    sorted_w = sorted(windows)
    if sorted_w[0][0] > 0:
        gaps.append((0, sorted_w[0][0]))
    for (a, b), (c, d) in zip(sorted_w, sorted_w[1:]):
        if c > b:
            gaps.append((b, c))
    if sorted_w[-1][1] < horizon:
        gaps.append((sorted_w[-1][1], horizon))
    return gaps


def plot_gantt(
    sched: Schedule,
    instance: FJSPInstance,
    save_path: str | None = None,
    title: str = "FJSP schedule",
) -> None:
    n_m, n_o = instance.n_machines, instance.n_operators
    fig, ax = plt.subplots(figsize=(12, 0.8 * (n_m + n_o) + 1.5))
    cmap = plt.get_cmap("tab10")
    horizon = sched.makespan + 2

    # Draw unavailability bands (gray, hatched).
    for m, wins in enumerate(instance.machine_windows):
        for a, b in _gaps(wins, horizon):
            ax.barh(m, b - a, left=a, height=0.6,
                    color="lightgray", hatch="///", edgecolor="gray")
    for o, wins in enumerate(instance.operator_windows):
        for a, b in _gaps(wins, horizon):
            ax.barh(n_m + o, b - a, left=a, height=0.6,
                    color="lightgray", hatch="///", edgecolor="gray")

    # Draw scheduled ops on machine row and operator row.
    for s in sched.ops:
        color = cmap(s.op.job_id % 10)
        if s.setup_duration > 0:
            ax.barh(s.machine, s.setup_duration, left=s.start, height=0.6,
                    color=color, alpha=0.35, edgecolor="black")
        ax.barh(s.machine, s.end - s.proc_start, left=s.proc_start, height=0.6,
                color=color, edgecolor="black")
        ax.text((s.proc_start + s.end) / 2, s.machine,
                f"J{s.op.job_id}-O{s.op.op_idx}",
                ha="center", va="center", fontsize=8, color="white")
        ax.barh(n_m + s.operator, s.end - s.proc_start, left=s.proc_start,
                height=0.6, color=color, edgecolor="black", alpha=0.85)

    ax.set_yticks(list(range(n_m)) + [n_m + i for i in range(n_o)])
    ax.set_yticklabels([f"M{m}" for m in range(n_m)] +
                       [f"Op{o}" for o in range(n_o)])
    ax.set_xlabel("Time")
    ax.set_xlim(0, horizon)
    ax.set_title(f"{title}  (Cmax = {sched.makespan})")
    ax.grid(axis="x", linestyle=":", alpha=0.5)

    legend = [
        mpatches.Patch(facecolor="white", edgecolor="black", label="processing"),
        mpatches.Patch(facecolor="white", edgecolor="black", alpha=0.35, label="setup"),
        mpatches.Patch(facecolor="lightgray", hatch="///", label="unavailable"),
    ]
    ax.legend(handles=legend, loc="upper right", fontsize=8)
    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=130)
        plt.close(fig)
    else:
        plt.show()
