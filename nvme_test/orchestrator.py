import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from nvme_test.device import DeviceError, build_aggregate_target, prepare_devices, sanitize_pci, teardown_raid
from nvme_test.fio import generate_all_jobs, run_all_jobs
from nvme_test.plot import generate_all_plots, generate_comparison_plots
from nvme_test.results import aggregate_results, load_results_csv, write_comparison_outputs

logger = logging.getLogger(__name__)


@dataclass
class Scenario:
    scenario_id: str
    target_id: str
    target_label: str
    target_type: str
    output_dir: Path
    pci_addr: str | None = None


def run_test_plan(config: dict, config_path: Path, test_dir: Path) -> dict:
    """Execute all configured test scenarios and write a run summary."""
    del config_path
    start_time = time.time()
    started_at = _timestamp()

    scenarios = _expand_scenarios(config, test_dir)
    scenario_summaries = []
    comparison_inputs = []
    execution_cfg = config["execution"]
    plot_format = config["output"]["plot_format"]
    comparison_info = {
        "status": "skipped",
        "included_targets": [],
        "generated_csv": [],
        "generated_plots": [],
    }

    shared_device_map = None
    if execution_cfg["prepare_mode"] == "once":
        try:
            shared_device_map = prepare_devices(
                pci_addresses=config["devices"]["pci_addresses"],
                format_before_test=config["devices"]["format_before_test"],
            )
        except DeviceError as exc:
            error_message = str(exc)
            for scenario in scenarios:
                scenario_summaries.append(
                    _failed_summary(
                        scenario=scenario,
                        test_dir=test_dir,
                        jobs_total=_expected_job_count(config["fio"]),
                        error_message=error_message,
                    )
                )
            comparison_info["status"] = "failed"
            comparison_info["error_message"] = error_message
            return _finalize_summary(
                config=config,
                test_dir=test_dir,
                started_at=started_at,
                start_time=start_time,
                scenario_summaries=scenario_summaries,
                comparison_info=comparison_info,
            )

    for scenario in scenarios:
        try:
            if execution_cfg["prepare_mode"] == "once":
                device_map = shared_device_map or {}
            else:
                device_map = _prepare_for_scenario(config, scenario)

            scenario_summary = _run_scenario(
                config=config,
                scenario=scenario,
                device_map=device_map,
                plot_format=plot_format,
                test_dir=test_dir,
            )
        except DeviceError as exc:
            scenario_summary = _failed_summary(
                scenario=scenario,
                test_dir=test_dir,
                jobs_total=_expected_job_count(config["fio"]),
                error_message=str(exc),
            )

        scenario_summaries.append(scenario_summary)
        if scenario_summary["status"] in ("success", "partial") and scenario_summary["csv_rows"]:
            comparison_inputs.append(
                {
                    "scenario_id": scenario_summary["scenario_id"],
                    "target_id": scenario_summary["target_id"],
                    "target_label": scenario_summary["target_label"],
                    "target_type": scenario_summary["target_type"],
                    "csv_rows": scenario_summary["csv_rows"],
                }
            )

    comparison_info = _run_comparison_stage(
        config=config,
        test_dir=test_dir,
        scenario_summaries=scenario_summaries,
        comparison_inputs=comparison_inputs,
    )

    return _finalize_summary(
        config=config,
        test_dir=test_dir,
        started_at=started_at,
        start_time=start_time,
        scenario_summaries=scenario_summaries,
        comparison_info=comparison_info,
    )


def _expand_scenarios(config: dict, test_dir: Path) -> list[Scenario]:
    scenarios = []
    execution_cfg = config["execution"]

    if execution_cfg["run_per_device"]:
        for pci_addr in config["devices"]["pci_addresses"]:
            target_id = sanitize_pci(pci_addr)
            scenarios.append(
                Scenario(
                    scenario_id=f"per_device/{target_id}",
                    target_id=target_id,
                    target_label=pci_addr,
                    target_type="device",
                    output_dir=test_dir / "per_device" / target_id,
                    pci_addr=pci_addr,
                )
            )

    if execution_cfg["run_aggregate"]:
        scenarios.append(
            Scenario(
                scenario_id="aggregate",
                target_id="aggregate",
                target_label="aggregate",
                target_type="aggregate",
                output_dir=test_dir / "aggregate",
            )
        )

    return scenarios


def _prepare_for_scenario(config: dict, scenario: Scenario) -> dict[str, str]:
    if scenario.target_type == "device":
        pci_addresses = [scenario.pci_addr]
    else:
        pci_addresses = config["devices"]["pci_addresses"]

    return prepare_devices(
        pci_addresses=pci_addresses,
        format_before_test=config["devices"]["format_before_test"],
    )


