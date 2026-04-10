# Avg Latency Line Plots Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three latency line-plot functions (`plot_latency_by_qd`, `plot_latency_by_bs`, `plot_latency_by_nj`) to `nvme_test/plot.py` with avg latency as the line and p99 as a semi-transparent error band, then replace the old `plot_latency` bar chart call in `generate_all_plots`.

**Architecture:** Three new functions mirror the existing `plot_bandwidth_iops_by_qd/bs/nj` pattern, substituting the metric loop with a single `lat_avg_us` line + `fill_between` to `lat_p99_us`. The old `plot_latency` function is retained in code but removed from the `generate_all_plots` pipeline.

**Tech Stack:** Python, matplotlib (`fill_between` for error bands), existing `_load_csv`, `_filter_rows`, `_parse_block_size` helpers.

---

## File Structure

- **Modify:** `nvme_test/plot.py` — add 3 new functions, update `generate_all_plots()`

---

### Task 1: Add `plot_latency_by_qd` function

**Files:**
- Modify: `nvme_test/plot.py` (insert after `plot_bandwidth_iops_by_nj`, before `plot_latency`)

- [ ] **Step 1: Add the function**

Insert the following function after `plot_bandwidth_iops_by_nj` (after line 195) and before `plot_latency`:

```python
def plot_latency_by_qd(csv_path: Path, plots_dir: Path, plot_format: str):
    """Generate line plots for avg latency with p99 error band.

    One chart per workload.
    X-axis: iodepth (log2). Lines: each (block_size, numjobs) combo.
    """
    rows = _load_csv(csv_path)
    plots_dir.mkdir(parents=True, exist_ok=True)

    workloads = sorted(set(r["workload"] for r in rows))

    for workload in workloads:
        wl_rows = _filter_rows(rows, workload=workload)
        if not wl_rows:
            continue

        block_sizes = sorted(set(r["block_size"] for r in wl_rows),
                             key=_parse_block_size)
        numjobs_list = sorted(set(r["numjobs"] for r in wl_rows))

        fig, ax = plt.subplots(figsize=(10, 6))

        for bs in block_sizes:
            for nj in numjobs_list:
                series = _filter_rows(wl_rows, block_size=bs, numjobs=nj)
                if not series:
                    continue
                series.sort(key=lambda r: r["iodepth"])
                x = [r["iodepth"] for r in series]
                y_avg = [r["lat_avg_us"] for r in series]
                y_p99 = [r["lat_p99_us"] for r in series]
                label = f"{bs}_nj{nj}"
                (line,) = ax.plot(x, y_avg, marker="o", label=label)
                ax.fill_between(x, y_avg, y_p99, alpha=0.2,
                                color=line.get_color())

        ax.set_xlabel("IO Depth")
        ax.set_ylabel("Latency (us)")
        ax.set_title(f"{workload} - Avg Latency (by iodepth)")
        ax.set_xscale("log", base=2)
        ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left")
        fig.tight_layout()

        out_path = plots_dir / f"{workload}_latency_by_qd.{plot_format}"
        fig.savefig(out_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        logger.info("Saved plot: %s", out_path.name)
```

- [ ] **Step 2: Verify no syntax errors**

Run: `python -c "import nvme_test.plot"` from the project root.
Expected: No output (clean import).

- [ ] **Step 3: Commit**

```bash
git add nvme_test/plot.py
git commit -m "feat: add plot_latency_by_qd for avg latency line plot"
```

---

### Task 2: Add `plot_latency_by_bs` function

**Files:**
- Modify: `nvme_test/plot.py` (insert after `plot_latency_by_qd`, before `plot_latency`)

- [ ] **Step 1: Add the function**

Insert the following function after `plot_latency_by_qd`:

```python
def plot_latency_by_bs(csv_path: Path, plots_dir: Path, plot_format: str):
    """Generate line plots for avg latency with p99 error band, block size X-axis.

    One chart per workload.
    X-axis: block_size (log2). Lines: each (iodepth, numjobs) combo.
    """
    rows = _load_csv(csv_path)
    plots_dir.mkdir(parents=True, exist_ok=True)

    workloads = sorted(set(r["workload"] for r in rows))

    for workload in workloads:
        wl_rows = _filter_rows(rows, workload=workload)
        if not wl_rows:
            continue

        iodepths = sorted(set(r["iodepth"] for r in wl_rows))
        numjobs_list = sorted(set(r["numjobs"] for r in wl_rows))

        fig, ax = plt.subplots(figsize=(10, 6))

        for qd in iodepths:
            for nj in numjobs_list:
                series = _filter_rows(wl_rows, iodepth=qd, numjobs=nj)
                if not series:
                    continue
                series.sort(key=lambda r: _parse_block_size(r["block_size"]))
                x = [_parse_block_size(r["block_size"]) for r in series]
                y_avg = [r["lat_avg_us"] for r in series]
                y_p99 = [r["lat_p99_us"] for r in series]
                label = f"qd{qd}_nj{nj}"
                (line,) = ax.plot(x, y_avg, marker="o", label=label)
                ax.fill_between(x, y_avg, y_p99, alpha=0.2,
                                color=line.get_color())

        ax.set_xlabel("Block Size")
        ax.set_ylabel("Latency (us)")
        ax.set_title(f"{workload} - Avg Latency (by block size)")
        ax.set_xscale("log", base=2)
        all_bs = sorted(set(r["block_size"] for r in wl_rows),
                        key=_parse_block_size)
        ax.set_xticks([_parse_block_size(bs) for bs in all_bs])
        ax.set_xticklabels(all_bs)
        ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left")
        fig.tight_layout()

        out_path = plots_dir / f"{workload}_latency_by_bs.{plot_format}"
        fig.savefig(out_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        logger.info("Saved plot: %s", out_path.name)
```

