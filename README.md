# Building a GRASP solver for the Flexible Job-Shop Problem

A small, readable Python implementation of **GRASP** (Greedy Randomized
Adaptive Search Procedure) for an **extended Flexible Job-Shop Problem**
(FJSP). The instance model covers the constraints that show up on a
real shop floor: shop-level production stages with optional
stage–machine partitioning, machine availability windows, operator
shifts and operator–machine eligibility, product-dependent setup times,
and per-stage real-time order status (completed / running / pending).

The code is organized into three layers — **input** (data), **solver**
(GRASP), and **output** (visualization & export):

| Layer       | Modules                                                                                                                   | Role                                                            |
| ----------- | ------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| Input       | [src/fjsp/input/domain.py](src/fjsp/input/domain.py), [io.py](src/fjsp/input/io.py), [generator.py](src/fjsp/input/generator.py) | Domain types · JSON load/save · `toy_instance()` and `random_instance()` |
| Solver      | [src/fjsp/solver.py](src/fjsp/solver.py)                                                                                  | GRASP construction + local search, with running-op pinning      |
| Output      | [src/fjsp/output/gantt.py](src/fjsp/output/gantt.py), [web_export.py](src/fjsp/output/web_export.py), [web/index.html](web/index.html) | Matplotlib Gantt · React viewer with search, filters, tooltips |
| CLI         | [src/fjsp/cli.py](src/fjsp/cli.py)                                                                                        | `fjsp solve` · `fjsp generate` · `fjsp inspect` (click-based)   |
| Instances   | [instances/](instances/)                                                                                                  | One JSON file per instance                                      |

The implementation follows the canonical formulation from
**Resende & Ribeiro (2016)**, *Optimization by GRASP* (in [docs/](docs/)).
The choice of constraints is inspired by **Cartes & Medina (2016)**,
*A GRASP Algorithm for the Elective Surgeries Scheduling Problem in a
Chilean Public Hospital* (also in [docs/](docs/)), which uses GRASP for
a problem with surgeon/nurse/anesthetist availability — directly
analogous to operator availability in our FJSP.

---

## 1. The problem

### 1.1 Classical FJSP

You have:

- `n` jobs. Job `i` is an *ordered* sequence of operations
  `O_{i,1}, O_{i,2}, ..., O_{i,n_i}`.
- `m` machines.
- For each operation `O_{i,j}`, a subset `F_{i,j}` of *eligible* machines
  with a (possibly different) processing time on each.
- Two decisions per operation:
    1. **routing**: pick one machine from `F_{i,j}`,
    2. **sequencing**: pick when to run on that machine.
- The standard objective is to minimize the **makespan** `C_max`, i.e.,
  the time the last operation finishes.

### 1.2 What an instance carries

The instances this codebase represents and generates go beyond the
textbook FJSP. Concretely, every instance carries:

1. **Products with shop-level production stages.** Each product has a
   *fixed ordered list* of stages; stage indices are global concepts
   (shared across all products), not per-product. A product's `Stage`
   declares the machines it can run on at that stage and the processing
   time on each.

2. **Shop-level stage layout.** The shop tells you which machines are
   eligible for each stage via `Instance.stage_machines`. Two modes
   (`Instance.machine_stage_mode`):

   - `per_stage` — each machine belongs to *exactly one* stage. Models
     a flow-shop with stage-specialized machines (paint booth ↔ painting,
     CNC mill ↔ milling, etc.); the per-stage machine lists are disjoint.
   - `shared` — a machine may serve *multiple* stages. Standard FJSP.

   A validator enforces that every product's `Stage.eligible_machines[k]`
   is a subset of `stage_machines[k]`.

3. **Machine availability windows.** Each machine has a list of closed
   intervals during which it is usable (i.e. *not* under maintenance).
   An operation can be processed on a machine only if its entire
   `setup + processing` block fits inside one window.

4. **Machine setup matrices** (sequence-dependent setup times, SDST).
   Each machine has an optional product-dependent setup matrix
   `s(prev, curr)`; an empty matrix means the machine never requires
   setup. A `Machine.current_product_id` field captures the product
   most recently processed so the *first* newly-scheduled op pays the
   right setup.

