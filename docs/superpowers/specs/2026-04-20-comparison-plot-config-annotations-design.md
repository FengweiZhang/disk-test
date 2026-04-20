# Comparison Plot Config Annotations

## Overview

Add visible test-configuration annotations to comparison overview plots generated from `comparison_summary`.

The user wants PNG/PDF images to show the configuration behind:

- fixed comparison points such as `16k_read_hot`
- best-result overview bars, where each best result may come from a different fio matrix point

## Scope

Only comparison overview plots are changed:

- `<point_name>_overview.<format>` from `fixed_points.csv`
- `best_bandwidth_overview.<format>`
- `best_iops_overview.<format>`
- `best_latency_overview.<format>`

Per-scenario matrix plots are unchanged because they show many combinations through lines rather than one specific test condition.

## Fixed-Point Plot Annotation

Each fixed-point overview figure gets a compact table inside the image.

Columns:

- `name`
- `workload`
- `block_size`
- `numjobs`
- `iodepth`

Example:

```text
name            workload  block_size  numjobs  iodepth
16k_read_hot    read      16K         4        64
```

## Best-Point Plot Annotation

Each best overview figure gets a table inside the image showing the fio matrix point that produced each displayed best bar.

Columns:

- `workload`
- `target`
- `block_size`
- `numjobs`
- `iodepth`

Example:

```text
workload  target          block_size  numjobs  iodepth
read      0000:50:00.0    16K         4        64
read      aggregate       16K         4        256
```

The table content differs per best plot:

- `best_bandwidth_overview` shows the config rows for `summary_type = best_bw`
- `best_iops_overview` shows the config rows for `summary_type = best_iops`
- `best_latency_overview` shows the config rows for `summary_type = best_latency`

## Layout

Add one reusable helper in `nvme_test/plot.py` to render a table at the bottom of a figure.

Layout rules:

- Use a small font size so the table remains readable without dominating the plot.
- Increase figure height based on table row count.
- Keep the table below the plotting area to avoid covering bars.
- Keep all rows visible rather than truncating.

## Files

- `nvme_test/plot.py`
  - add reusable config table helper
  - update best overview plots
  - update fixed-point overview plots
- `README.md`
  - document that comparison plots include config tables

## Validation

Use synthetic comparison rows to generate:

- `best_bandwidth_overview.png`
- `best_iops_overview.png`
- `best_latency_overview.png`
- `<point_name>_overview.png`

Then verify the commands complete and output files exist.
