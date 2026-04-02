import csv
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

CSV_COLUMNS = [
    "workload",
    "block_size",
    "numjobs",
    "iodepth",
    "bw_MBps",
    "iops",
    "lat_avg_us",
    "lat_p50_us",
    "lat_p99_us",
    "lat_max_us",
]


def parse_fio_json(json_path: Path) -> dict | None:
    """Parse a single fio JSON output file into a result row dict.

    Returns None if parsing fails.
    """
    try:
        with open(json_path) as f:
            data = json.load(f)

        job = data["jobs"][0]
        job_name = job["jobname"]

        # Parse job_name: <workload>_<bs>_nj<numjobs>_qd<iodepth>
        # "randread_4K_nj1_qd32" -> ["randread", "4K", "nj1", "qd32"]
        parts = job_name.split("_")
        # Workloads like "randread" stay as one token after split
        workload = parts[0]
        block_size = parts[1]
        numjobs = int(parts[2][2:])   # "nj1" -> 1
        iodepth = int(parts[3][2:])   # "qd32" -> 32

        # Select read or write stats based on workload type
        if workload in ("read", "randread"):
            stats = job["read"]
        else:
            stats = job["write"]

        bw_KBps = stats["bw"]  # fio reports bw in KB/s
        bw_MBps = round(bw_KBps / 1024, 2)
        iops = round(stats["iops"], 2)

        clat = stats["clat_ns"]
        lat_avg_us = round(clat["mean"] / 1000, 2)
        lat_max_us = round(clat["max"] / 1000, 2)

        percentiles = clat.get("percentile", {})
        lat_p50_us = round(percentiles.get("50.000000", 0) / 1000, 2)
        lat_p99_us = round(percentiles.get("99.000000", 0) / 1000, 2)

        return {
            "workload": workload,
            "block_size": block_size,
            "numjobs": numjobs,
            "iodepth": iodepth,
            "bw_MBps": bw_MBps,
            "iops": iops,
            "lat_avg_us": lat_avg_us,
            "lat_p50_us": lat_p50_us,
            "lat_p99_us": lat_p99_us,
            "lat_max_us": lat_max_us,
        }

    except (json.JSONDecodeError, KeyError, IndexError) as e:
        logger.error("Failed to parse %s: %s", json_path.name, e)
        return None


def aggregate_results(json_paths: list[Path], csv_dir: Path) -> Path:
    """Parse all fio JSON outputs and write aggregated CSV.

    Returns path to the written CSV file.
    """
    csv_dir.mkdir(parents=True, exist_ok=True)
    csv_path = csv_dir / "results.csv"

    rows = []
    for json_path in json_paths:
        row = parse_fio_json(json_path)
        if row is not None:
            rows.append(row)

    # Sort by workload, block_size, numjobs, iodepth for readability
    rows.sort(key=lambda r: (r["workload"], r["block_size"], r["numjobs"], r["iodepth"]))

    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    logger.info("Wrote %d results to %s", len(rows), csv_path)
    return csv_path
