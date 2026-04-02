import argparse
import json
import logging
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

from nvme_test.config import load_config
from nvme_test.device import prepare_all_devices, teardown_raid
from nvme_test.fio import generate_all_jobs, run_all_jobs
from nvme_test.results import aggregate_results
from nvme_test.plot import generate_all_plots


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def create_test_dir(config: dict) -> Path:
    """Create the timestamped output directory for this test run."""
    base_dir = Path(config["output"]["base_dir"])
    test_name = config["test_name"]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    test_dir = base_dir / f"{test_name}_{timestamp}"
    test_dir.mkdir(parents=True, exist_ok=True)
    return test_dir


def main():
    setup_logging()
    logger = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(description="NVMe Performance Test Tool")
    parser.add_argument(
        "-c", "--config",
        default="config.json",
        help="Path to JSON config file (default: config.json)",
    )
    args = parser.parse_args()

    # Step 1: Load config
    config = load_config(args.config)
    logger.info("Loaded config: test_name=%s", config["test_name"])

    # Step 2: Create output directory
    test_dir = create_test_dir(config)
    logger.info("Output directory: %s", test_dir)

    # Step 3: Copy config for reproducibility
    shutil.copy2(args.config, test_dir / "config.json")

    start_time = time.time()

    # Step 4-5: Prepare devices
    test_device, raid_device = prepare_all_devices(config)
    logger.info("Test target device: %s", test_device)

    try:
        # Step 6: Generate fio jobs
        jobs_dir = test_dir / "fio_jobs"
        job_files = generate_all_jobs(config["fio"], test_device, jobs_dir)

        # Step 7: Run fio jobs
        raw_dir = test_dir / "fio_raw"
        json_paths = run_all_jobs(job_files, raw_dir)

        # Step 8: Aggregate results
        csv_dir = test_dir / "csv"
        csv_path = aggregate_results(json_paths, csv_dir)

        # Step 9: Generate plots
        plots_dir = test_dir / "plots"
        plot_format = config["output"]["plot_format"]
        generate_all_plots(csv_path, plots_dir, plot_format)

    finally:
        # Step 10: RAID teardown
        if raid_device is not None:
            teardown_raid(raid_device)

    # Step 11: Summary
    elapsed = time.time() - start_time
    total_jobs = len(job_files)
    successful = len(json_paths)
    logger.info("=" * 60)
    logger.info("Test complete!")
    logger.info("  Output directory: %s", test_dir)
    logger.info("  Jobs: %d/%d successful", successful, total_jobs)
    logger.info("  Total time: %.1f seconds (%.1f minutes)", elapsed, elapsed / 60)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
