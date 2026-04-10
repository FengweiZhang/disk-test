# numjobs X-axis Bandwidth/IOPS Plots Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `plot_bandwidth_iops_by_nj` to generate bandwidth and IOPS line plots with numjobs as the X-axis, completing the three-dimension plotting symmetry.

**Architecture:** New function in `nvme_test/plot.py` mirrors `plot_bandwidth_iops_by_bs` but swaps the X-axis from block_size to numjobs, with lines representing (block_size, iodepth) combos. Integrated via a single call in `generate_all_plots()`.

**Tech Stack:** Python, matplotlib, existing CSV loading/filtering helpers in `plot.py`

---

## File Structure

- **Modify:** `nvme_test/plot.py` — add `plot_bandwidth_iops_by_nj` function and update `generate_all_plots()`

---

### Task 1: Add `plot_bandwidth_iops_by_nj` function

**Files:**
- Modify: `nvme_test/plot.py:143` (insert before `plot_latency`)

- [ ] **Step 1: Add the function after `plot_bandwidth_iops_by_bs` and before `plot_latency`**

Insert the following function at line 145 (after the blank line following `plot_bandwidth_iops_by_bs`, before `def plot_latency`):

```python
def plot_bandwidth_iops_by_nj(csv_path: Path, plots_dir: Path, plot_format: str):
    """Generate line plots for bandwidth and IOPS with numjobs as X-axis.

    One chart per (workload, metric).
    X-axis: numjobs (log2). Lines: each (block_size, iodepth) combo.
    """
    rows = _load_csv(csv_path)
    plots_dir.mkdir(parents=True, exist_ok=True)

    workloads = sorted(set(r["workload"] for r in rows))
    metrics = [("bw_MBps", "Bandwidth (MB/s)", "bandwidth"), ("iops", "IOPS", "iops")]

    for workload in workloads:
        wl_rows = _filter_rows(rows, workload=workload)
        if not wl_rows:
            continue

        block_sizes = sorted(set(r["block_size"] for r in wl_rows),
                             key=_parse_block_size)
        iodepths = sorted(set(r["iodepth"] for r in wl_rows))

        for metric_key, ylabel, file_suffix in metrics:
            fig, ax = plt.subplots(figsize=(10, 6))

            for bs in block_sizes:
                for qd in iodepths:
                    series = _filter_rows(wl_rows, block_size=bs, iodepth=qd)
                    if not series:
                        continue
                    series.sort(key=lambda r: r["numjobs"])
                    x = [r["numjobs"] for r in series]
                    y = [r[metric_key] for r in series]
                    label = f"{bs}_qd{qd}"
                    ax.plot(x, y, marker="o", label=label)

            ax.set_xlabel("Number of Jobs")
            ax.set_ylabel(ylabel)
            ax.set_title(f"{workload} - {ylabel} (by numjobs)")
            ax.set_xscale("log", base=2)
            all_nj = sorted(set(r["numjobs"] for r in wl_rows))
            ax.set_xticks(all_nj)
            ax.set_xticklabels([str(nj) for nj in all_nj])
            ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left")
            fig.tight_layout()

            out_path = plots_dir / f"{workload}_by_nj_{file_suffix}.{plot_format}"
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
git commit -m "feat: add plot_bandwidth_iops_by_nj for numjobs x-axis plots"
```

---

### Task 2: Integrate into `generate_all_plots()`

**Files:**
- Modify: `nvme_test/plot.py` — `generate_all_plots` function (line 210-214)

- [ ] **Step 1: Add `plot_bandwidth_iops_by_nj` call in `generate_all_plots`**

The current `generate_all_plots` body is:

```python
def generate_all_plots(csv_path: Path, plots_dir: Path, plot_format: str):
    """Generate all plots from results CSV."""
    plot_bandwidth_iops(csv_path, plots_dir, plot_format)
    plot_bandwidth_iops_by_bs(csv_path, plots_dir, plot_format)
    plot_latency(csv_path, plots_dir, plot_format)
```

Add the new call after `plot_bandwidth_iops_by_bs`:

```python
def generate_all_plots(csv_path: Path, plots_dir: Path, plot_format: str):
    """Generate all plots from results CSV."""
    plot_bandwidth_iops(csv_path, plots_dir, plot_format)
    plot_bandwidth_iops_by_bs(csv_path, plots_dir, plot_format)
    plot_bandwidth_iops_by_nj(csv_path, plots_dir, plot_format)
    plot_latency(csv_path, plots_dir, plot_format)
```

- [ ] **Step 2: Verify clean import**

Run: `python -c "import nvme_test.plot"` from the project root.
Expected: No output (clean import).

- [ ] **Step 3: Commit**

```bash
git add nvme_test/plot.py
git commit -m "feat: integrate plot_bandwidth_iops_by_nj into generate_all_plots"
```
