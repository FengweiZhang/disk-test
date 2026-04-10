# Design: Bandwidth/IOPS Plots with numjobs X-axis

**Date:** 2026-04-10

## Context

`nvme_test/plot.py` has two bandwidth/IOPS plotting functions covering two of the three test dimensions as X-axes:

| Function | X-axis | Lines |
|----------|--------|-------|
| `plot_bandwidth_iops` | iodepth | (block_size, numjobs) |
| `plot_bandwidth_iops_by_bs` | block_size | (iodepth, numjobs) |

The third dimension — numjobs — is missing as an X-axis option.

## Requirement

Add `plot_bandwidth_iops_by_nj` to complete the symmetry.

## Function Specification

### `plot_bandwidth_iops_by_nj(csv_path, plots_dir, plot_format)`

- **X-axis:** numjobs (integer values: 1, 2, 4, ...), log2 scale
- **Lines:** each (block_size, iodepth) combination
- **Label format:** `{bs}_qd{qd}` (e.g., `4K_qd128`)
- **One chart per:** (workload, metric)
- **Metrics:** bandwidth (MB/s) and IOPS

### Chart Parameters

- Figure size: (10, 6)
- X-axis: log2 scale, tick labels are integer numjobs values
- Y-axis: metric value (MB/s or IOPS count)
- Legend: `bbox_to_anchor=(1.05, 1)`, `loc="upper left"`
- DPI: 150, `bbox_inches="tight"`

### Output File Naming

- `{workload}_by_nj_bandwidth.{plot_format}`
- `{workload}_by_nj_iops.{plot_format}`

## Integration

Add call to `plot_bandwidth_iops_by_nj` in `generate_all_plots()`.

## Notes

- numjobs is already an integer in the CSV, so no string-to-int parsing (unlike block_size) is needed.
- X-axis tick labels use the raw integer values directly.
- Structure mirrors `plot_bandwidth_iops_by_bs` with iodepth/block_size roles swapped with numjobs.
