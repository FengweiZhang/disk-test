import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from nvme_test.results import load_results_csv

logger = logging.getLogger(__name__)


def _load_csv(csv_path: Path) -> list[dict]:
    """Load CSV results into list of dicts with numeric conversion."""
    return load_results_csv(csv_path)


def _parse_block_size(s: str) -> int:
    """Convert block size string like '4K', '64K', '1M' to bytes."""
    s = s.strip().upper()
    multipliers = {"K": 1024, "M": 1024**2, "G": 1024**3}
    for suffix, mult in multipliers.items():
        if s.endswith(suffix):
            return int(s[:-1]) * mult
    return int(s)


def _filter_rows(rows: list[dict], **kwargs) -> list[dict]:
    """Filter rows matching all given key=value pairs."""
    result = rows
    for key, value in kwargs.items():
        result = [r for r in result if r[key] == value]
    return result


def plot_bandwidth_iops_by_qd(csv_path: Path, plots_dir: Path, plot_format: str):
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

            out_path = plots_dir / f"{workload}_{file_suffix}_by_qd.{plot_format}"
            fig.savefig(out_path, dpi=150, bbox_inches="tight")
            plt.close(fig)
            logger.info("Saved plot: %s", out_path.name)


def plot_bandwidth_iops_by_bs(csv_path: Path, plots_dir: Path, plot_format: str):
    """Generate line plots for bandwidth and IOPS with block size as X-axis.

    One chart per (workload, metric).
    X-axis: block_size (log2). Lines: each (iodepth, numjobs) combo.
    """
    rows = _load_csv(csv_path)
    plots_dir.mkdir(parents=True, exist_ok=True)

    workloads = sorted(set(r["workload"] for r in rows))
    metrics = [("bw_MBps", "Bandwidth (MB/s)", "bandwidth"), ("iops", "IOPS", "iops")]

    for workload in workloads:
        wl_rows = _filter_rows(rows, workload=workload)
        if not wl_rows:
            continue

        iodepths = sorted(set(r["iodepth"] for r in wl_rows))
        numjobs_list = sorted(set(r["numjobs"] for r in wl_rows))

        for metric_key, ylabel, file_suffix in metrics:
            fig, ax = plt.subplots(figsize=(10, 6))

            for qd in iodepths:
                for nj in numjobs_list:
                    series = _filter_rows(wl_rows, iodepth=qd, numjobs=nj)
                    if not series:
                        continue
                    series.sort(key=lambda r: _parse_block_size(r["block_size"]))
                    x = [_parse_block_size(r["block_size"]) for r in series]
                    y = [r[metric_key] for r in series]
                    label = f"qd{qd}_nj{nj}"
                    ax.plot(x, y, marker="o", label=label)

            ax.set_xlabel("Block Size")
            ax.set_ylabel(ylabel)
            ax.set_title(f"{workload} - {ylabel} (by block size)")
            ax.set_xscale("log", base=2)
            # Use original block size strings as tick labels
            all_bs = sorted(set(r["block_size"] for r in wl_rows),
                            key=_parse_block_size)
            ax.set_xticks([_parse_block_size(bs) for bs in all_bs])
            ax.set_xticklabels(all_bs)
            ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left")
            fig.tight_layout()

            out_path = plots_dir / f"{workload}_{file_suffix}_by_bs.{plot_format}"
            fig.savefig(out_path, dpi=150, bbox_inches="tight")
            plt.close(fig)
            logger.info("Saved plot: %s", out_path.name)


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

            out_path = plots_dir / f"{workload}_{file_suffix}_by_nj.{plot_format}"
            fig.savefig(out_path, dpi=150, bbox_inches="tight")
            plt.close(fig)
            logger.info("Saved plot: %s", out_path.name)


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
                        err_vals.append(max(0, match[0]["lat_p99_us"] - match[0]["lat_avg_us"]))
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
    plot_bandwidth_iops_by_qd(csv_path, plots_dir, plot_format)
    plot_bandwidth_iops_by_bs(csv_path, plots_dir, plot_format)
    plot_bandwidth_iops_by_nj(csv_path, plots_dir, plot_format)
    plot_latency_by_qd(csv_path, plots_dir, plot_format)
    plot_latency_by_bs(csv_path, plots_dir, plot_format)
    plot_latency_by_nj(csv_path, plots_dir, plot_format)


