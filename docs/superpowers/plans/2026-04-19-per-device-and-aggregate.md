# Per-Device and Aggregate NVMe Test Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new execution mode that can run per-device fio tests, aggregate fio tests, or both in one run, then generate cross-device comparison CSVs and overview plots.

**Architecture:** Keep the current fio pipeline as the reusable single-scenario executor, then add an orchestration layer that expands one config into multiple scenarios and writes outputs into `aggregate/`, `per_device/`, and `comparison/`. Extend config parsing, device preparation, results aggregation, and plotting only where needed to support scenario metadata and summary outputs.

**Tech Stack:** Python, standard library (`json`, `csv`, `dataclasses`, `datetime`, `pathlib`), matplotlib, existing fio/device shell scripts

---

### Task 1: Extend config parsing and scenario orchestration

**Files:**
- Modify: `main.py`
- Modify: `nvme_test/config.py`
- Modify: `nvme_test/device.py`
- Create: `nvme_test/orchestrator.py`

- [ ] **Step 1: Add `execution` defaults and validation in `nvme_test/config.py`**

Implement optional `execution` parsing with defaults:

```python
DEFAULT_EXECUTION = {
    "run_aggregate": True,
    "run_per_device": False,
    "prepare_mode": "once",
    "comparison_summary": {
        "best_points": False,
        "fixed_points": [],
    },
}
```

Validation must enforce:
- at least one of `run_aggregate` / `run_per_device`
- `prepare_mode in {"once", "per_test"}`
- unique `fixed_points[].name`
- each fixed point value must exist in the configured fio matrix

- [ ] **Step 2: Refactor `nvme_test/device.py` to expose reusable helpers**

Add helpers shaped like:

```python
def prepare_devices(pci_addresses: list[str], format_before_test: bool) -> dict[str, str]:
    ...

def build_aggregate_target(config: dict, device_map: dict[str, str]) -> tuple[str, str | None]:
    ...

def sanitize_pci(pci_addr: str) -> str:
    return pci_addr.replace(":", "_").replace(".", "_")
```

Keep `prepare_device()` and RAID teardown behavior, but stop coupling orchestration to a single returned target string.

- [ ] **Step 3: Create `nvme_test/orchestrator.py` with scenario expansion**

Implement small scenario records and orchestration helpers:

```python
from dataclasses import dataclass
from pathlib import Path

@dataclass
class Scenario:
    scenario_id: str
    target_label: str
    target_type: str
    target_device: str
    output_dir: Path
```

Add functions to:
- expand configured scenarios in per-device-then-aggregate order
- prepare devices once or per test
- execute one scenario through fio/results/plots
- collect scenario status for the final summary

- [ ] **Step 4: Switch `main.py` to orchestration entry point**

Replace the current inline single-scenario flow with:

```python
from nvme_test.orchestrator import run_test_plan

summary = run_test_plan(config=config, config_path=Path(args.config), test_dir=test_dir)
```

Keep logging setup and output directory creation in `main.py`, but move scenario execution and final accounting into orchestration.

- [ ] **Step 5: Verify the new modules import cleanly**

Run: `python3 -c "import main; import nvme_test.config; import nvme_test.device; import nvme_test.orchestrator"`

Expected: command exits successfully with no traceback

### Task 2: Add comparison CSV generation and overview plots

**Files:**
- Modify: `nvme_test/results.py`
- Modify: `nvme_test/plot.py`
- Modify: `nvme_test/orchestrator.py`

- [ ] **Step 1: Add comparison CSV helpers in `nvme_test/results.py`**

Add helpers to produce:
- `comparison/csv/all_results.csv`
- `comparison/csv/best_points.csv`
- `comparison/csv/fixed_points.csv`

Suggested interface:

```python
def write_comparison_outputs(
    scenario_results: list[dict],
    comparison_dir: Path,
    fixed_points: list[dict],
) -> dict:
    ...
```

Each merged row must include:

```python
{
    "target_id": ...,
    "target_label": ...,
    "target_type": ...,
}
```

Implement deterministic best-point selection with tie-breaks:
1. smaller block size
2. smaller `numjobs`
3. smaller `iodepth`

- [ ] **Step 2: Add comparison plotting helpers in `nvme_test/plot.py`**

Add functions shaped like:

```python
def generate_comparison_plots(
    all_results_csv: Path,
    best_points_csv: Path | None,
    fixed_points_csv: Path | None,
    plots_dir: Path,
    plot_format: str,
):
    ...
```