5. **Operators with shifts and machine eligibility.** Every operation
   needs both a machine and an operator present for the whole block.
   Operators carry (a) the subset of machines they can run, and (b)
   their own shift availability windows (work / break alternation).

6. **Orders with deadlines and per-stage real-time status.** Each stage
   of each order is in exactly one of three buckets:

   - `completed` — already finished; the order's `OrderStatus.completed`
     entry records the past machine, operator, start, end and setup.
   - `running` — currently in progress; the `OrderStatus.running` entry
     pins a (machine, operator) pair busy until its expected end.
   - `pending` — derived (everything else); these are the only stages
     the solver actually schedules.

The constraint shape echoes the surgery-scheduling problem in
Cartes & Medina (2016) — rooms ↔ machines, surgeons / nurses ↔
operators, surgical-team compatibility ↔ setups — making GRASP a
natural fit.

### 1.3 Domain model

The relational shape — mirroring how the data would live in a real
shop's database — is in
[src/fjsp/input/domain.py](src/fjsp/input/domain.py):

| Type           | Real-world counterpart                                                                 |
| -------------- | -------------------------------------------------------------------------------------- |
| `Product`      | A manufactured product type with an ordered list of `Stage`s                          |
| `Stage`        | One production step + the machines this product uses for it + processing time on each |
| `Machine`      | A machine, its availability windows, its setup matrix, and its current/last product   |
| `Operator`     | A worker: which machines they can run + their shift availability                       |
| `Order`        | A customer order = a job; product + deadline + per-stage `OrderStatus`                 |
| `OrderStatus`  | Two lists of `StageHistory`: `completed` and `running`; `pending` is derived           |
| `StageHistory` | An already-known stage instance: machine, operator, start, end, setup duration         |
| `Instance`     | Everything above + horizon + `stage_machines` + `machine_stage_mode`                   |

Instances are loaded from / saved to JSON via
[`load_instance`](src/fjsp/input/io.py) /
[`save_instance`](src/fjsp/input/io.py). `load_instance` runs
[`validate_instance`](src/fjsp/input/io.py) automatically — refusing an
instance whose product stages escape the shop's per-stage whitelist or
that violates `per_stage` disjointness. The JSON schema is documented
in [instances/README.md](instances/README.md).

### 1.4 Generating instances

Two builders in [src/fjsp/input/generator.py](src/fjsp/input/generator.py):

- **`toy_instance()`** — a fixed 2-product / 4-machine / 2-stage /
  2-operator example used in §1.5 and throughout this README.
- **`random_instance(config, **overrides)`** — parametric synthetic
  generation driven by a
  [`ProblemConfig`](src/fjsp/input/config.py), normally loaded from a
  YAML file:

  ```bash
  uv run fjsp generate -c instances/small-1/problem_config.yaml \
      --seed 42 --out-dir instances/my-instance
  ```

  Knobs on the config:

  | Field                                                     | What it controls                                              |
  | --------------------------------------------------------- | ------------------------------------------------------------- |
  | `n_products`, `n_machines`, `n_operators`, `n_orders`     | counts                                                        |
  | `horizon`                                                 | planning horizon (also caps window upper bounds)              |
  | `n_stages`, `machine_stage_mode`                          | shop-level stage layout                                       |
  | `stage_machines`                                          | explicit per-stage machine list (auto-partitioned if omitted) |
  | `operator_machine_coverage`                               | `P(operator allowed on each machine)`                         |
  | `setup_machines_fraction`                                 | fraction of machines that have a non-empty setup matrix       |
  | `setup_time_min` / `_max`, `proc_time_min` / `_max`       | duration bounds                                               |
  | `seed`                                                    | random seed                                                   |

  When `stage_machines` is left blank: `per_stage` mode round-robins
  `M0..M{n-1}` across `n_stages`; `shared` mode joins each
  `(machine, stage)` pair independently with probability
  `stage_share`. See
  [instances/small-1/problem_config.yaml](instances/small-1/problem_config.yaml)
  for the example wired to the bundled `small-1` instance.

