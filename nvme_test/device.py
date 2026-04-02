import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def _run_script(script_name: str, args: list[str]) -> str:
    """Run a shell script from the scripts/ directory.

    Returns stdout (KEY=VALUE lines). Logs stderr. Exits on failure.
    """
    script_path = SCRIPTS_DIR / script_name
    cmd = ["sudo", "bash", str(script_path)] + args
    logger.info("Running: %s", " ".join(cmd))

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.stderr:
        for line in result.stderr.strip().splitlines():
            logger.info("[%s] %s", script_name, line)

    if result.returncode != 0:
        logger.error("Script %s failed (exit %d)", script_name, result.returncode)
        sys.exit(1)

    return result.stdout


def _parse_kv(output: str) -> dict[str, str]:
    """Parse KEY=VALUE lines from script stdout."""
    kv = {}
    for line in output.strip().splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            kv[key.strip()] = value.strip()
    return kv


def prepare_device(pci_addr: str, format_before_test: bool) -> str:
    """Prepare a single NVMe device: format or just bind.

    Returns the block device path (e.g., /dev/nvme0n1).
    """
    if format_before_test:
        logger.info("Formatting device at PCI %s", pci_addr)
        output = _run_script("format_nvme_device.sh", [pci_addr])
    else:
        logger.info("Binding device at PCI %s", pci_addr)
        output = _run_script("bind_nvme_device.sh", [pci_addr])

    kv = _parse_kv(output)
    device_path = kv.get("DEVICE_PATH")
    if not device_path:
        logger.error("Script did not return DEVICE_PATH for PCI %s", pci_addr)
        sys.exit(1)

    logger.info("Device ready: %s -> %s", pci_addr, device_path)
    return device_path


def prepare_all_devices(config: dict) -> tuple[str, str | None]:
    """Prepare all devices from config. Returns (test_target_device, raid_device_or_None).

    If use_raid is True, creates a RAID0 array and returns the RAID device path.
    Otherwise returns the single device path.
    """
    devices_cfg = config["devices"]
    pci_addresses = devices_cfg["pci_addresses"]
    format_before_test = devices_cfg["format_before_test"]

    device_paths = []
    for pci_addr in pci_addresses:
        path = prepare_device(pci_addr, format_before_test)
        device_paths.append(path)

    if devices_cfg["use_raid"]:
        raid_device = create_raid(device_paths, devices_cfg["raid_chunk_size"])
        return raid_device, raid_device
    else:
        return device_paths[0], None


def create_raid(device_paths: list[str], chunk_size: str) -> str:
    """Create a RAID0 array from the given device paths. Returns /dev/mdX."""
    logger.info("Creating RAID0 from %s with chunk=%s", device_paths, chunk_size)
    args = ["--chunk", chunk_size] + device_paths
    output = _run_script("raid0_create.sh", args)

    kv = _parse_kv(output)
    raid_device = kv.get("RAID_DEVICE")
    if not raid_device:
        logger.error("raid0_create.sh did not return RAID_DEVICE")
        sys.exit(1)

    logger.info("RAID0 created: %s", raid_device)
    return raid_device


def teardown_raid(raid_device: str):
    """Stop and remove a RAID array."""
    logger.info("Tearing down RAID %s", raid_device)
    _run_script("raid0_delete.sh", [raid_device])
    logger.info("RAID %s removed", raid_device)
