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

NUMERIC_INT_FIELDS = {"numjobs", "iodepth"}
NUMERIC_FLOAT_FIELDS = {"bw_MBps", "iops", "lat_avg_us", "lat_p50_us", "lat_p99_us", "lat_max_us"}
ALL_RESULTS_COLUMNS = ["target_id", "target_label", "target_type"] + CSV_COLUMNS
BEST_POINTS_COLUMNS = ["summary_type"] + ALL_RESULTS_COLUMNS
FIXED_POINTS_COLUMNS = ["point_name"] + ALL_RESULTS_COLUMNS


def parse_fio_json(json_path: Path) -> dict | None:
    """Parse a single fio JSON output file into a result row dict."""
    try:
        with open(json_path) as f:
            data = json.load(f)

        job = data["jobs"][0]
        job_name = job["jobname"]
        parts = job_name.split("_")
        workload = parts[0]
        block_size = parts[1]
        numjobs = int(parts[2][2:])
        iodepth = int(parts[3][2:])

        if workload in ("read", "randread"):
            stats = job["read"]
        else:
            stats = job["write"]

        bw_kbps = stats["bw"]
        bw_MBps = round(bw_kbps / 1024, 2)
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

    except (json.JSONDecodeError, KeyError, IndexError) as exc:
        logger.error("Failed to parse %s: %s", json_path.name, exc)
        return None


def aggregate_results(json_paths: list[Path], csv_dir: Path) -> Path:
    """Parse all fio JSON outputs and write aggregated CSV."""
    rows = []
    for json_path in json_paths:
        row = parse_fio_json(json_path)
        if row is not None:
            rows.append(row)

    rows = _sort_result_rows(rows)
    csv_dir.mkdir(parents=True, exist_ok=True)
    csv_path = csv_dir / "results.csv"
    _write_csv(csv_path, CSV_COLUMNS, rows)
    logger.info("Wrote %d results to %s", len(rows), csv_path)
    return csv_path


def load_results_csv(csv_path: Path) -> list[dict]:
    """Load a results or comparison CSV with numeric type conversion."""
    rows = []
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(_convert_row_types(row))
    return rows


def write_comparison_outputs(
    scenario_results: list[dict],
    comparison_dir: Path,
    fixed_points: list[dict],
    best_points_enabled: bool = True,
) -> dict:
    """Write merged comparison CSV outputs and return their paths."""
    csv_dir = comparison_dir / "csv"
    csv_dir.mkdir(parents=True, exist_ok=True)

    all_rows = []
    included_targets = []
    for scenario in scenario_results:
        included_targets.append(scenario["target_id"])
        for row in scenario["csv_rows"]:
            merged_row = {
                "target_id": scenario["target_id"],
                "target_label": scenario["target_label"],
                "target_type": scenario["target_type"],
            }
            merged_row.update(row)
            all_rows.append(merged_row)

    all_rows.sort(key=_sort_all_results_key)
    all_results_csv = csv_dir / "all_results.csv"
    _write_csv(all_results_csv, ALL_RESULTS_COLUMNS, all_rows)

    best_points_csv = None
    if best_points_enabled and all_rows:
        best_rows = _build_best_points_rows(all_rows)
        best_points_csv = csv_dir / "best_points.csv"
        _write_csv(best_points_csv, BEST_POINTS_COLUMNS, best_rows)
    else:
        best_rows = []

    fixed_rows, missing_fixed_points = _build_fixed_points_rows(all_rows, fixed_points)
    fixed_points_csv = None
    if fixed_rows:
        fixed_points_csv = csv_dir / "fixed_points.csv"
        _write_csv(fixed_points_csv, FIXED_POINTS_COLUMNS, fixed_rows)

    return {
        "all_results_csv": all_results_csv,
        "best_points_csv": best_points_csv,
        "fixed_points_csv": fixed_points_csv,
        "included_targets": included_targets,
        "missing_fixed_points": missing_fixed_points,
        "best_points_rows": best_rows,
        "fixed_points_rows": fixed_rows,
    }


