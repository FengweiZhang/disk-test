# Per-Device and Aggregate NVMe Test Orchestration

## Overview

Add a new execution mode that supports per-device fio testing for every PCI address listed in the JSON config, while preserving the existing aggregate test behavior.

The new design must support:

- aggregate-only runs (existing behavior)
- per-device-only runs
- combined runs that execute per-device tests and aggregate tests within one top-level run
- comparison CSVs and overview plots across tested devices
- configurable device preparation strategy, defaulting to "prepare once per run"

The existing single-scenario fio pipeline remains the core execution unit. The main change is to add a thin orchestration layer that expands one config into multiple scenarios and organizes their outputs under one run directory.

## Goals

- Keep existing configs working without changes
- Add a dedicated config section for per-device execution
- Reuse the current device preparation, fio generation, results aggregation, and plotting flow wherever possible
- Produce one run directory with clear separation between aggregate results, per-device results, and cross-device comparisons
- Support both best-result summaries and fixed-test-point summaries for comparison plots

## Non-Goals

- No parallel execution of scenarios in this phase
- No change to existing fio metric extraction logic
- No attempt to normalize or calibrate device state beyond the configured prepare strategy
- No redesign of the current per-scenario plot types

## Config Design

### Existing Sections

The existing `devices`, `fio`, and `output` sections stay in place.

### New `execution` Section

Add a new optional `execution` section:

```json
{
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
  }
}
```

### Field Semantics

| Field | Type | Description |
|------|------|-------------|
| `execution.run_aggregate` | bool | Whether to execute the aggregate scenario |
| `execution.run_per_device` | bool | Whether to execute one full fio matrix for each listed PCI address |
| `execution.prepare_mode` | string | `"once"` or `"per_test"` |
| `execution.comparison_summary.best_points` | bool | Whether to generate best-result comparison summaries |
| `execution.comparison_summary.fixed_points` | list | Explicit comparison points to extract from the fio matrix |

### Validation Rules

- `execution` is optional
- If `execution` is absent:
  - `run_aggregate = true`
  - `run_per_device = false`
  - `prepare_mode = "once"`
  - `comparison_summary.best_points = false`
  - `comparison_summary.fixed_points = []`
- At least one of `run_aggregate` or `run_per_device` must be `true`
- `prepare_mode` must be `"once"` or `"per_test"`
- Each fixed point `name` must be unique
- Each fixed point must reference values already present in:
  - `fio.workloads`
  - `fio.block_sizes`
  - `fio.numjobs`
  - `fio.iodepth`

This preserves backward compatibility while adding a dedicated execution configuration for the new mode.

## Output Layout

One config run creates one top-level directory:

```text
output/<test_name>_<YYYYMMDD_HHMMSS>/
├── config.json
├── run_summary.json
├── aggregate/
│   ├── fio_jobs/
│   ├── fio_raw/
│   ├── csv/results.csv
│   └── plots/
├── per_device/
│   ├── 0000_50_00_0/
│   │   ├── fio_jobs/
│   │   ├── fio_raw/
│   │   ├── csv/results.csv
│   │   └── plots/
│   └── 0000_51_00_0/
│       ├── fio_jobs/
│       ├── fio_raw/
│       ├── csv/results.csv
│       └── plots/
└── comparison/
    ├── csv/
    └── plots/
```

### Directory Rules

- `aggregate/` stores the existing aggregate scenario outputs
- `per_device/<sanitized_pci>/` stores the outputs for one PCI device
- `comparison/` stores merged comparison CSVs and overview plots
- `run_summary.json` stores machine-readable scenario status and output paths

PCI addresses are sanitized for directory names by replacing `:` and `.` with `_`.

## Execution Architecture

### Recommended Approach

Add a small orchestration layer instead of replacing the current single-scenario flow.

### Module Responsibilities

#### `main.py`

- parse CLI args
- load config
- create top-level output directory
- copy config into the run directory
- invoke the new orchestration entry point
- print final summary

#### New orchestration module

Add a new module such as `nvme_test/orchestrator.py` to:

- normalize config defaults
- expand the config into a scenario list
- manage device preparation timing
- execute each scenario in sequence
- collect scenario summaries
- generate comparison CSVs and overview plots
- write `run_summary.json`

#### `device.py`

Extend the current API so orchestration can work with explicit device mappings instead of only a single test target string.

The device layer should support:

