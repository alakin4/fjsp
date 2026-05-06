# Building a GRASP solver for the Flexible Job-Shop Problem

A small, readable Python implementation of **GRASP** (Greedy Randomized
Adaptive Search Procedure) for an **extended Flexible Job-Shop Problem**
(FJSP). The extensions — machine availability, operator availability, and
product-dependent setup times — are the kind of constraints that make
real shop-floor problems harder than the textbook FJSP.

The code is organized into three components:

| Component                | File                                                       | Role                                          |
| ------------------------ | ---------------------------------------------------------- | --------------------------------------------- |
| Data                     | [src/fjsp/data.py](src/fjsp/data.py)                       | Instance representation + the toy example     |
| Solver                   | [src/fjsp/solver.py](src/fjsp/solver.py)                   | GRASP: construction + local search            |
| Visualization (static)   | [src/fjsp/visualization.py](src/fjsp/visualization.py)     | Matplotlib Gantt with availability + setups   |
| Visualization (interactive) | [web/index.html](web/index.html) + [src/fjsp/export.py](src/fjsp/export.py) | React-based Gantt with search, filters, tooltips |

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

### 1.2 Three real-world extensions

The classical FJSP assumes machines and operators are always available
and that switching jobs is free. None of those is true on a real shop
floor, so we add:

1. **Machine availability windows.** Each machine `m` has a list of
   intervals `[a, b]` during which it is usable (e.g. excluded:
   maintenance, planned downtime). An operation can be processed on
   `m` only if its entire processing block fits inside *one* such
   window.

2. **Operator availability windows.** Each operation also requires an
   operator drawn from an eligible subset. Each operator has its own
   availability windows (e.g. shift, breaks). The op's block must fit
   inside one machine window **and** one operator window
   simultaneously.

3. **Product-dependent setup times** (also called *sequence-dependent
   setup times*, SDST). When a machine `m` switches from a job
   producing product `p1` to one producing `p2`, it incurs a setup
   `s(m, p1, p2)` *before* processing starts. The first job on a
   machine has no predecessor; we treat that as `s(m, ⊥, p) = 0`.

These three constraints are exactly the family of conditions that
Cartes & Medina (2016) handles for surgery scheduling (rooms = machines,
surgeons/nurses = operators, surgical-team compatibility ≈ setups).

### 1.3 Toy instance

The instance built by `toy_instance()` in [src/fjsp/data.py](src/fjsp/data.py)
has 2 jobs, 2 machines, 2 operators, 2 products:

| Operation | Product | M0 (proc) | M1 (proc) | Eligible operators |
| --------- | ------- | --------- | --------- | ------------------ |
| O(0,0)    | P0      | 3         | 2         | Op0, Op1           |
| O(0,1)    | P0      | 2         | 4         | Op0, Op1           |
| O(1,0)    | P1      | 4         | 3         | Op0, Op1           |
| O(1,1)    | P1      | 3         | 5         | Op0, Op1           |

Availability:

- **M0**: always available.
- **M1**: available `[0, 3)` ∪ `[5, ∞)` — maintenance closes M1 in
  `[3, 5)`.
- **Op0**: available `[0, 4)` ∪ `[6, ∞)` — lunch break in `[4, 6)`.
- **Op1**: always available.

Setup matrix `s(prev, curr)` (same on both machines):

|              | curr = P0 | curr = P1 |
| ------------ | --------- | --------- |
| prev = ⊥     | 0         | 0         |
| prev = P0    | 0         | 1         |
| prev = P1    | 2         | 0         |

So switching from P0 to P1 costs 1 unit of setup; switching from P1 to
P0 costs 2; staying on the same product costs 0; the first op on a
machine is free.

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
[src/fjsp/solver.py:73](src/fjsp/solver.py:73).

### 4.3 One-step trace on the toy instance, α = 0.3

Initially `machine_end = [0, 0]`, `operator_end = [0, 0]`,
`job_ready = [0, 0]`, all `machine_last_product = ⊥`. Ready ops:
`{O(0,0), O(1,0)}`.

Enumerate every (op, m, o) candidate. Setup is 0 for everyone (no
machine has run anything yet). I'll list end times:

| Candidate                  | block (setup + proc) | window check                | start | end |
| -------------------------- | -------------------- | --------------------------- | ----- | --- |
| O(0,0), M0, Op0            | 0 + 3 = 3            | M0 ok, Op0 [0,4] fits       | 0     | 3   |
| O(0,0), M0, Op1            | 0 + 3 = 3            | both ok                     | 0     | 3   |
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
(`simulate(...)` at [src/fjsp/solver.py:125](src/fjsp/solver.py:125)).
This makes each move cheap: O(|ops|) per evaluation.

This corresponds to `local_search(...)` at
[src/fjsp/solver.py:164](src/fjsp/solver.py:164).

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
├── src/fjsp/
│   ├── data.py                      # Operation, FJSPInstance, toy_instance()
│   ├── solver.py                    # construct, local_search, simulate, grasp
│   ├── visualization.py             # plot_gantt (matplotlib)
│   ├── export.py                    # export_web_data — writes web/data.js
│   └── __init__.py                  # exports + `uv run fjsp` entry point
└── web/
    ├── index.html                   # React viewer (loaded via CDN, no build step)
    └── data.js                      # generated by `uv run fjsp`
```

### API at a glance

```python
from fjsp import toy_instance, grasp, plot_gantt

inst  = toy_instance()
sched = grasp(inst, max_iter=200, alpha=0.3, seed=0)
plot_gantt(sched, inst, save_path="gantt.png")
```

Where things live in [solver.py](src/fjsp/solver.py):

| GRASP concept                           | Code                                   |
| --------------------------------------- | -------------------------------------- |
| Top-level multistart loop               | `grasp` (line 216)                     |
| Semi-greedy construction (RCL)          | `construct` (line 73)                  |
| `RCL = { c : g(c) ≤ g_min + α(g_max-g_min) }` | line 109                          |
| Earliest feasible start under windows   | `_earliest_feasible_start` (line 49)   |
| Schedule replay (used by local search)  | `simulate` (line 125)                  |
| Local search on N_M and N_O             | `local_search` (line 164)              |

---

## 7. Run it

The project is managed with **uv**.

```bash
uv sync                           # install dependencies
uv run fjsp                       # solve the toy instance, save gantt.png
```

Sample output on the toy instance with `seed=0, α=0.3, max_iter=200`:

```
Cmax = 9
op             mach  op#   setup  proc_start  end
O(0,0)[P0]     M0    Op1   0      0           3
O(0,1)[P0]     M0    Op1   0      3           5
O(1,0)[P1]     M1    Op0   0      0           3
O(1,1)[P1]     M0    Op1   1      6           9
```

Reading the schedule:

- `O(0,0)` runs on M0/Op1, [0, 3]. M0 last product = P0.
- `O(0,1)` runs on M0/Op1, [3, 5]. P0→P0, setup 0.
- `O(1,0)` runs on M1/Op0, [0, 3]. Fits inside M1's first window
  `[0, 3)`; Op0 is fine (not yet on lunch break).
- `O(1,1)` runs on M0/Op1, setup [5, 6] (P0→P1 = 1) then processing
  [6, 9]. Note: O(1,1) was *moved* off M1 — although M1 returns at 5,
  M1 has p = 5 for O(1,1) (longer), and a P1→P1 setup of 0 on M1 vs.
  P0→P1 setup of 1 on M0 still nets a worse Cmax. The local search
  finds this.

Cmax = 9.

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