def _convert_row_types(row: dict) -> dict:
    converted = dict(row)
    for field in NUMERIC_INT_FIELDS:
        if field in converted and converted[field] != "":
            converted[field] = int(converted[field])
    for field in NUMERIC_FLOAT_FIELDS:
        if field in converted and converted[field] != "":
            converted[field] = float(converted[field])
    return converted


def _write_csv(path: Path, columns: list[str], rows: list[dict]):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _parse_block_size(value: str) -> int:
    value = value.strip().upper()
    multipliers = {"K": 1024, "M": 1024**2, "G": 1024**3}
    for suffix, multiplier in multipliers.items():
        if value.endswith(suffix):
            return int(value[:-1]) * multiplier
    return int(value)


def _sort_result_rows(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda row: (row["workload"], _parse_block_size(row["block_size"]), row["numjobs"], row["iodepth"]))


def _sort_all_results_key(row: dict) -> tuple:
    return (
        1 if row["target_type"] == "aggregate" else 0,
        row["target_label"],
        row["workload"],
        _parse_block_size(row["block_size"]),
        row["numjobs"],
        row["iodepth"],
    )


def _build_best_points_rows(all_rows: list[dict]) -> list[dict]:
    grouped = {}
    for row in all_rows:
        grouped.setdefault((row["target_id"], row["workload"]), []).append(row)

    best_rows = []
    for rows in grouped.values():
        best_bw = max(rows, key=lambda row: (row["bw_MBps"], -_parse_block_size(row["block_size"]), -row["numjobs"], -row["iodepth"]))
        best_iops = max(rows, key=lambda row: (row["iops"], -_parse_block_size(row["block_size"]), -row["numjobs"], -row["iodepth"]))
        best_latency = min(rows, key=lambda row: (row["lat_avg_us"], _parse_block_size(row["block_size"]), row["numjobs"], row["iodepth"]))
        best_rows.extend([
            _build_summary_row("best_bw", best_bw),
            _build_summary_row("best_iops", best_iops),
            _build_summary_row("best_latency", best_latency),
        ])

    best_rows.sort(key=lambda row: (row["summary_type"], row["workload"], 1 if row["target_type"] == "aggregate" else 0, row["target_label"]))
    return best_rows


def _build_summary_row(summary_type: str, row: dict) -> dict:
    summary_row = {"summary_type": summary_type}
    for column in ALL_RESULTS_COLUMNS:
        summary_row[column] = row[column]
    return summary_row


def _build_fixed_points_rows(all_rows: list[dict], fixed_points: list[dict]) -> tuple[list[dict], list[dict]]:
    fixed_rows = []
    missing = []
    for point in fixed_points:
        for target_id, target_rows in _group_rows_by_target(all_rows).items():
            match = None
            for row in target_rows:
                if (
                    row["workload"] == point["workload"]
                    and row["block_size"] == point["block_size"]
                    and row["numjobs"] == point["numjobs"]
                    and row["iodepth"] == point["iodepth"]
                ):
                    match = row
                    break
            if match is None:
                target_label = target_rows[0]["target_label"] if target_rows else target_id
                missing.append({"point_name": point["name"], "target_id": target_id, "target_label": target_label})
                continue

            fixed_row = {"point_name": point["name"]}
            for column in ALL_RESULTS_COLUMNS:
                fixed_row[column] = match[column]
            fixed_rows.append(fixed_row)

    fixed_rows.sort(key=lambda row: (row["point_name"], 1 if row["target_type"] == "aggregate" else 0, row["target_label"]))
    return fixed_rows, missing


def _group_rows_by_target(rows: list[dict]) -> dict[str, list[dict]]:
    grouped = {}
    for row in rows:
        grouped.setdefault(row["target_id"], []).append(row)
    return grouped