Per-flag CLI options (`--mode`, `--machines`, `--seed`, …) override
individual fields of the loaded config. `fjsp inspect <instance.json>`
prints a human-readable summary including the stage layout.

### 1.5 Toy instance

The instance built by `toy_instance()` and saved as
[instances/toy/instance.json](instances/toy/instance.json) has **2 products, 4 machines,
2 operators**, in `per_stage` mode with **2 stages**:

- **stage 0** → machines M0, M1
- **stage 1** → machines M2, M3

Per-product processing times:

| Product | Stage 0 (M0 / M1) | Stage 1 (M2 / M3) |
| ------- | ----------------- | ----------------- |
| P0      | 3 / 2             | 2 / 4             |
| P1      | 4 / 3             | 3 / 5             |

Availability:

- **M0** always available · **M1** maintenance in `[3, 5)`
- **M2** always available · **M3** maintenance in `[4, 6)`
- **Op0** lunch break in `[4, 7)` · **Op1** lunch break in `[5, 7)`

Both operators can run all four machines. Setup matrix `s(prev, curr)`
(applied uniformly on every machine):

|              | curr = P0 | curr = P1 |
| ------------ | --------- | --------- |
| prev = ⊥     | 0         | 0         |
| prev = P0    | 0         | 1         |
| prev = P1    | 2         | 0         |

Switching from P0 to P1 costs 1 unit of setup; from P1 to P0, 2; staying
on the same product is free; the first op on a machine is free.

The companion [instances/toy-running/instance.json](instances/toy-running/instance.json)
extends this with three orders that exercise the per-stage status
machinery — one all-pending, one with a completed stage, one mid-flight
on a stage-1 machine — see §5.5 for what the solver does with each.

---

## 2. GRASP in 30 seconds

GRASP (Feo & Resende 1989, 1995; Resende & Ribeiro 2016) is a
**multistart** metaheuristic. Each iteration has two phases:

1. **Construction** — build a feasible solution with a *semi-greedy*
   rule, i.e. greedy with a controlled dose of randomness.
2. **Local search** — improve that solution to a local optimum.

The randomness lets GRASP visit many *different* basins of attraction
across iterations; the local search slides each starting point to the
bottom of its basin. The best local optimum found over all iterations
is returned.

The randomness knob is the **RCL parameter** `α ∈ [0, 1]`. For a
minimization problem (Resende & Ribeiro 2016, p. 60):

```
RCL = { c ∈ F : g(c) ≤ g_min + α · (g_max − g_min) }
```

| α      | Effect                                              |
| ------ | --------------------------------------------------- |
| 0      | Pure greedy (only the best candidates in the RCL)   |
| 1      | Uniform random (every feasible candidate in the RCL)|
| 0.1–0.3| Typical "semi-greedy" working range                  |

The book uses the same formula and explicitly states "α = 0 corresponds
to a pure greedy algorithm... α = 1 leads to a completely random
algorithm" (Fig. 3.18 caption).

---

## 3. Top-level GRASP

```
 1: function GRASP(instance, MaxIter, α):
 2:     bestSol ← None
 3:     for k = 1 to MaxIter:
 4:         sol ← Construct(instance, α)        # phase 1
 5:         sol ← LocalSearch(instance, sol)    # phase 2
 6:         if sol better than bestSol:
 7:             bestSol ← sol
 8:     return bestSol
```

| Line | What it does                                                                    |
| ---- | ------------------------------------------------------------------------------- |
| 2    | Track the incumbent across restarts — that's the multistart idea.               |
| 3    | Each iteration is independent. (GRASP is embarrassingly parallel.)              |
| 4    | Build a *fresh* solution from scratch — different randomness, different basin.  |
| 5    | Polish to a local optimum.                                                      |
| 6–7  | Standard "remember the best".                                                   |

This corresponds to `grasp(...)` at
[src/fjsp/solver.py:216](src/fjsp/solver.py:216).

