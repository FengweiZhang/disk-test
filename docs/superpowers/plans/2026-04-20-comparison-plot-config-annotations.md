# Comparison Plot Config Annotations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add visible fio configuration tables to fixed-point and best-result comparison overview images.

**Architecture:** Keep comparison CSV generation unchanged. Add a reusable table-rendering helper in `nvme_test/plot.py`, then call it from the fixed-point and best-point overview plot functions. Update README to document that comparison images embed test configuration metadata.

**Tech Stack:** Python, matplotlib, existing CSV comparison helpers

---

### Task 1: Add reusable figure table helper

**Files:**
- Modify: `nvme_test/plot.py`

- [ ] **Step 1: Verify current helper absence**

Run:

```bash
python3 - <<'PY'
import nvme_test.plot as plot
assert not hasattr(plot, "_add_config_table")
PY
```

Expected: command exits successfully before implementation.

- [ ] **Step 2: Implement `_add_config_table`**

Add a helper that accepts a figure, table rows, and columns. The helper should:

- create a bottom table with `fig.text`/`fig.table` support via an added axes
- use font size `8`
- reserve bottom space by adjusting subplot layout
- return without changing the figure if rows are empty

- [ ] **Step 3: Verify helper exists**

Run:

```bash
python3 - <<'PY'
import nvme_test.plot as plot
assert hasattr(plot, "_add_config_table")
PY
```

Expected: command exits successfully after implementation.

### Task 2: Annotate best and fixed comparison plots

**Files:**
- Modify: `nvme_test/plot.py`

- [ ] **Step 1: Generate pre-change smoke output**

Run a synthetic comparison generation command and inspect that it currently only verifies file existence, not annotations.

- [ ] **Step 2: Update best overview plots**

For each best overview figure, build rows with:

- `workload`
- `target`
- `block_size`
- `numjobs`
- `iodepth`

Pass those rows to `_add_config_table`.

- [ ] **Step 3: Update fixed-point overview plots**

For each fixed-point overview figure, build one row with:

- `name`
- `workload`
- `block_size`
- `numjobs`
- `iodepth`

Pass that row to `_add_config_table`.

- [ ] **Step 4: Verify synthetic output generation**

Run:

```bash
MPLCONFIGDIR=/tmp/mplconfig-nvme-annotations python3 - <<'PY'
from pathlib import Path
from nvme_test.results import write_comparison_outputs
from nvme_test.plot import generate_comparison_plots
import shutil

base = Path("/tmp/nvme-annotation-smoke")
if base.exists():
    shutil.rmtree(base)
base.mkdir(parents=True)

scenario_results = [
    {
        "scenario_id": "per_device/0000_50_00_0",
        "target_id": "0000_50_00_0",
        "target_label": "0000:50:00.0",
        "target_type": "device",
        "csv_rows": [
            {"workload": "read", "block_size": "16K", "numjobs": 4, "iodepth": 64, "bw_MBps": 1000.0, "iops": 60000.0, "lat_avg_us": 80.0, "lat_p50_us": 70.0, "lat_p99_us": 110.0, "lat_max_us": 200.0}
        ],
    },
    {
        "scenario_id": "aggregate",
        "target_id": "aggregate",
        "target_label": "aggregate",
        "target_type": "aggregate",
        "csv_rows": [
            {"workload": "read", "block_size": "16K", "numjobs": 4, "iodepth": 64, "bw_MBps": 1800.0, "iops": 110000.0, "lat_avg_us": 90.0, "lat_p50_us": 75.0, "lat_p99_us": 120.0, "lat_max_us": 210.0}
        ],
    },
]
outputs = write_comparison_outputs(
    scenario_results=scenario_results,
    comparison_dir=base,
    fixed_points=[{"name": "16k_read_hot", "workload": "read", "block_size": "16K", "numjobs": 4, "iodepth": 64}],
    best_points_enabled=True,
)
plots = generate_comparison_plots(
    all_results_csv=outputs["all_results_csv"],
    best_points_csv=outputs["best_points_csv"],
    fixed_points_csv=outputs["fixed_points_csv"],
    plots_dir=base / "plots",
    plot_format="png",
)
expected = {
    "best_bandwidth_overview.png",
    "best_iops_overview.png",
    "best_latency_overview.png",
    "16k_read_hot_overview.png",
}
assert expected == {path.name for path in plots}
print(sorted(path.name for path in plots))
PY
```

Expected: command prints the four expected PNG names.

### Task 3: Update docs and final verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README comparison plot notes**

Document that:

- fixed-point overview plots include `name`, `workload`, `block_size`, `numjobs`, and `iodepth`
- best overview plots include the `workload`, `target`, `block_size`, `numjobs`, and `iodepth` that produced each best value

- [ ] **Step 2: Run compile verification**

Run:

```bash
python3 -m compileall main.py nvme_test
```

Expected: command exits successfully.

- [ ] **Step 3: Run config compatibility verification**

Run:

```bash
python3 -c "from nvme_test.config import load_config; print(load_config('config.json')['execution']['run_aggregate'])"
```

Expected: prints `True`.
