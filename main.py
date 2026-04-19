import argparse
import logging
import shutil
from datetime import datetime
from pathlib import Path

from nvme_test.config import load_config
from nvme_test.orchestrator import run_test_plan


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

    config_path = Path(args.config)
    config = load_config(str(config_path))
    logger.info("Loaded config: test_name=%s", config["test_name"])

    test_dir = create_test_dir(config)
    logger.info("Output directory: %s", test_dir)
    shutil.copy2(config_path, test_dir / "config.json")

    summary = run_test_plan(config=config, config_path=config_path, test_dir=test_dir)
    total_jobs = sum(scenario["jobs_total"] for scenario in summary["scenarios"])
    successful_jobs = sum(scenario["jobs_succeeded"] for scenario in summary["scenarios"])

    logger.info("=" * 60)
    logger.info("Test complete!")
    logger.info("  Output directory: %s", test_dir)
    logger.info("  Scenarios: %d", len(summary["scenarios"]))
    logger.info("  Jobs: %d/%d successful", successful_jobs, total_jobs)
    logger.info("  Comparison: %s", summary["comparison"]["status"])
    logger.info("  Total time: %.1f seconds (%.1f minutes)", summary["duration_seconds"], summary["duration_seconds"] / 60)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