---

## 4. Phase 1: greedy randomized construction

When you specialize GRASP to a problem, you answer **four** design
questions:

| Q | What does GRASP need? | Choice for our FJSP                                                                |
| - | --------------------- | ---------------------------------------------------------------------------------- |
| 1 | The candidate set     | Triples `(op, machine, operator)` where op is *ready* (its predecessor is done)    |
| 2 | A greedy function `g` | `earliest completion time` of the candidate, accounting for setup + windows       |
| 3 | The RCL rule          | `g(c) ≤ g_min + α(g_max − g_min)` (Resende & Ribeiro 2016, ch. 3)                  |
| 4 | How to advance state  | Fix `(op*, m*, o*, start*, end*)`, update machine/operator/job clocks, re-iterate |

The "ready set" is what makes this *adaptive* in the GRASP sense: each
time you commit to a candidate, the set of feasible next candidates
changes.

### 4.1 Computing `g(op, m, o)` — the earliest completion time

This is the only place where the three new constraints enter, so it
deserves a careful look. Given current state, scheduling op on
machine m with operator o needs:

1. **Earliest "wishful" start**:
   `t0 = max(machine_end[m], operator_end[o], job_ready[op.job])`.
2. **Setup duration**:
   `s = setup(m, machine_last_product[m], op.product)`.
3. **Block duration** (setup + processing):
   `block = s + p(op, m)`.
4. **Earliest *feasible* start**: smallest `t ≥ t0` such that
   `[t, t + block]` lies entirely inside one machine availability
   window **and** one operator availability window. (If no such `t`
   exists in any window pair, this candidate is infeasible.)
5. **Completion time**: `g(op, m, o) = t + block`.

Step 4 is implemented by `_earliest_feasible_start(...)` at
[src/fjsp/solver.py:49](src/fjsp/solver.py:49) — it iterates over pairs
of (machine window, operator window) and keeps the smallest start time
that fits.

### 4.2 Construction pseudocode

```
 1: function Construct(instance, α):
 2:     machine_end[m] ← 0 for each machine m
 3:     machine_last_product[m] ← ⊥ for each m
 4:     operator_end[o] ← 0 for each operator o
 5:     job_ready[j] ← 0 for each job j
 6:     S ← empty schedule
 7:     while some job has un-scheduled operations:
 8:         C ← []
 9:         for each ready operation op:
10:             for each machine m in op.machine_options:
11:                 setup ← s(m, machine_last_product[m], op.product)
12:                 block ← setup + p(op, m)
13:                 for each operator o in op.operator_options:
14:                     t0 ← max(machine_end[m], operator_end[o], job_ready[op.job])
15:                     start ← earliest_feasible(t0, block, m_windows[m], o_windows[o])
16:                     if start exists:
17:                         end ← start + block
18:                         C.append( (op, m, o, start, setup, end) )
19:         g_min ← min(c.end for c in C)
20:         g_max ← max(c.end for c in C)
21:         threshold ← g_min + α · (g_max − g_min)
22:         RCL ← [c for c in C if c.end ≤ threshold]
23:         (op, m, o, start, setup, end) ← random_choice(RCL)
24:         append (op, m, o, start, setup, end) to S
25:         machine_end[m] ← end
26:         machine_last_product[m] ← op.product
27:         operator_end[o] ← end
28:         job_ready[op.job] ← end
29:     return S
```

| Line  | Meaning                                                                                                                |
| ----- | ---------------------------------------------------------------------------------------------------------------------- |
| 2–5   | Four state vectors: when each *machine* is free, what *product* it last ran, when each *operator* is free, when each *job's* prefix has finished. |
| 9     | "Ready" operations are the next un-scheduled op of each job (precedence within the job is enforced by `job_ready`).    |
| 11    | Setup depends on the last product seen on **this** machine — that's the SDST extension.                                |
| 14    | All three resources block start: machine, operator, and the job's previous op.                                         |
| 15    | The availability extension lives entirely in this call — see §4.1.                                                     |
| 19–22 | RCL formula straight from Resende & Ribeiro (2016, p. 60).                                                              |
| 23    | The only random step in the construction.                                                                              |
| 25–28 | Advance state. The "adaptive" property: future RCLs depend on what we just chose.                                      |

