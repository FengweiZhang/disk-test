# Plot Bandwidth/IOPS by Block Size

## Goal

Add a new set of line plots to `nvme_test/plot.py` that show bandwidth and IOPS with **block size as the X-axis**, complementing the existing plots that use iodepth as the X-axis.

## Design

### New function: `plot_bandwidth_iops_by_bs`

Mirrors `plot_bandwidth_iops` with swapped axes:

| Aspect | Existing `plot_bandwidth_iops` | New `plot_bandwidth_iops_by_bs` |
|--------|-------------------------------|----------------------------------|
| X-axis | iodepth (log2) | block_size (log2) |
| Lines  | `{bs}_nj{numjobs}` | `qd{iodepth}_nj{numjobs}` |
| Charts | One per workload, two metrics | One per workload, two metrics |
| Files  | `{wl}_bandwidth.fmt` | `{wl}_by_bs_bandwidth.fmt` |

### X-axis handling

Block size values are strings like "4K", "64K", "1M". To place them on a log2 numeric axis:

1. Add helper `_parse_block_size(s: str) -> int` that converts "4K" -> 4096, "1M" -> 1048576, etc.
2. Use the parsed numeric value for X-axis positioning.
3. Keep the original string as tick label.
4. Sort X values numerically.

### Chart details

- **Figure size**: (10, 6) — same as existing plots
- **X-axis**: log2 scale, tick labels show original strings ("4K", "16K", ...)
- **Y-axis**: "Bandwidth (MB/s)" or "IOPS"
- **Title**: `{workload} - {ylabel} (by block size)`
- **Legend**: outside plot, upper left anchored at (1.05, 1) — same as existing
- **Markers**: "o" — same as existing
- **DPI**: 150 — same as existing

### Integration

Add `plot_bandwidth_iops_by_bs(csv_path, plots_dir, plot_format)` call in `generate_all_plots`.

### Output file naming

```
{workload}_by_bs_bandwidth.{png|pdf}
{workload}_by_bs_iops.{png|pdf}
```

Examples: `read_by_bs_bandwidth.png`, `randwrite_by_bs_iops.png`

## Files to modify

- `nvme_test/plot.py`: Add `_parse_block_size` helper and `plot_bandwidth_iops_by_bs` function; update `generate_all_plots`.

## Out of scope

- No changes to existing plots.
- No changes to CSV format, config, or test execution.
- No new dependencies.