Generate:
- `best_bandwidth_overview.<fmt>`
- `best_iops_overview.<fmt>`
- `best_latency_overview.<fmt>`
- one `<point_name>_overview.<fmt>` figure per configured fixed point

Use grouped bars for best summaries and one 3-subplot figure per fixed point.

- [ ] **Step 3: Integrate comparison generation into orchestration**

After all eligible scenarios finish, `nvme_test/orchestrator.py` should:
- gather successful and partial scenario CSVs
- call comparison CSV generation
- call comparison plotting
- add comparison status and generated paths to `run_summary.json`

- [ ] **Step 4: Verify comparison helpers import cleanly**

Run: `python3 -c "import nvme_test.results; import nvme_test.plot; import nvme_test.orchestrator"`

Expected: command exits successfully with no traceback

### Task 3: Update docs, sample config, and run smoke verification

**Files:**
- Modify: `README.md`
- Create: `config_per_device_compare.json`
- Modify: `docs/superpowers/specs/2026-04-19-per-device-and-aggregate-design.md`
- Modify: `docs/superpowers/plans/2026-04-19-per-device-and-aggregate.md`

- [ ] **Step 1: Add a sample config for combined per-device and aggregate runs**

Create `config_per_device_compare.json` with:

```json
{
  "test_name": "per_device_and_aggregate",
  "devices": {
    "pci_addresses": ["0000:50:00.0", "0000:51:00.0"],
    "format_before_test": true,
    "use_raid": false,
    "raid_chunk_size": "64K"
  },
  "execution": {
    "run_aggregate": true,
    "run_per_device": true,
    "prepare_mode": "once",
    "comparison_summary": {
      "best_points": true,
      "fixed_points": [
        {
          "name": "4k_randread_hot",
          "workload": "randread",
          "block_size": "4K",
          "numjobs": 4,
          "iodepth": 64
        }
      ]
    }
  },
  "fio": {
    "block_sizes": ["4K", "64K"],
    "numjobs": [1, 4],
    "iodepth": [1, 64],
    "workloads": ["read", "randread"],
    "runtime": 5,
    "ramp_time": 2,
    "direct": 1,
    "ioengine": "libaio",
    "size": "100%"
  },
  "output": {
    "base_dir": "./output",
    "plot_format": "png"
  }
}
```

- [ ] **Step 2: Document the new execution mode in `README.md`**

Add:
- `execution` field table
- backward-compatible behavior when `execution` is absent
- output layout with `aggregate/`, `per_device/`, `comparison/`, and `run_summary.json`
- a per-device-only example description
- a combined-run example description

- [ ] **Step 3: Run focused smoke verification**

Run:
- `python3 -m compileall main.py nvme_test`
- `python3 -c "from nvme_test.config import load_config; cfg = load_config('config_per_device_compare.json'); print(cfg['execution']['prepare_mode'])"`

Expected:
- compile step reports no syntax errors
- config load prints `once`

- [ ] **Step 4: Run an orchestration dry smoke with stubbed scenario files**

Use a short Python command to call comparison generation against synthetic rows, for example:

```bash
python3 - <<'PY'
from pathlib import Path
from nvme_test.results import write_comparison_outputs
from nvme_test.plot import generate_comparison_plots

base = Path("/tmp/nvme-test-compare-smoke")
base.mkdir(parents=True, exist_ok=True)

scenario_results = [
    {
        "scenario_id": "per_device/0000_50_00_0",
        "target_id": "0000_50_00_0",
        "target_label": "0000:50:00.0",
        "target_type": "device",
        "csv_rows": [
            {"workload": "randread", "block_size": "4K", "numjobs": 4, "iodepth": 64, "bw_MBps": 1000.0, "iops": 250000.0, "lat_avg_us": 80.0, "lat_p50_us": 70.0, "lat_p99_us": 110.0, "lat_max_us": 200.0},
        ],
    },
]

outputs = write_comparison_outputs(
    scenario_results=scenario_results,
    comparison_dir=base,
    fixed_points=[{"name": "4k_randread_hot", "workload": "randread", "block_size": "4K", "numjobs": 4, "iodepth": 64}],
)
generate_comparison_plots(
    all_results_csv=outputs["all_results_csv"],
    best_points_csv=outputs["best_points_csv"],
    fixed_points_csv=outputs["fixed_points_csv"],
    plots_dir=base / "plots",
    plot_format="png",
)
print(sorted(p.name for p in (base / "plots").glob("*.png")))
PY
```

Expected: printed file list includes best-overview plots and `4k_randread_hot_overview.png`