- [ ] **Step 2: Verify no syntax errors**

Run: `python -c "import nvme_test.plot"` from the project root.
Expected: No output (clean import).

- [ ] **Step 3: Commit**

```bash
git add nvme_test/plot.py
git commit -m "feat: add plot_latency_by_bs for avg latency by block size"
```

---

### Task 3: Add `plot_latency_by_nj` function

**Files:**
- Modify: `nvme_test/plot.py` (insert after `plot_latency_by_bs`, before `plot_latency`)

- [ ] **Step 1: Add the function**

Insert the following function after `plot_latency_by_bs`:

```python
def plot_latency_by_nj(csv_path: Path, plots_dir: Path, plot_format: str):
    """Generate line plots for avg latency with p99 error band, numjobs X-axis.

    One chart per workload.
    X-axis: numjobs (log2). Lines: each (block_size, iodepth) combo.
    """
    rows = _load_csv(csv_path)
    plots_dir.mkdir(parents=True, exist_ok=True)

    workloads = sorted(set(r["workload"] for r in rows))

    for workload in workloads:
        wl_rows = _filter_rows(rows, workload=workload)
        if not wl_rows:
            continue

        block_sizes = sorted(set(r["block_size"] for r in wl_rows),
                             key=_parse_block_size)
        iodepths = sorted(set(r["iodepth"] for r in wl_rows))

        fig, ax = plt.subplots(figsize=(10, 6))

        for bs in block_sizes:
            for qd in iodepths:
                series = _filter_rows(wl_rows, block_size=bs, iodepth=qd)
                if not series:
                    continue
                series.sort(key=lambda r: r["numjobs"])
                x = [r["numjobs"] for r in series]
                y_avg = [r["lat_avg_us"] for r in series]
                y_p99 = [r["lat_p99_us"] for r in series]
                label = f"{bs}_qd{qd}"
                (line,) = ax.plot(x, y_avg, marker="o", label=label)
                ax.fill_between(x, y_avg, y_p99, alpha=0.2,
                                color=line.get_color())

        ax.set_xlabel("Number of Jobs")
        ax.set_ylabel("Latency (us)")
        ax.set_title(f"{workload} - Avg Latency (by numjobs)")
        ax.set_xscale("log", base=2)
        all_nj = sorted(set(r["numjobs"] for r in wl_rows))
        ax.set_xticks(all_nj)
        ax.set_xticklabels([str(nj) for nj in all_nj])
        ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left")
        fig.tight_layout()

        out_path = plots_dir / f"{workload}_latency_by_nj.{plot_format}"
        fig.savefig(out_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        logger.info("Saved plot: %s", out_path.name)
```

- [ ] **Step 2: Verify no syntax errors**

Run: `python -c "import nvme_test.plot"` from the project root.
Expected: No output (clean import).

- [ ] **Step 3: Commit**

```bash
git add nvme_test/plot.py
git commit -m "feat: add plot_latency_by_nj for avg latency by numjobs"
```

---

### Task 4: Update `generate_all_plots` pipeline

**Files:**
- Modify: `nvme_test/plot.py` — `generate_all_plots` function (lines 261-266)

- [ ] **Step 1: Replace the `generate_all_plots` body**

Current body:

```python
def generate_all_plots(csv_path: Path, plots_dir: Path, plot_format: str):
    """Generate all plots from results CSV."""
    plot_bandwidth_iops_by_qd(csv_path, plots_dir, plot_format)
    plot_bandwidth_iops_by_bs(csv_path, plots_dir, plot_format)
    plot_bandwidth_iops_by_nj(csv_path, plots_dir, plot_format)
    plot_latency(csv_path, plots_dir, plot_format)
```

Replace with:

```python
def generate_all_plots(csv_path: Path, plots_dir: Path, plot_format: str):
    """Generate all plots from results CSV."""
    plot_bandwidth_iops_by_qd(csv_path, plots_dir, plot_format)
    plot_bandwidth_iops_by_bs(csv_path, plots_dir, plot_format)
    plot_bandwidth_iops_by_nj(csv_path, plots_dir, plot_format)
    plot_latency_by_qd(csv_path, plots_dir, plot_format)
    plot_latency_by_bs(csv_path, plots_dir, plot_format)
    plot_latency_by_nj(csv_path, plots_dir, plot_format)
```

- [ ] **Step 2: Verify clean import**

Run: `python -c "import nvme_test.plot"` from the project root.
Expected: No output (clean import).

- [ ] **Step 3: Smoke test with real data**

Run:

```bash
python -c "
from pathlib import Path
from nvme_test.plot import generate_all_plots
generate_all_plots(
    Path('output/test_iops_1_disk_20260410_122713/csv/results.csv'),
    Path('/tmp/latency_plot_test'),
    'png'
)
print('OK')
"
```

Expected: `OK` printed, and `/tmp/latency_plot_test/` contains files including `read_latency_by_qd.png`, `read_latency_by_bs.png`, `read_latency_by_nj.png`.

Verify output files:

```bash
ls /tmp/latency_plot_test/*latency*
```

Expected: 3 latency plot files.

- [ ] **Step 4: Commit**

```bash
git add nvme_test/plot.py
git commit -m "feat: integrate latency line plots into generate_all_plots"
```
