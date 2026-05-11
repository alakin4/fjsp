window.SCHEDULE_DATA = {
  "name": "toy-running",
  "n_machines": 4,
  "n_operators": 2,
  "n_products": 2,
  "time_min": -4,
  "horizon": 13,
  "machines": [
    {
      "id": 0,
      "name": "M0",
      "stage": 0
    },
    {
      "id": 1,
      "name": "M1",
      "stage": 0
    },
    {
      "id": 2,
      "name": "M2",
      "stage": 1
    },
    {
      "id": 3,
      "name": "M3",
      "stage": 1
    }
  ],
  "stage_machines": [
    [
      0,
      1
    ],
    [
      2,
      3
    ]
  ],
  "machine_stage_mode": "per_stage",
  "operators": [
    {
      "id": 0,
      "name": "Op0"
    },
    {
      "id": 1,
      "name": "Op1"
    }
  ],
  "products": [
    {
      "id": 0,
      "name": "P0"
    },
    {
      "id": 1,
      "name": "P1"
    }
  ],
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
    ],
    [
      [
        0,
        10000
      ]
    ],
    [
      [
        0,
        4
      ],
      [
        6,
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
  "orders": [
    {
      "job_id": 0,
      "product_id": 0,
      "deadline": 12,
      "completed_stages": [],
      "running_stages": []
    },
    {
      "job_id": 1,
      "product_id": 1,
      "deadline": 12,
      "completed_stages": [
        0
      ],
      "running_stages": []
    },
    {
      "job_id": 2,
      "product_id": 1,
      "deadline": 12,
      "completed_stages": [
        0
      ],
      "running_stages": [
        1
      ]
    }
  ],
  "schedule": {
    "makespan": 11,
    "solver_makespan": 11,
    "ops": [
      {
        "job_id": 1,
        "op_idx": 0,
        "product_id": 1,
        "machine": 0,
        "operator": 0,
        "start": -4,
        "setup_duration": 0,
        "proc_start": -4,
        "end": 0,
        "state": "completed"
      },
      {
        "job_id": 2,
        "op_idx": 0,
        "product_id": 1,
        "machine": 1,
        "operator": 1,
        "start": -3,
        "setup_duration": 0,
        "proc_start": -3,
        "end": 0,
        "state": "completed"
      },
      {
        "job_id": 2,
        "op_idx": 1,
        "product_id": 1,
        "machine": 2,
        "operator": 0,
        "start": 0,
        "setup_duration": 0,
        "proc_start": 0,
        "end": 3,
        "state": "running"
      },
      {
        "job_id": 0,
        "op_idx": 0,
        "product_id": 0,
        "machine": 0,
        "operator": 1,
        "start": 0,
        "setup_duration": 2,
        "proc_start": 2,
        "end": 5,
        "state": "pending"
      },
      {
        "job_id": 1,
        "op_idx": 1,
        "product_id": 1,
        "machine": 2,
        "operator": 1,
        "start": 7,
        "setup_duration": 0,
        "proc_start": 7,
        "end": 10,
        "state": "pending"
      },
      {
        "job_id": 0,
        "op_idx": 1,
        "product_id": 0,
        "machine": 3,
        "operator": 0,
        "start": 7,
        "setup_duration": 0,
        "proc_start": 7,
        "end": 11,
        "state": "pending"
      }
    ]
  }
};