- preparing one PCI address and returning its `/dev/nvmeXnY`
- preparing multiple PCI addresses and returning a mapping:
  - `pci_addr -> device_path`
- constructing an aggregate target from prepared devices:
  - single-device path
  - RAID device path
  - colon-separated fio multi-device path

RAID creation and teardown should remain scoped to the aggregate scenario only.

#### `fio.py`, `results.py`, and `plot.py`

These remain scenario-level utilities:

- generate job files for one explicit target device string
- run jobs for one scenario
- aggregate results for one scenario
- generate the current per-scenario plot set for one scenario

This keeps the existing pipeline reusable with minimal change.

## Scenario Expansion

The orchestration layer expands one config into a list of scenarios:

- one `per_device/<pci>` scenario for each listed PCI address if `run_per_device = true`
- one `aggregate` scenario if `run_aggregate = true`

### Scenario Order

Run scenarios in this order:

1. all per-device scenarios
2. aggregate scenario

This ordering keeps the default `prepare_mode = "once"` intuitive and leaves RAID creation, if any, to the final phase.

## Device Preparation Strategy

### `prepare_mode = "once"`

- prepare all configured PCI devices once at the start of the run
- reuse the resulting mapping for all per-device scenarios
- create RAID only when entering the aggregate scenario, if `use_raid = true`
- tear down RAID after the aggregate scenario completes

This is the default because it is faster and matches the requested behavior.

### `prepare_mode = "per_test"`

- each scenario prepares the devices it needs immediately before execution
- each `per_device/<pci>` scenario prepares only that device
- the aggregate scenario prepares all listed devices
- aggregate RAID lifecycle still exists only inside the aggregate scenario

This mode favors cleaner isolation between scenarios at the cost of longer runtime.

## Scenario Execution Flow

Each scenario reuses the same scenario-level pipeline:

1. resolve the scenario target device string
2. create scenario output subdirectories
3. generate fio jobs
4. run fio jobs sequentially
5. aggregate successful fio JSON outputs into `csv/results.csv`
6. generate the standard per-scenario plot set
7. record scenario status for `run_summary.json`

Scenario output structure deliberately mirrors the current top-level run structure so existing downstream logic can be reused with path substitutions.

## Comparison Data Model

Generate comparison data from successful or partially successful per-device and aggregate scenario CSVs.

### `comparison/csv/all_results.csv`

Merge all scenario result rows into a single CSV and add these columns:

- `target_id` — stable identifier such as `aggregate` or `0000_50_00_0`
- `target_label` — human-readable label such as `aggregate` or `0000:50:00.0`
- `target_type` — `aggregate` or `device`

This file is the base dataset for all comparison outputs.

### `comparison/csv/best_points.csv`

Store one row per:

- `target`
- `workload`
- `summary_type`

Recommended `summary_type` values:

- `best_bw`
- `best_iops`
- `best_latency`

Best-point selection rules:

- `best_bw` = row with maximum `bw_MBps`
- `best_iops` = row with maximum `iops`
- `best_latency` = row with minimum `lat_avg_us`

Tie-break rule for deterministic output:

1. smaller block size
2. smaller `numjobs`
3. smaller `iodepth`

Each best-point row should retain the original:

- `workload`
- `block_size`
- `numjobs`
- `iodepth`
- metric columns

so users can see exactly which test combination produced the summary value.

### `comparison/csv/fixed_points.csv`

Store one row per configured fixed point per target.

Each row should include:

- `point_name`
- `workload`
- `block_size`
- `numjobs`
- `iodepth`
- metric columns
- `target_id`
- `target_label`
- `target_type`

If a fixed point is configured but a target does not have a corresponding row, omit it from the output and record the omission in `run_summary.json`.

## Comparison Plot Design

The user selected a summary-oriented comparison output rather than a full matrix of per-dimension cross-device plots.

### Best-Point Overview Plots

Generate three grouped bar charts:

- `best_bandwidth_overview.<plot_format>`
- `best_iops_overview.<plot_format>`
- `best_latency_overview.<plot_format>`

Plot rules:

- X-axis = workload
- series = target devices plus aggregate if present
- Y-axis = metric value
- latency title should explicitly indicate that lower is better

### Fixed-Point Overview Plots

Generate one file per configured fixed point:

- `<point_name>_overview.<plot_format>`

Each fixed-point overview plot should contain three subplots:

- bandwidth
- IOPS
- average latency

Plot rules:

- X-axis = target
- one figure per fixed point keeps the output compact
- aggregate appears alongside individual devices when available

## Failure Handling

### Config Errors

- invalid config exits immediately before scenario execution begins

### Device Preparation Failures

#### `prepare_mode = "once"`

- if shared preparation fails, the entire run fails

#### `prepare_mode = "per_test"`

- a failing per-device scenario is marked `failed`
- remaining per-device scenarios continue
- an aggregate preparation failure marks only aggregate as `failed`

### fio Failures

- failed fio jobs do not stop the scenario
- successful JSON outputs are still aggregated
- scenario status becomes:
  - `success` if all jobs succeed
  - `partial` if some jobs fail but CSV/plots are still produced
  - `failed` if no usable result data is produced

### Plotting or Comparison Failures

- preserve already generated job files, raw fio outputs, and CSVs
- mark the affected scenario or comparison stage as `partial`
- record an error message in `run_summary.json`

## `run_summary.json`

Write one machine-readable summary file at the run root.

Recommended structure:

```json
{
  "test_name": "multi_nvme_compare",
  "started_at": "2026-04-19T12:00:00Z",
  "finished_at": "2026-04-19T12:34:56Z",
  "prepare_mode": "once",
  "scenarios": [
    {
      "scenario_id": "per_device/0000_50_00_0",
      "target_label": "0000:50:00.0",
      "status": "success",
      "jobs_total": 96,
      "jobs_succeeded": 96,
      "csv_path": "per_device/0000_50_00_0/csv/results.csv",
      "plots_dir": "per_device/0000_50_00_0/plots"
    },
    {
      "scenario_id": "aggregate",
      "target_label": "aggregate",
      "status": "partial",
      "jobs_total": 96,
      "jobs_succeeded": 94,
      "csv_path": "aggregate/csv/results.csv",
      "plots_dir": "aggregate/plots",
      "error_message": "2 fio jobs failed"
    }
  ],
  "comparison": {
    "status": "success",
    "included_targets": ["0000_50_00_0", "0000_51_00_0", "aggregate"],
    "generated_csv": [
      "comparison/csv/all_results.csv",
      "comparison/csv/best_points.csv",
      "comparison/csv/fixed_points.csv"
    ],
    "generated_plots": [
      "comparison/plots/best_bandwidth_overview.png",
      "comparison/plots/best_iops_overview.png",
      "comparison/plots/best_latency_overview.png",
      "comparison/plots/4k_randread_hot_overview.png"
    ]
  }
}
```

Comparison should include only scenario outputs with status `success` or `partial`.

## Documentation Changes

Update `README.md` to include:

- the new `execution` section and field descriptions
- backward compatibility behavior for configs without `execution`
- a per-device-only example config
- a combined per-device plus aggregate example config
- the new output directory layout
- the meaning of `run_summary.json`
- the comparison CSV and plot outputs

Add a new sample config file:

- `config_per_device_compare.json`

## Validation Strategy

Focus automated validation on pure Python logic and deterministic file generation rather than on real `sudo fio` execution.

### Automated Tests

Recommended coverage:

- config compatibility and validation
- scenario expansion rules
- prepare strategy branching
- comparison CSV generation
- best-point tie-breaking
- fixed-point extraction

### Manual Verification

Use a quick two-device config with:

- `run_per_device = true`
- `run_aggregate = true`
- at least one fixed point

Verify that the run produces:

- `aggregate/`
- `per_device/`
- `comparison/`
- `run_summary.json`

and that comparison outputs include both:

- best-result summaries
- fixed-point summaries

## Files Expected to Change

| File | Change |
|------|--------|
| `main.py` | Replace direct single-scenario flow with orchestration entry |
| `nvme_test/config.py` | Add `execution` defaults and validation |
| `nvme_test/device.py` | Expose device mapping and aggregate target construction helpers |
| `nvme_test/fio.py` | Reuse scenario pipeline with minimal interface adjustments if needed |
| `nvme_test/results.py` | Reuse per-scenario aggregation; may add helpers for comparison CSV generation |
| `nvme_test/plot.py` | Add comparison overview plot generation helpers |
| `nvme_test/orchestrator.py` | New scenario expansion and run coordination module |
| `README.md` | Document the new execution mode and outputs |
| `config_per_device_compare.json` | New example config |