def _run_scenario(config: dict, scenario: Scenario, device_map: dict[str, str], plot_format: str, test_dir: Path) -> dict:
    raid_device = None
    jobs_total = 0
    jobs_succeeded = 0
    csv_rows = []
    error_messages = []

    target_device, raid_device = _resolve_target_device(config, scenario, device_map)
    logger.info("Scenario %s target device: %s", scenario.scenario_id, target_device)

    try:
        jobs_dir = scenario.output_dir / "fio_jobs"
        job_files = generate_all_jobs(config["fio"], target_device, jobs_dir)
        jobs_total = len(job_files)

        raw_dir = scenario.output_dir / "fio_raw"
        json_paths = run_all_jobs(job_files, raw_dir)
        jobs_succeeded = len(json_paths)

        csv_dir = scenario.output_dir / "csv"
        csv_path = aggregate_results(json_paths, csv_dir)
        csv_rows = load_results_csv(csv_path)

        plots_dir = scenario.output_dir / "plots"
        try:
            generate_all_plots(csv_path, plots_dir, plot_format)
        except Exception as exc:
            error_messages.append(f"Plot generation failed: {exc}")

        status = _scenario_status(jobs_total=jobs_total, jobs_succeeded=jobs_succeeded, csv_rows=csv_rows, errors=error_messages)
        if not csv_rows:
            error_messages.append("No successful fio results were aggregated")
            status = "failed"

        return {
            "scenario_id": scenario.scenario_id,
            "target_id": scenario.target_id,
            "target_label": scenario.target_label,
            "target_type": scenario.target_type,
            "status": status,
            "jobs_total": jobs_total,
            "jobs_succeeded": jobs_succeeded,
            "csv_path": _rel(csv_path, test_dir),
            "plots_dir": _rel(plots_dir, test_dir),
            "csv_rows": csv_rows,
            **({"error_message": "; ".join(error_messages)} if error_messages else {}),
        }

    finally:
        if raid_device is not None:
            teardown_raid(raid_device)


def _resolve_target_device(config: dict, scenario: Scenario, device_map: dict[str, str]) -> tuple[str, str | None]:
    if scenario.target_type == "device":
        if scenario.pci_addr not in device_map:
            raise DeviceError(f"Prepared device map missing PCI {scenario.pci_addr}")
        return device_map[scenario.pci_addr], None

    return build_aggregate_target(config, device_map)


def _run_comparison_stage(config: dict, test_dir: Path, scenario_summaries: list[dict], comparison_inputs: list[dict]) -> dict:
    comparison_dir = test_dir / "comparison"
    comparison_dir.mkdir(parents=True, exist_ok=True)

    if not comparison_inputs:
        return {
            "status": "skipped",
            "included_targets": [],
            "generated_csv": [],
            "generated_plots": [],
            "error_message": "No successful scenario results available for comparison",
        }

    summary_cfg = config["execution"]["comparison_summary"]
    comparison_outputs = write_comparison_outputs(
        scenario_results=comparison_inputs,
        comparison_dir=comparison_dir,
        fixed_points=summary_cfg["fixed_points"],
        best_points_enabled=summary_cfg["best_points"],
    )

    generated_csv = [_rel(comparison_outputs["all_results_csv"], test_dir)]
    if comparison_outputs["best_points_csv"] is not None:
        generated_csv.append(_rel(comparison_outputs["best_points_csv"], test_dir))
    if comparison_outputs["fixed_points_csv"] is not None:
        generated_csv.append(_rel(comparison_outputs["fixed_points_csv"], test_dir))

    generated_plots = []
    error_messages = []
    try:
        generated_plots = generate_comparison_plots(
            all_results_csv=comparison_outputs["all_results_csv"],
            best_points_csv=comparison_outputs["best_points_csv"],
            fixed_points_csv=comparison_outputs["fixed_points_csv"],
            plots_dir=comparison_dir / "plots",
            plot_format=config["output"]["plot_format"],
        )
    except Exception as exc:
        error_messages.append(f"Comparison plot generation failed: {exc}")

    status = "success" if not error_messages else "partial"
    if not generated_plots and not generated_csv:
        status = "failed"

    info = {
        "status": status,
        "included_targets": comparison_outputs["included_targets"],
        "generated_csv": generated_csv,
        "generated_plots": [_rel(path, test_dir) for path in generated_plots],
    }

    if comparison_outputs["missing_fixed_points"]:
        info["missing_fixed_points"] = comparison_outputs["missing_fixed_points"]
        if status == "success":
            info["status"] = "partial"

    if error_messages:
        info["error_message"] = "; ".join(error_messages)

    return info


def _finalize_summary(
    config: dict,
    test_dir: Path,
    started_at: str,
    start_time: float,
    scenario_summaries: list[dict],
    comparison_info: dict,
) -> dict:
    finished_at = _timestamp()
    duration_seconds = round(time.time() - start_time, 2)
    summary = {
        "test_name": config["test_name"],
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": duration_seconds,
        "prepare_mode": config["execution"]["prepare_mode"],
        "scenarios": [
            {key: value for key, value in scenario.items() if key != "csv_rows"}
            for scenario in scenario_summaries
        ],
        "comparison": comparison_info,
    }

    summary_path = test_dir / "run_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    return summary


def _failed_summary(scenario: Scenario, test_dir: Path, jobs_total: int, error_message: str) -> dict:
    return {
        "scenario_id": scenario.scenario_id,
        "target_id": scenario.target_id,
        "target_label": scenario.target_label,
        "target_type": scenario.target_type,
        "status": "failed",
        "jobs_total": jobs_total,
        "jobs_succeeded": 0,
        "csv_path": _rel(scenario.output_dir / "csv" / "results.csv", test_dir),
        "plots_dir": _rel(scenario.output_dir / "plots", test_dir),
        "csv_rows": [],
        "error_message": error_message,
    }


def _scenario_status(jobs_total: int, jobs_succeeded: int, csv_rows: list[dict], errors: list[str]) -> str:
    if not csv_rows:
        return "failed"
    if errors or jobs_succeeded < jobs_total:
        return "partial"
    return "success"


def _expected_job_count(fio_cfg: dict) -> int:
    return (
        len(fio_cfg["block_sizes"])
        * len(fio_cfg["numjobs"])
        * len(fio_cfg["iodepth"])
        * len(fio_cfg["workloads"])
    )


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()
