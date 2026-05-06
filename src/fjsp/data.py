"""FJSP data model with three real-world extensions.

Extensions over the textbook FJSP:
  1. Machine availability — each machine is only usable during a set of
     time windows (e.g. maintenance closes a machine for a while).
  2. Operator availability — each operation also needs an operator drawn
     from a permitted subset; operators have their own availability windows
     (e.g. a worker is on a meal break).
  3. Product-dependent setup times — when a machine switches from product
     p1 to product p2 it incurs a setup of duration s(machine, p1, p2).

A `Window` is a closed interval [start, end]; the resource is available
to perform an operation iff the whole [op.start, op.end] interval lies
inside one of its windows. We use HORIZON for "effectively unbounded".
"""

from dataclasses import dataclass

HORIZON = 10_000  # large enough to act as "always available"


@dataclass(frozen=True)
class Operation:
    job_id: int
    op_idx: int
    product_id: int
    machine_options: dict[int, int]  # machine_id -> processing time
    operator_options: frozenset[int]  # eligible operator ids

    def __repr__(self) -> str:
        return f"O({self.job_id},{self.op_idx})[P{self.product_id}]"


@dataclass
class FJSPInstance:
    n_machines: int
    n_operators: int
    n_products: int
    jobs: list[list[Operation]]
    machine_windows: list[list[tuple[int, int]]]  # per machine: available windows
    operator_windows: list[list[tuple[int, int]]]  # per operator: available windows
    # setup_times[machine][prev_product or -1][curr_product]
    # (prev_product = -1 means "no previous job ran on this machine yet")
    setup_times: list[dict[int, dict[int, int]]]

    @property
    def n_jobs(self) -> int:
        return len(self.jobs)

    def setup(self, machine: int, prev_product: int | None, curr_product: int) -> int:
        key = -1 if prev_product is None else prev_product
        return self.setup_times[machine][key].get(curr_product, 0)


def toy_instance() -> FJSPInstance:
    """The 2-job, 2-machine, 2-operator instance used in the README trace.

    - Job 0 produces product P0; Job 1 produces product P1.
    - Machine M1 has a maintenance window: unavailable during [3, 5).
    - Operator Op0 has a lunch break: unavailable during [4, 6).
    - Setup matrix (same on both machines):
                P0   P1
        none    0    0
        P0      0    1
        P1      2    0
    """
    jobs = [
        [
            Operation(
                0,
                0,
                product_id=0,
                machine_options={0: 3, 1: 2},
                operator_options=frozenset({0, 1}),
            ),
            Operation(
                0,
                1,
                product_id=0,
                machine_options={0: 2, 1: 4},
                operator_options=frozenset({0, 1}),
            ),
        ],
        [
            Operation(
                1,
                0,
                product_id=1,
                machine_options={0: 4, 1: 3},
                operator_options=frozenset({0, 1}),
            ),
            Operation(
                1,
                1,
                product_id=1,
                machine_options={0: 3, 1: 5},
                operator_options=frozenset({0, 1}),
            ),
        ],
    ]
    machine_windows = [
        [(0, HORIZON)],  # M0 always available
        [(0, 3), (5, HORIZON)],  # M1 down for [3, 5)
    ]
    operator_windows = [
        [(0, 4), (7, HORIZON)],  # Op0 lunch break [4, 6)
        [(0, 5), (7, HORIZON)],  # Op1 lunch break [5, 7)
    ]
    base_matrix = {
        -1: {0: 0, 1: 0},  # initial setup is free
        0: {0: 0, 1: 1},  # P0 -> P0 / P0 -> P1
        1: {0: 2, 1: 0},  # P1 -> P0 / P1 -> P1
    }
    setup_times = [base_matrix, base_matrix]
    return FJSPInstance(
        n_machines=2,
        n_operators=2,
        n_products=2,
        jobs=jobs,
        machine_windows=machine_windows,
        operator_windows=operator_windows,
        setup_times=setup_times,
    )
