# Avg Latency Line Plots Design Spec

## Overview

Add three new line-plot functions to `nvme_test/plot.py` for visualizing average latency across different X-axis parameters (iodepth, block_size, numjobs), with p99 latency shown as a semi-transparent error band. Replace the existing `plot_latency` bar chart call in `generate_all_plots` with these three new functions.

## Motivation

The existing `plot_latency` function generates grouped bar charts fixed per (workload, block_size) with iodepth on the X-axis. This limits analysis to a single dimension. The new line plots will provide consistent latency visualization across all three parameter axes, matching the existing bandwidth/IOPS plot coverage.

## New Functions

### `plot_latency_by_qd(csv_path, plots_dir, plot_format)`

- **Scope**: One chart per workload
- **X-axis**: `iodepth` (log2 scale)
- **Lines**: Each `(block_size, numjobs)` combination
- **Label format**: `{block_size}_nj{numjobs}` (e.g., `4K_nj1`)
- **Line**: `lat_avg_us`, solid line with `marker="o"`
- **Error band**: `fill_between(x, lat_avg_us, lat_p99_us, alpha=0.2)`, color matches line
- **Output file**: `{workload}_latency_by_qd.{format}`

### `plot_latency_by_bs(csv_path, plots_dir, plot_format)`

- **Scope**: One chart per workload
- **X-axis**: `block_size` converted to bytes via `_parse_block_size()` (log2 scale), original strings as tick labels
- **Lines**: Each `(iodepth, numjobs)` combination
- **Label format**: `qd{iodepth}_nj{numjobs}` (e.g., `qd32_nj1`)
- **Line**: `lat_avg_us`, solid line with `marker="o"`
- **Error band**: `fill_between(x, lat_avg_us, lat_p99_us, alpha=0.2)`, color matches line
- **Output file**: `{workload}_latency_by_bs.{format}`

### `plot_latency_by_nj(csv_path, plots_dir, plot_format)`

- **Scope**: One chart per workload
- **X-axis**: `numjobs` (log2 scale), integer tick labels
- **Lines**: Each `(block_size, iodepth)` combination
- **Label format**: `{block_size}_qd{iodepth}` (e.g., `4K_qd32`)
- **Line**: `lat_avg_us`, solid line with `marker="o"`
- **Error band**: `fill_between(x, lat_avg_us, lat_p99_us, alpha=0.2)`, color matches line
- **Output file**: `{workload}_latency_by_nj.{format}`

## Chart Style (shared)

| Property         | Value                                    |
|------------------|------------------------------------------|
| figsize          | `(10, 6)`                                |
| Y-axis label     | `Latency (us)`                           |
| Title            | `{workload} - Avg Latency (by {x_param})`|
| X scale          | `log`, base=2                            |
| Legend position   | `bbox_to_anchor=(1.05, 1)`, `loc="upper left"` |
| dpi              | 150                                      |
| Error band alpha | 0.2                                      |

## Changes to `generate_all_plots`

```python
def generate_all_plots(csv_path, plots_dir, plot_format):
    plot_bandwidth_iops_by_qd(csv_path, plots_dir, plot_format)
    plot_bandwidth_iops_by_bs(csv_path, plots_dir, plot_format)
    plot_bandwidth_iops_by_nj(csv_path, plots_dir, plot_format)
    # plot_latency removed from pipeline
    plot_latency_by_qd(csv_path, plots_dir, plot_format)
    plot_latency_by_bs(csv_path, plots_dir, plot_format)
    plot_latency_by_nj(csv_path, plots_dir, plot_format)
```

## Unchanged

- `plot_latency` function code is retained but no longer called by `generate_all_plots`.

## Implementation Notes

- Each function follows the same structure as the existing `plot_bandwidth_iops_by_qd/bs/nj` functions.
- The `fill_between` call uses the line's color via `ax.plot()` return value: `line, = ax.plot(...)` then `ax.fill_between(..., color=line.get_color(), alpha=0.2)`.
- All three functions reuse existing helpers: `_load_csv`, `_filter_rows`, `_parse_block_size`.
