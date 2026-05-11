"""Data input layer: domain types, JSON IO, and instance generation."""

from .config import ProblemConfig, load_config
from .domain import (
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
from .generator import random_instance, toy_instance
from .io import load_instance, save_instance

__all__ = [
    "HORIZON",
    "Instance",
    "Machine",
    "Operator",
    "Order",
    "OrderStatus",
    "ProblemConfig",
    "Product",
    "Stage",
    "StageHistory",
    "StageMode",
    "StageState",
    "load_config",
    "load_instance",
    "random_instance",
    "save_instance",
    "toy_instance",
]
