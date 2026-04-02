import csv
import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

logger = logging.getLogger(__name__)


def _load_csv(csv_path: Path) -> list[dict]:
    """Load CSV results into list of dicts with numeric conversion."""
    rows = []
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["numjobs"] = int(row["numjobs"])
            row["iodepth"] = int(row["iodepth"])
            row["bw_MBps"] = float(row["bw_MBps"])
            row["iops"] = float(row["iops"])
            row["lat_avg_us"] = float(row["lat_avg_us"])
            row["lat_p50_us"] = float(row["lat_p50_us"])
            row["lat_p99_us"] = float(row["lat_p99_us"])
            row["lat_max_us"] = float(row["lat_max_us"])
            rows.append(row)
    return rows


def _filter_rows(rows: list[dict], **kwargs) -> list[dict]:
    """Filter rows matching all given key=value pairs."""
    result = rows
    for key, value in kwargs.items():
        result = [r for r in result if r[key] == value]
    return result


def plot_bandwidth_iops(csv_path: Path, plots_dir: Path, plot_format: str):
    """Generate line plots for bandwidth and IOPS.

    One chart per (workload, metric).
    X-axis: iodepth. Lines: each (block_size, numjobs) combo.
    """
    rows = _load_csv(csv_path)
    plots_dir.mkdir(parents=True, exist_ok=True)

    workloads = sorted(set(r["workload"] for r in rows))
    metrics = [("bw_MBps", "Bandwidth (MB/s)", "bandwidth"), ("iops", "IOPS", "iops")]

    for workload in workloads:
        wl_rows = _filter_rows(rows, workload=workload)
        if not wl_rows:
            continue

        block_sizes = sorted(set(r["block_size"] for r in wl_rows))
        numjobs_list = sorted(set(r["numjobs"] for r in wl_rows))

        for metric_key, ylabel, file_suffix in metrics:
            fig, ax = plt.subplots(figsize=(10, 6))

            for bs in block_sizes:
                for nj in numjobs_list:
                    series = _filter_rows(wl_rows, block_size=bs, numjobs=nj)
                    if not series:
                        continue
                    series.sort(key=lambda r: r["iodepth"])
                    x = [r["iodepth"] for r in series]
                    y = [r[metric_key] for r in series]
                    label = f"{bs}_nj{nj}"
                    ax.plot(x, y, marker="o", label=label)

            ax.set_xlabel("IO Depth")
            ax.set_ylabel(ylabel)
            ax.set_title(f"{workload} - {ylabel}")
            ax.set_xscale("log", base=2)
            ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left")
            fig.tight_layout()

            out_path = plots_dir / f"{workload}_{file_suffix}.{plot_format}"
            fig.savefig(out_path, dpi=150, bbox_inches="tight")
            plt.close(fig)
            logger.info("Saved plot: %s", out_path.name)


def plot_latency(csv_path: Path, plots_dir: Path, plot_format: str):
    """Generate bar charts with error bars for latency.

    One chart per (workload, block_size).
    X-axis: iodepth. Grouped bars: numjobs. Height: avg latency. Error cap: p99.
    """
    rows = _load_csv(csv_path)
    plots_dir.mkdir(parents=True, exist_ok=True)

    workloads = sorted(set(r["workload"] for r in rows))
    block_sizes = sorted(set(r["block_size"] for r in rows))

    for workload in workloads:
        for bs in block_sizes:
            subset = _filter_rows(rows, workload=workload, block_size=bs)
            if not subset:
                continue

            numjobs_list = sorted(set(r["numjobs"] for r in subset))
            iodepths = sorted(set(r["iodepth"] for r in subset))

            fig, ax = plt.subplots(figsize=(10, 6))
            n_groups = len(iodepths)
            n_bars = len(numjobs_list)
            bar_width = 0.8 / max(n_bars, 1)
            x_indices = np.arange(n_groups)

            for i, nj in enumerate(numjobs_list):
                avg_vals = []
                err_vals = []
                for qd in iodepths:
                    match = _filter_rows(subset, numjobs=nj, iodepth=qd)
                    if match:
                        avg_vals.append(match[0]["lat_avg_us"])
                        # Error bar shows distance from avg to p99
                        err_vals.append(match[0]["lat_p99_us"] - match[0]["lat_avg_us"])
                    else:
                        avg_vals.append(0)
                        err_vals.append(0)

                offset = (i - n_bars / 2 + 0.5) * bar_width
                ax.bar(
                    x_indices + offset,
                    avg_vals,
                    bar_width,
                    yerr=err_vals,
                    capsize=3,
                    label=f"nj{nj}",
                )

            ax.set_xlabel("IO Depth")
            ax.set_ylabel("Latency (us)")
            ax.set_title(f"{workload} - {bs} - Latency (avg + p99 error)")
            ax.set_xticks(x_indices)
            ax.set_xticklabels([str(qd) for qd in iodepths])
            ax.legend()
            fig.tight_layout()

            out_path = plots_dir / f"{workload}_{bs}_latency.{plot_format}"
            fig.savefig(out_path, dpi=150, bbox_inches="tight")
            plt.close(fig)
            logger.info("Saved plot: %s", out_path.name)


def generate_all_plots(csv_path: Path, plots_dir: Path, plot_format: str):
    """Generate all plots from results CSV."""
    plot_bandwidth_iops(csv_path, plots_dir, plot_format)
    plot_latency(csv_path, plots_dir, plot_format)