This corresponds to `construct(...)` at
[src/fjsp/solver.py:168](src/fjsp/solver.py:168). Note that lines 2–5
of the pseudocode are not literally `0` everywhere — they come from
[`_initial_state`](src/fjsp/solver.py:111), which seeds the clocks from
the instance's `OrderStatus`: machines and operators that are tied up
on a `running` op are pinned busy until that op's expected end, and
each machine's `current_product_id` is propagated into
`machine_last_product` so the first newly-scheduled op pays the right
setup. See §5.5.

### 4.3 One-step trace on the toy instance, α = 0.3

Initially `machine_end = [0, 0]`, `operator_end = [0, 0]`,
`job_ready = [0, 0]`, all `machine_last_product = ⊥`. Ready ops:
`{O(0,0), O(1,0)}`.

Enumerate every (op, m, o) candidate. Setup is 0 for everyone (no
machine has run anything yet). I'll list end times:

| Candidate                  | block (setup + proc) | window check                | start | end |
| -------------------------- | -------------------- | --------------------------- | ----- | --- |
| O(0,0), M0, Op0            | 0 + 3 = 3            | M0 ok, Op0 [0,4] fits       | 0     | 3   |
| O(0,0), M0, Op1            | 0 + 3 = 3            | M0 ok, Op1 [0,5] fits       | 0     | 3   |
| O(0,0), M1, Op0            | 0 + 2 = 2            | M1 [0,3] fits, Op0 ok       | 0     | **2** |
| O(0,0), M1, Op1            | 0 + 2 = 2            | both ok                     | 0     | **2** |
| O(1,0), M0, Op0            | 0 + 4 = 4            | M0 ok, Op0 [0,4] *just* fits | 0     | 4   |
| O(1,0), M0, Op1            | 0 + 4 = 4            | both ok                     | 0     | 4   |
| O(1,0), M1, Op0            | 0 + 3 = 3            | M1 [0,3] fits                | 0     | 3   |
| O(1,0), M1, Op1            | 0 + 3 = 3            | both ok                     | 0     | 3   |

`g_min = 2`, `g_max = 4`, threshold = `2 + 0.3 × (4 − 2) = 2.6`.
RCL = `{O(0,0)/M1/Op0, O(0,0)/M1/Op1}`. Pick one uniformly, say
`O(0,0)/M1/Op1` → start 0, end 2.

State update: `machine_end[1] = 2`, `machine_last_product[1] = P0`,
`operator_end[1] = 2`, `job_ready[0] = 2`.

The next iteration recomputes the candidate set — *now* M1 is busy, the
last product on M1 is P0, etc. Different candidates, different RCL,
new random pick. After ~4 iterations the schedule is complete.

---

## 5. Phase 2: local search

Once construction returns a feasible schedule, local search improves
it. We use **first-improvement** on two natural FJSP neighborhoods:

- **`N_M` — machine reassignment**: pick one scheduled op, try every
  *other* eligible machine. Keep the same operation order; recompute
  start/end times.
- **`N_O` — operator reassignment**: same idea, but change the
  operator instead of the machine.

```
 1: function LocalSearch(instance, S):
 2:     repeat:
 3:         for each scheduled op (j, k):
 4:             for each alternative machine m' ≠ current(op):
 5:                 S' ← simulate(sequence(S), assign with op.machine = m')
 6:                 if S' feasible and Cmax(S') < Cmax(S):
 7:                     S ← S';  go back to line 2
 8:         for each scheduled op (j, k):
 9:             for each alternative operator o' ≠ current(op):
10:                 S' ← simulate(sequence(S), assign with op.operator = o')
11:                 if S' feasible and Cmax(S') < Cmax(S):
12:                     S ← S';  go back to line 2
13:     until no improvement found
14:     return S
```

