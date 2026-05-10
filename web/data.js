window.SCHEDULE_DATA = {
  "name": "small-1",
  "n_machines": 4,
  "n_operators": 3,
  "n_products": 4,
  "time_min": 0,
  "horizon": 50,
  "machines": [
    {
      "id": 0,
      "name": "M0"
    },
    {
      "id": 1,
      "name": "M1"
    },
    {
      "id": 2,
      "name": "M2"
    },
    {
      "id": 3,
      "name": "M3"
    }
  ],
  "operators": [
    {
      "id": 0,
      "name": "Op0"
    },
    {
      "id": 1,
      "name": "Op1"
    },
    {
      "id": 2,
      "name": "Op2"
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
    },
    {
      "id": 2,
      "name": "P2"
    },
    {
      "id": 3,
      "name": "P3"
    }
  ],
  "machine_windows": [
    [
      [
        0,
        34
      ],
      [
        40,
        63
      ],
      [
        68,
        90
      ],
      [
        96,
        125
      ],
      [
        133,
        173
      ],
      [
        179,
        200
      ]
    ],
    [
      [
        0,
        32
      ],
      [
        36,
        70
      ],
      [
        77,
        123
      ],
      [
        127,
        152
      ],
      [
        156,
        187
      ],
      [
        190,
        200
      ]
    ],
    [
      [
        0,
        42
      ],
      [
        49,
        89
      ],
      [
        91,
        130
      ],
      [
        137,
        162
      ],
      [
        168,
        200
      ]
    ],
    [
      [
        0,
        46
      ],
      [
        48,
        93
      ],
      [
        97,
        129
      ],
      [
        133,
        155
      ],
      [
        158,
        200
      ]
    ]
  ],
  "operator_windows": [
    [
      [
        0,
        54
      ],
      [
        64,
        105
      ],
      [
        115,
        155
      ],
      [
        171,
        200
      ]
    ],
    [
      [
        0,
        33
      ],
      [
        49,
        105
      ],
      [
        114,
        142
      ],
      [
        151,
        185
      ],
      [
        195,
        200
      ]
    ],
    [
      [
        0,
        60
      ],
      [
        68,
        100
      ],
      [
        116,
        158
      ],
      [
        171,
        200
      ]
    ]
  ],
  "orders": [
    {
      "job_id": 0,
      "product_id": 3,
      "deadline": 13,
      "completed_stages": [],
      "running_stages": []
    },
    {
      "job_id": 1,
      "product_id": 0,
      "deadline": 64,
      "completed_stages": [],
      "running_stages": []
    },
    {
      "job_id": 2,
      "product_id": 2,
      "deadline": 37,
      "completed_stages": [],
      "running_stages": []
    },
    {
      "job_id": 3,
      "product_id": 1,
      "deadline": 41,
      "completed_stages": [],
      "running_stages": []
    },
    {
      "job_id": 4,
      "product_id": 0,
      "deadline": 73,
      "completed_stages": [],
      "running_stages": []
    },
    {
      "job_id": 5,
      "product_id": 2,
      "deadline": 47,
      "completed_stages": [],
      "running_stages": []
    },
    {
      "job_id": 6,
      "product_id": 1,
      "deadline": 46,
      "completed_stages": [],
      "running_stages": []
    },
    {
      "job_id": 7,
      "product_id": 1,
      "deadline": 58,
      "completed_stages": [],
      "running_stages": []
    }
  ],
  "schedule": {
    "makespan": 48,
    "solver_makespan": 48,
    "ops": [
      {
        "job_id": 0,
        "op_idx": 0,
        "product_id": 3,
        "machine": 3,
        "operator": 0,
        "start": 0,
        "setup_duration": 0,
        "proc_start": 0,
        "end": 2,
        "state": "pending"
      },
      {
        "job_id": 0,
        "op_idx": 1,
        "product_id": 3,
        "machine": 2,
        "operator": 0,
        "start": 2,
        "setup_duration": 0,
        "proc_start": 2,
        "end": 6,
        "state": "pending"
      },
      {
        "job_id": 1,
        "op_idx": 0,
        "product_id": 0,
        "machine": 0,
        "operator": 2,
        "start": 0,
        "setup_duration": 0,
        "proc_start": 0,
        "end": 7,
        "state": "pending"
      },
      {
        "job_id": 7,
        "op_idx": 0,
        "product_id": 1,
        "machine": 3,
        "operator": 1,
        "start": 2,
        "setup_duration": 0,
        "proc_start": 2,
        "end": 9,
        "state": "pending"
      },
      {
        "job_id": 1,
        "op_idx": 1,
        "product_id": 0,
        "machine": 1,
        "operator": 2,
        "start": 7,
        "setup_duration": 0,
        "proc_start": 7,
        "end": 10,
        "state": "pending"
      },
      {
        "job_id": 2,
        "op_idx": 0,
        "product_id": 2,
        "machine": 3,
        "operator": 1,
        "start": 9,
        "setup_duration": 0,
        "proc_start": 9,
        "end": 13,
        "state": "pending"
      },
      {
        "job_id": 6,
        "op_idx": 0,
        "product_id": 1,
        "machine": 2,
        "operator": 0,
        "start": 6,
        "setup_duration": 1,
        "proc_start": 7,
        "end": 14,
        "state": "pending"
      },
      {
        "job_id": 5,
        "op_idx": 0,
        "product_id": 2,
        "machine": 3,
        "operator": 0,
        "start": 14,
        "setup_duration": 0,
        "proc_start": 14,
        "end": 18,
        "state": "pending"
      },
      {
        "job_id": 7,
        "op_idx": 1,
        "product_id": 1,
        "machine": 0,
        "operator": 2,
        "start": 10,
        "setup_duration": 2,
        "proc_start": 12,
        "end": 16,
        "state": "pending"
      },
      {
        "job_id": 2,
        "op_idx": 1,
        "product_id": 2,
        "machine": 1,
        "operator": 1,
        "start": 13,
        "setup_duration": 0,
        "proc_start": 13,
        "end": 21,
        "state": "pending"
      },
      {
        "job_id": 6,
        "op_idx": 1,
        "product_id": 1,
        "machine": 3,
        "operator": 0,
        "start": 18,
        "setup_duration": 0,
        "proc_start": 18,
        "end": 24,
        "state": "pending"
      },
      {
        "job_id": 3,
        "op_idx": 0,
        "product_id": 1,
        "machine": 2,
        "operator": 0,
        "start": 24,
        "setup_duration": 0,
        "proc_start": 24,
        "end": 31,
        "state": "pending"
      },
      {
        "job_id": 3,
        "op_idx": 1,
        "product_id": 1,
        "machine": 3,
        "operator": 0,
        "start": 31,
        "setup_duration": 0,
        "proc_start": 31,
        "end": 37,
        "state": "pending"
      },
      {
        "job_id": 5,
        "op_idx": 1,
        "product_id": 2,
        "machine": 1,
        "operator": 1,
        "start": 21,
        "setup_duration": 0,
        "proc_start": 21,
        "end": 29,
        "state": "pending"
      },
      {
        "job_id": 1,
        "op_idx": 2,
        "product_id": 0,
        "machine": 0,
        "operator": 2,
        "start": 16,
        "setup_duration": 3,
        "proc_start": 19,
        "end": 25,
        "state": "pending"
      },
      {
        "job_id": 1,
        "op_idx": 3,
        "product_id": 0,
        "machine": 0,
        "operator": 2,
        "start": 25,
        "setup_duration": 0,
        "proc_start": 25,
        "end": 27,
        "state": "pending"
      },
      {
        "job_id": 4,
        "op_idx": 0,
        "product_id": 0,
        "machine": 0,
        "operator": 2,
        "start": 27,
        "setup_duration": 0,
        "proc_start": 27,
        "end": 34,
        "state": "pending"
      },
      {
        "job_id": 4,
        "op_idx": 1,
        "product_id": 0,
        "machine": 1,
        "operator": 2,
        "start": 36,
        "setup_duration": 0,
        "proc_start": 36,
        "end": 39,
        "state": "pending"
      },
      {
        "job_id": 4,
        "op_idx": 2,
        "product_id": 0,
        "machine": 0,
        "operator": 2,
        "start": 40,
        "setup_duration": 0,
        "proc_start": 40,
        "end": 46,
        "state": "pending"
      },
      {
        "job_id": 4,
        "op_idx": 3,
        "product_id": 0,
        "machine": 0,
        "operator": 2,
        "start": 46,
        "setup_duration": 0,
        "proc_start": 46,
        "end": 48,
        "state": "pending"
      }
    ]
  }
};
