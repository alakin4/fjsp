# FJSP instances

Each instance lives in its **own subfolder** under `instances/`. The
folder bundles the JSON the solver reads and (when applicable) the YAML
config that generated it:

```
instances/
├── toy/
│   └── instance.json              # built by toy_instance() — no yaml
├── toy-running/
│   └── instance.json              # toy_instance() + manual per-stage status
└── small-1/
    ├── instance.json
    └── problem_config.yaml        # the config used to generate it
```

Run any of them with:

```bash
uv run fjsp solve --instance instances/<name>/instance.json
uv run fjsp inspect instances/<name>/instance.json
```

The bare `uv run fjsp` defaults to `instances/toy/instance.json`.

## Bundled examples

| Folder                   | Notes                                                                 |
| ------------------------ | --------------------------------------------------------------------- |
| `instances/toy/`         | 2 products, 4 machines split 2-per-stage across 2 stages (`per_stage` mode), 2 operators. All orders pending. Built by `toy_instance()`. |
| `instances/toy-running/` | Same shop layout, three orders demonstrating per-stage state: **J0** all pending; **J1** stage 0 completed (P1 on M0/Op0 from t = -4 to 0); **J2** stage 0 completed (P1 on M1/Op1 from t = -3 to 0) and stage 1 running (P1 on M2/Op0 from t = 0 to 3). |
| `instances/small-1/`     | Output of `fjsp generate -c instances/small-1/problem_config.yaml -d instances/small-1`. |

## Generating a new instance into the folder convention

Two ways to drop a new instance under `instances/`:

```bash
# 1) recommended — fjsp writes the folder for you (instance.json + problem_config.yaml):
uv run fjsp generate \
    -c instances/small-1/problem_config.yaml \
    --seed 42 \
    --out-dir instances/my-instance

# 2) explicit file path (no config copy):
uv run fjsp generate \
    -c instances/small-1/problem_config.yaml \
    -o instances/my-instance.json
```

`--out-dir` (`-d`) is the convention used by the bundled examples: it
creates the folder if needed, writes `instance.json`, and copies the
`--config` YAML alongside (or dumps the *effective* config as YAML if
none was provided). CLI flags like `--seed`, `--mode`, `--machines`
override individual fields of the loaded config — the saved YAML is the
input config, so if you override fields on the command line, edit the
saved YAML to record what you actually used.

### Stage-machine layout

The `--mode` flag (and `machine_stage_mode` field in YAML) chooses how
machines are distributed across the shop's production stages:

| Mode        | What it means                                                                   |
| ----------- | ------------------------------------------------------------------------------- |
| `per_stage` | Each machine belongs to *exactly one* stage; the lists in `stage_machines` are **disjoint**. Models a true flow shop with stage-specialized machines. |
| `shared`    | A machine may be eligible for *multiple* stages; lists may overlap. Standard FJSP. |

Either way, every product's `Stage.eligible_machines[k]` must be a
subset of `stage_machines[k]` — `validate_instance` (run automatically
on load) refuses an instance that violates this.

## How per-stage state affects scheduling

For each order the solver:

- skips every stage in `status.completed` and `status.running`;
- pins the **machine** and **operator** of each running stage as busy
  until that stage's `end` (the expected finish time);
- propagates the running stage's product onto the machine, so the next
  newly-scheduled op on it pays the correct setup;
- schedules everything else (the *pending* stages — those not in either
  list) starting from t = 0.

In the visualization all three categories are drawn together: completed
stages keep their actual past times, running stages keep their expected
end, and pending stages get whatever times the solver assigns. The chart
extends into negative time automatically if any completed stage starts
before t = 0, with a "now" line at t = 0.

## JSON schema

```jsonc
{
  "name": "string",
  "horizon": 10000,                   // upper time bound for windows

  // 1 entry per product type. Stages are ordered.
  "products": [
    {
      "id": 0,
      "name": "P0",
      "stages": [
        {
          "stage_idx": 0,
          "name": "stage-0",
          // machine_id (string-keyed in JSON) -> processing time
          "eligible_machines": { "0": 3, "1": 2 }
        }
      ]
    }
  ],

  // Shop-level stage layout. Each `stage_machines[k]` lists the
  // machines eligible for stage k. Each product's `Stage.eligible_machines`
  // for index k must be a subset of this list.
  "machine_stage_mode": "per_stage",  // or "shared"
  "stage_machines": [[0, 1], [2, 3]], // null for "no shop-level partition"

  // 1 entry per machine.
  "machines": [
    {
      "id": 0,
      "name": "M0",
      // closed-interval availability windows [a, b]; an op of duration d
      // can be scheduled starting at s only if [s, s+d] fits in ONE window.
      "availability": [[0, 3], [5, 10000]],
      // setup_times[prev_product or "-1"][curr_product] -> duration.
      // Empty object {} means the machine never requires setup.
      "setup_times": {
        "-1": { "0": 0, "1": 0 },
        "0":  { "0": 0, "1": 1 },
        "1":  { "0": 2, "1": 0 }
      },
      // The product currently or most recently processed on this machine.
      // Informs setup for the FIRST newly-scheduled op. null = no history.
      "current_product_id": null
    }
  ],

  // 1 entry per operator.
  "operators": [
    {
      "id": 0,
      "name": "Op0",
      // The subset of machines this operator can run.
      "eligible_machines": [0, 1],
      // Shift availability (closed intervals).
      "shifts": [[0, 4], [7, 10000]]
    }
  ],

  // 1 entry per customer order = job to schedule.
  "orders": [
    {
      "job_id": 0,
      "product_id": 0,
      "deadline": 12,
      "status": {
        // Stages already finished. Each entry is a StageHistory:
        // stage_idx, machine_id, operator_id, start, end, setup_duration.
        // Past times (end <= 0) are typical.
        "completed": [],
        // Stages currently in progress. `end` here is the EXPECTED end.
        // The solver pins (machine, operator) busy until that time.
        "running": []
        // pending = derived = all_stages − completed − running
      }
    }
  ]
}
```