The key invariant: **the operation order is held fixed during local
search**. Only the machine or operator assignment of one op changes at
a time; everything else is recomputed by replaying that order
(`simulate(...)` at [src/fjsp/solver.py:233](src/fjsp/solver.py:233)).
This makes each move cheap: O(|ops|) per evaluation.

When `N_M` switches an op to a machine the current operator can't run,
the local search picks any eligible operator for that machine on the
fly; otherwise the move would be invalid by construction.

This corresponds to `local_search(...)` at
[src/fjsp/solver.py:278](src/fjsp/solver.py:278).

### 5.5 Real-time status: per-stage state

State is tracked **per stage**, not per order. Each `Order.status`
([OrderStatus](src/fjsp/input/domain.py)) carries two lists:

```python
@dataclass
class OrderStatus:
    completed: list[StageHistory]   # already finished
    running:   list[StageHistory]   # currently in progress
    # pending = derived = all_stages − completed − running
```

A `StageHistory` is `(stage_idx, machine_id, operator_id, start, end,
setup_duration)`. For completed entries `end` is the actual finish time
(typically ≤ 0 in solver-clock terms — the past). For running entries
`end` is the *expected* finish time (typically ≥ 0).

How [`_initial_state`](src/fjsp/solver.py) seeds the solver clocks:

| For each…           | Effect on the solver                                                                                                                               |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| **completed** stage | Doesn't pin anything. *Updates* `machine_last_product[m]` if it's the most recently ended completed/running stage on that machine — so the first newly-scheduled op on `m` pays the right setup. |
| **running** stage   | Pins `machine_end[m] = h.end`, `operator_end[o] = h.end`, propagates `machine_last_product[m] = order.product_id`, advances `job_ready[j] = h.end`. |
| `next_op_idx[j]`    | Smallest stage index *not* in completed ∪ running. (For FJSP, completed and running form a prefix.)                                                |

`Machine.current_product_id` is the analogous field at the *machine*
level — what was on the machine before any order's history applies (e.g.,
a machine that finished a now-completed job). The seed is:

```python
machine_last_product = [m.current_product_id for m in instance.machines]
# then, in time order, completed/running stages overwrite their machine's slot
```

#### Visualization across all three states

The solver itself only outputs **pending** ops (its decisions). For
display, [`combined_ops(instance, sched)`](src/fjsp/solver.py)
merges the OrderStatus history with the solver's output into a single
list, each `ScheduledOp` carrying a `state` field
(`"completed"` / `"running"` / `"pending"`). Both the matplotlib Gantt
and the React viewer consume this combined list, so completed and
running stages are always visible — with distinct visual styles
(dashed green border, thick blue border, and solid black respectively).
The chart's time axis extends into negative territory automatically if
any completed stage started before t = 0, with a "now" marker at t = 0.

[`total_makespan(instance, sched)`](src/fjsp/solver.py) is the final
`Cmax` across **all** ops including running — the figure the CLI prints.

> The Resende & Ribeiro book also discusses *best-improvement* and
> Variable Neighborhood Descent (VND); first-improvement is the
> simplest correct choice and is what Cartes & Medina (2016) use.
> A natural next step is to add a third neighborhood: swapping two
> adjacent operations on the same machine on the *critical path*
> (Nowicki & Smutnicki 1996).

---

## 6. Code map

