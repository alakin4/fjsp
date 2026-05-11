"""FJSP solver: GRASP for the flexible job-shop with availability,
setups, and per-stage order status."""

from .cli import cli
from .input.config import ProblemConfig, load_config
from .input.domain import (
    HORIZON,
    Instance,
    Machine,
    Operator,
    Order,
    OrderStatus,
    Product,
    Stage,
    StageHistory,
    StageMode,
    StageState,
)
from .input.generator import random_instance, toy_instance
from .input.io import load_instance, save_instance, validate_instance
from .output.gantt import plot_gantt
from .output.web_export import export_web_data
from .solver import (
    OperationView,
    Schedule,
    ScheduledOp,
    combined_ops,
    construct,
    grasp,
    local_search,
    simulate,
    total_makespan,
)


def main() -> None:
    """Entry point for `uv run fjsp`. Delegates to the click CLI."""
    cli()


__all__ = [
    "HORIZON",
    "Instance",
    "Machine",
    "OperationView",
    "Operator",
    "Order",
    "OrderStatus",
    "ProblemConfig",
    "Product",
    "Schedule",
    "ScheduledOp",
    "Stage",
    "StageHistory",
    "StageMode",
    "StageState",
    "cli",
    "combined_ops",
    "construct",
    "export_web_data",
    "grasp",
    "load_config",
    "load_instance",
    "local_search",
    "main",
    "plot_gantt",
    "random_instance",
    "save_instance",
    "simulate",
    "toy_instance",
    "total_makespan",
    "validate_instance",
]