def generate_comparison_plots(
    all_results_csv: Path,
    best_points_csv: Path | None,
    fixed_points_csv: Path | None,
    plots_dir: Path,
    plot_format: str,
) -> list[Path]:
    """Generate compact cross-target comparison overview plots."""
    del all_results_csv
    plots_dir.mkdir(parents=True, exist_ok=True)
    generated = []

    if best_points_csv is not None and best_points_csv.exists():
        best_rows = load_results_csv(best_points_csv)
        generated.extend(_plot_best_point_overviews(best_rows, plots_dir, plot_format))

    if fixed_points_csv is not None and fixed_points_csv.exists():
        fixed_rows = load_results_csv(fixed_points_csv)
        generated.extend(_plot_fixed_point_overviews(fixed_rows, plots_dir, plot_format))

    return generated


def _plot_best_point_overviews(rows: list[dict], plots_dir: Path, plot_format: str) -> list[Path]:
    generated = []
    plot_specs = [
        ("best_bw", "bw_MBps", "Best Bandwidth (MB/s)", "best_bandwidth_overview"),
        ("best_iops", "iops", "Best IOPS", "best_iops_overview"),
        ("best_latency", "lat_avg_us", "Best Avg Latency (us, lower is better)", "best_latency_overview"),
    ]

    for summary_type, metric_key, ylabel, filename in plot_specs:
        subset = [row for row in rows if row["summary_type"] == summary_type]
        if not subset:
            continue

        workloads = sorted(set(row["workload"] for row in subset))
        targets = _sorted_targets(subset)
        fig, ax = plt.subplots(figsize=(10, 6))
        x_indices = np.arange(len(workloads))
        bar_width = 0.8 / max(len(targets), 1)

        for index, target in enumerate(targets):
            values = []
            for workload in workloads:
                match = _find_target_workload_row(subset, target, workload)
                values.append(match[metric_key] if match else 0)
            offset = (index - len(targets) / 2 + 0.5) * bar_width
            ax.bar(x_indices + offset, values, bar_width, label=target)

        ax.set_xlabel("Workload")
        ax.set_ylabel(ylabel)
        ax.set_title(ylabel)
        ax.set_xticks(x_indices)
        ax.set_xticklabels(workloads)
        ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left")
        fig.tight_layout()

        out_path = plots_dir / f"{filename}.{plot_format}"
        fig.savefig(out_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        logger.info("Saved plot: %s", out_path.name)
        generated.append(out_path)

    return generated


def _plot_fixed_point_overviews(rows: list[dict], plots_dir: Path, plot_format: str) -> list[Path]:
    generated = []
    point_names = sorted(set(row["point_name"] for row in rows))
    metrics = [
        ("bw_MBps", "Bandwidth (MB/s)"),
        ("iops", "IOPS"),
        ("lat_avg_us", "Avg Latency (us)"),
    ]

    for point_name in point_names:
        subset = [row for row in rows if row["point_name"] == point_name]
        if not subset:
            continue

        targets = _sorted_targets(subset)
        fig, axes = plt.subplots(1, 3, figsize=(15, 5))

        for ax, (metric_key, ylabel) in zip(axes, metrics):
            values = []
            for target in targets:
                match = _find_target_row(subset, target)
                values.append(match[metric_key] if match else 0)

            ax.bar(np.arange(len(targets)), values)
            ax.set_title(ylabel)
            ax.set_ylabel(ylabel)
            ax.set_xticks(np.arange(len(targets)))
            ax.set_xticklabels(targets, rotation=30, ha="right")
            if metric_key == "lat_avg_us":
                ax.set_title(f"{ylabel} (lower is better)")

        fig.suptitle(f"Fixed Point: {point_name}")
        fig.tight_layout()

        out_path = plots_dir / f"{point_name}_overview.{plot_format}"
        fig.savefig(out_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        logger.info("Saved plot: %s", out_path.name)
        generated.append(out_path)

    return generated


def _sorted_targets(rows: list[dict]) -> list[str]:
    return sorted(
        set(row["target_label"] for row in rows),
        key=lambda target: (1 if target == "aggregate" else 0, target),
    )


def _find_target_workload_row(rows: list[dict], target: str, workload: str) -> dict | None:
    for row in rows:
        if row["target_label"] == target and row["workload"] == workload:
            return row
    return None


def _find_target_row(rows: list[dict], target: str) -> dict | None:
    for row in rows:
        if row["target_label"] == target:
            return row
    return None