```
fjsp/
├── docs/                            # the literature, kept for reference
│   ├── Optimization by GRASP_*.pdf  # Resende & Ribeiro 2016 — canonical GRASP
│   ├── 1-s2.0-S1568494621000740-main.pdf  # Cildoz et al. 2021 — GRASP for ER scheduling
│   └── cartes2016.pdf               # Cartes & Medina 2016 — GRASP for surgery scheduling
├── pyproject.toml                   # uv-managed
├── instances/                       # one subfolder per instance
│   ├── README.md                    # JSON schema + folder convention
│   ├── toy/instance.json            # the canonical toy
│   ├── toy-running/instance.json    # toy + per-stage status example
│   └── small-1/                     # generated example
│       ├── instance.json
│       └── problem_config.yaml
├── src/fjsp/
│   ├── input/                       # data layer
│   │   ├── domain.py                # Stage, Product, Machine, Operator,
│   │   │                            # Order, OrderStatus, Instance
│   │   ├── io.py                    # load_instance, save_instance, validate
│   │   ├── config.py                # ProblemConfig + YAML loader
│   │   └── generator.py             # toy_instance, random_instance
│   ├── solver.py                    # construct, local_search, simulate,
│   │                                # grasp, OperationView, _initial_state
│   ├── output/                      # output layer
│   │   ├── gantt.py                 # plot_gantt (matplotlib)
│   │   └── web_export.py            # export_web_data — writes web/data.js
│   ├── cli.py                       # click CLI: solve, generate, inspect
│   └── __init__.py                  # public API + `uv run fjsp` entry
└── web/
    ├── index.html                   # React viewer (CDN, no build step)
    └── data.js                      # generated by `uv run fjsp`
```

### API at a glance

```python
from fjsp import (
    toy_instance, random_instance, load_instance, save_instance,
    grasp, plot_gantt, export_web_data,
)

inst  = load_instance("instances/toy/instance.json")    # or toy_instance()
sched = grasp(inst, max_iter=200, alpha=0.3, seed=0)
plot_gantt(sched, inst, save_path="gantt.png")
export_web_data(inst, sched, "web/data.js")
```

Where things live in [solver.py](src/fjsp/solver.py):

| GRASP concept                                | Code                                          |
| -------------------------------------------- | --------------------------------------------- |
| Top-level multistart loop                    | `grasp` (line 343)                            |
| Semi-greedy construction (RCL)               | `construct` (line 168)                        |
| `RCL = { c : g(c) ≤ g_min + α(g_max-g_min)}` | line 217                                      |
| Earliest feasible start under windows        | `_earliest_feasible_start` (line 73)          |
| Operator–machine eligibility lookup          | `_eligible_operators` (line 95)               |
| Initial state from `OrderStatus`             | `_initial_state` (line 111)                   |
| Schedule replay (used by local search)       | `simulate` (line 233)                         |
| Local search on N_M and N_O                  | `local_search` (line 278)                     |

---

## 7. Run it

The project is managed with **uv** and the CLI is a click app.

```bash
uv sync                                              # install dependencies
uv run fjsp solve -i instances/toy/instance.json     # solve a saved instance
uv run fjsp generate \
    -c instances/small-1/problem_config.yaml \
    --seed 42 --out-dir instances/my-instance        # writes both instance.json
                                                     # and problem_config.yaml
uv run fjsp inspect instances/small-1/instance.json  # print a summary
uv run fjsp                                          # shortcut for `solve -i instances/toy/instance.json`
```

Three subcommands today (`fjsp --help` lists them):

| Subcommand    | What it does                                                         |
| ------------- | -------------------------------------------------------------------- |
| `solve`       | Read an instance JSON, run GRASP, save Gantt + React data            |
| `generate`    | Build a parametric synthetic instance and write it as JSON           |
| `inspect`     | Print a human-readable summary of an instance                        |

Sample output on the toy with `seed=0, α=0.3, max_iter=200`:

```
Loaded instance 'toy' from instances/toy/instance.json
  products=2  machines=4  operators=2  orders=2
Cmax = 11
  op             mach  op#   setup  proc_start  end
  O(0,0)[P0]     M1    Op1   0      0           2
  O(0,1)[P0]     M2    Op1   0      2           4
  O(1,0)[P1]     M0    Op0   0      0           4
  O(1,1)[P1]     M2    Op1   1      8           11
```

Reading the schedule (stage 0 ops live on M0/M1, stage 1 ops on M2/M3 —
the `per_stage` partition is respected):

- `O(0,0)` (P0 stage 0) runs on **M1**/Op1, `[0, 2]`. Block fits inside
  M1's first window `[0, 3)`. M1 last product = P0.
- `O(0,1)` (P0 stage 1) runs on **M2**/Op1, `[2, 4]`. P0→P0 setup = 0;
  M2 always available. M2 last product = P0.
