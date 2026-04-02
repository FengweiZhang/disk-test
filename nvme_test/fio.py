import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def generate_job_file(
    workload: str,
    block_size: str,
    numjobs: int,
    iodepth: int,
    device: str,
    fio_cfg: dict,
    output_dir: Path,
) -> Path:
    """Generate a single .fio job file. Returns the path to the created file."""
    job_name = f"{workload}_{block_size}_nj{numjobs}_qd{iodepth}"
    job_path = output_dir / f"{job_name}.fio"

    content = f"""[global]
ioengine={fio_cfg['ioengine']}
direct={fio_cfg['direct']}
runtime={fio_cfg['runtime']}
ramp_time={fio_cfg['ramp_time']}
time_based
group_reporting
size={fio_cfg['size']}

[{job_name}]
rw={workload}
bs={block_size}
numjobs={numjobs}
iodepth={iodepth}
filename={device}
"""
    job_path.write_text(content)
    return job_path


def generate_all_jobs(fio_cfg: dict, device: str, jobs_dir: Path) -> list[Path]:
    """Generate .fio job files for every combination in the test matrix.

    Returns list of paths to job files.
    """
    jobs_dir.mkdir(parents=True, exist_ok=True)
    job_files = []

    for workload in fio_cfg["workloads"]:
        for block_size in fio_cfg["block_sizes"]:
            for numjobs in fio_cfg["numjobs"]:
                for iodepth in fio_cfg["iodepth"]:
                    path = generate_job_file(
                        workload, block_size, numjobs, iodepth,
                        device, fio_cfg, jobs_dir,
                    )
                    job_files.append(path)

    logger.info("Generated %d fio job files in %s", len(job_files), jobs_dir)
    return job_files


def run_fio_job(job_file: Path, raw_output_dir: Path) -> Path | None:
    """Run a single fio job. Returns path to JSON output file, or None on failure."""
    raw_output_dir.mkdir(parents=True, exist_ok=True)
    json_name = job_file.stem + ".json"
    json_path = raw_output_dir / json_name

    cmd = [
        "sudo", "fio", str(job_file),
        "--output-format=json",
        f"--output={json_path}",
    ]
    logger.info("Running: %s", job_file.name)

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        logger.error("fio failed for %s: %s", job_file.name, result.stderr)
        return None

    logger.info("Completed: %s -> %s", job_file.name, json_path.name)
    return json_path


def run_all_jobs(job_files: list[Path], raw_output_dir: Path) -> list[Path]:
    """Run all fio jobs sequentially. Returns list of successful JSON output paths."""
    total = len(job_files)
    json_paths = []

    for i, job_file in enumerate(job_files, 1):
        logger.info("Progress: %d/%d", i, total)
        json_path = run_fio_job(job_file, raw_output_dir)
        if json_path is not None:
            json_paths.append(json_path)

    logger.info("Completed %d/%d fio jobs successfully", len(json_paths), total)
    return json_paths
