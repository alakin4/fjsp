window.SCHEDULE_DATA = {
  "n_machines": 2,
  "n_operators": 2,
  "n_products": 2,
  "horizon": 13,
  "machine_windows": [
    [
      [
        0,
        10000
      ]
    ],
    [
      [
        0,
        3
      ],
      [
        5,
        10000
      ]
    ]
  ],
  "operator_windows": [
    [
      [
        0,
        4
      ],
      [
        7,
        10000
      ]
    ],
    [
      [
        0,
        5
      ],
      [
        7,
        10000
      ]
    ]
  ],
  "schedule": {
    "makespan": 11,
    "ops": [
      {
        "job_id": 0,
        "op_idx": 0,
        "product_id": 0,
        "machine": 0,
        "operator": 1,
        "start": 0,
        "setup_duration": 0,
        "proc_start": 0,
        "end": 3
      },
      {
        "job_id": 0,
        "op_idx": 1,
        "product_id": 0,
        "machine": 0,
        "operator": 1,
        "start": 3,
        "setup_duration": 0,
        "proc_start": 3,
        "end": 5
      },
      {
        "job_id": 1,
        "op_idx": 0,
        "product_id": 1,
        "machine": 1,
        "operator": 0,
        "start": 0,
        "setup_duration": 0,
        "proc_start": 0,
        "end": 3
      },
      {
        "job_id": 1,
        "op_idx": 1,
        "product_id": 1,
        "machine": 0,
        "operator": 1,
        "start": 7,
        "setup_duration": 1,
        "proc_start": 8,
        "end": 11
      }
    ]
  }
};