- `O(1,0)` (P1 stage 0) runs on **M0**/Op0, `[0, 4]`. Op0's first shift
  `[0, 4)` just fits.
- `O(1,1)` (P1 stage 1) runs on **M2**/Op1. M2 was free at 4, but Op1's
  first shift `[0, 5)` only has one unit left and the block needs 4
  (P0→P1 setup 1 + processing 3). The op waits for Op1's next shift at
  `t = 7`: setup `[7, 8]`, processing `[8, 11]`.

Cmax = 11.

The Gantt chart (`gantt.png`) shows machine and operator timelines on
separate rows. Setup blocks appear as faded segments before the
processing block; gray hatched bars mark unavailability windows.

### 7.1 Interactive viewer

For exploring the schedule, open [web/index.html](web/index.html) in
any modern browser. It is a single-file React app loaded via CDN
(React 18 + Babel standalone) — no `npm`, no build step. It reads
`web/data.js` (generated by `uv run fjsp`).

Features:

- **Reactive search.** Type `J0`, `M1`, `Op0`, `P1`, `O(1,0)`, etc.
  Matching ops stay highlighted; non-matching ones dim. Useful for
  spotting "all ops of the same job" at a glance.
- **Filters.** Per-job / per-machine / per-operator / per-product
  checkboxes. Hidden ops are removed from the chart entirely (vs.
  search, which only dims).
- **Toggleable layers.**
    - *Setup* — show/hide the faded setup prefixes.
    - *Unavailability* — show/hide the gray hatched bands on machine
      and operator rows.
    - *Operators* — show/hide the operator rows.
- **Rich tooltips.** Hovering an op block (on either the machine row
  or the operator row) shows: parent job, op index, product, machine,
  operator, setup window, processing window, and total block.
- **Live `Cmax`** in the header; live `matched/total` ops counter in
  the toolbar.

The viewer talks only to local state — no server, no websocket. To
re-render after changing the instance or solver settings, re-run
`uv run fjsp` and refresh the page.

---

## 8. Where to take it next

In rough order of effort vs. payoff:

1. **Reactive GRASP** (Prais & Ribeiro 2000; Resende & Ribeiro 2016
   ch. 7): instead of fixing α, draw it from a discrete distribution
   that you *update* based on the quality of the solutions each α
   produced. Removes the need to tune α.
2. **More neighborhoods.** Add an *adjacent-swap on the critical path*
   move — operations not on the critical path can never improve `C_max`
   when swapped, so restricting to the critical path is both standard
   and cheap (Nowicki & Smutnicki 1996).
3. **Path-relinking** (Resende & Ribeiro 2016 ch. 8–9): keep an elite
   pool of best solutions and, after each GRASP iteration, "relink"
   the new local optimum to a randomly chosen elite. Reliable quality
   boost, modest implementation cost.
4. **Real instances.** Add a parser for the Brandimarte (`Mk01–Mk10`)
   benchmark instances from the FJSP literature, then re-time.

---

## 9. References

All three are in [docs/](docs/):

- **Resende, M.G.C. & Ribeiro, C.C. (2016).** *Optimization by GRASP:
  Greedy Randomized Adaptive Search Procedures.* Springer.
  Canonical reference; the RCL formula and pseudocode in this README
  follow ch. 3 (semi-greedy) and ch. 5 (basic GRASP).
- **Cartes, I. & Medina, R. (2016).** *A GRASP Algorithm for the
  Elective Surgeries Scheduling Problem in a Chilean Public Hospital.*
  IEEE Latin America Transactions, 14(5), pp. 2333–2338.
  Same constraint structure as our extended FJSP: room availability,
  surgeon/nurse/anesthetist availability, compatibility constraints.
- **Cildoz, M., Mallor, F. & Mateo, P.M. (2021).** *A GRASP-based
  algorithm for solving the emergency room physician scheduling
  problem.* Applied Soft Computing, 103, 107151.
  GRASP applied to a heavily-constrained personnel-availability
  scheduling problem — a useful contrast to a manufacturing FJSP.
