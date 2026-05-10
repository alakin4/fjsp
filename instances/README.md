# FJSP instance files

Each `*.json` file in this folder is a self-contained FJSP instance the
solver can read with `fjsp solve --instance <path>`.

## Schema

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
        // Stages that are already finished. Each entry is a
        // StageHistory: stage_idx, machine_id, operator_id, start, end,
        // setup_duration. Past times (end <= 0) are typical.
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

## Bundled examples

| File                 | Notes                                                               |
| -------------------- | ------------------------------------------------------------------- |
| `toy.json`           | The 2-job / 2-machine / 2-operator instance from the README walk-through. All orders pending. |
| `toy-running.json`   | Three orders demonstrating per-stage state:<br>**J0** — all stages pending.<br>**J1** — stage 0 completed (P1 ran on M0/Op0 from t = -4 to 0); stage 1 pending.<br>**J2** — stage 0 completed (P1 ran on M1/Op1 from t = -3 to 0); stage 1 running on M0/Op0 with expected end at t = 3. |
| `small-1.json`       | Output of `fjsp generate --seed 42 --machines 4 --operators 3 --products 4 --orders 8`. |

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

## Generate instances on the command line

```bash
# write a synthetic 4-product / 5-machine / 4-operator / 10-order instance
uv run fjsp generate \
    --name small-1 \
    --products 4 --machines 5 --operators 4 --orders 10 \
    --horizon 200 --seed 0 \
    -o instances/small-1.json
```

Then solve it:

```bash
uv run fjsp solve --instance instances/small-1.json --max-iter 200 --alpha 0.3 --seed 0
```

`fjsp inspect <path>` prints a human-readable summary of any instance.
