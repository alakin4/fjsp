"""YAML-driven configuration for FJSP instance generation.

A `ProblemConfig` defines the shop layout (number of stages, how machines
are distributed across stages) and the random-generation knobs. It is
loaded from a YAML file by `load_config` and consumed by
`generator.random_instance`.
"""

from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Optional

import yaml

from .domain import StageMode


@dataclass
class ProblemConfig:
    # Instance metadata
    name: str = "rand"
    horizon: int = 200

    # Counts
    n_products: int = 4
    n_machines: int = 5
    n_operators: int = 4
    n_orders: int = 10

    # Shop-level stage layout
    n_stages: int = 3
    machine_stage_mode: str = StageMode.SHARED   # or StageMode.PER_STAGE
    # Optional explicit per-stage machine list. If omitted:
    #   per_stage → partition `n_machines` evenly across `n_stages`
    #   shared    → each machine joins each stage with prob `stage_share`
    stage_machines: Optional[list[list[int]]] = None
    stage_share: float = 0.6   # only used when stage_machines is unset + shared

    # Operators
    operator_machine_coverage: float = 0.7

    # Setups
    setup_machines_fraction: float = 0.5
    setup_time_min: int = 1
    setup_time_max: int = 3

    # Processing time
    proc_time_min: int = 2
    proc_time_max: int = 8

    # Random seed
    seed: int = 0


def load_config(path: str | Path) -> ProblemConfig:
    """Load a ProblemConfig from a YAML file. Unknown keys are ignored
    so configs can carry user-defined notes without breaking the loader."""
    raw = yaml.safe_load(Path(path).read_text()) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: top-level YAML must be a mapping")
    known = {f.name for f in fields(ProblemConfig)}
    valid = {k: v for k, v in raw.items() if k in known}
    return ProblemConfig(**valid)
