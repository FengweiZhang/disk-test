import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


class DeviceError(RuntimeError):
    """Raised when device preparation or RAID lifecycle fails."""


def _run_script(script_name: str, args: list[str]) -> str:
    """Run a shell script from the scripts/ directory and return stdout."""
    script_path = SCRIPTS_DIR / script_name
    cmd = ["sudo", "bash", str(script_path)] + args
    logger.info("Running: %s", " ".join(cmd))

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.stderr:
        for line in result.stderr.strip().splitlines():
            logger.info("[%s] %s", script_name, line)

    if result.returncode != 0:
        raise DeviceError(f"Script {script_name} failed (exit {result.returncode})")

    return result.stdout


def _parse_kv(output: str) -> dict[str, str]:
    """Parse KEY=VALUE lines from script stdout."""
    kv = {}
    for line in output.strip().splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            kv[key.strip()] = value.strip()
    return kv


def sanitize_pci(pci_addr: str) -> str:
    """Convert PCI address to a filesystem-safe identifier."""
    return pci_addr.replace(":", "_").replace(".", "_")


def prepare_device(pci_addr: str, format_before_test: bool) -> str:
    """Prepare a single NVMe device and return its block device path."""
    if format_before_test:
        logger.info("Formatting device at PCI %s", pci_addr)
        output = _run_script("format_nvme_device.sh", [pci_addr])
    else:
        logger.info("Binding device at PCI %s", pci_addr)
        output = _run_script("bind_nvme_device.sh", [pci_addr])

    kv = _parse_kv(output)
    device_path = kv.get("DEVICE_PATH")
    if not device_path:
        raise DeviceError(f"Script did not return DEVICE_PATH for PCI {pci_addr}")

    logger.info("Device ready: %s -> %s", pci_addr, device_path)
    return device_path


def prepare_devices(pci_addresses: list[str], format_before_test: bool) -> dict[str, str]:
    """Prepare multiple NVMe devices and return a PCI-to-device-path map."""
    device_map = {}
    for pci_addr in pci_addresses:
        device_map[pci_addr] = prepare_device(pci_addr, format_before_test)
    return device_map


def build_aggregate_target(config: dict, device_map: dict[str, str]) -> tuple[str, str | None]:
    """Build the aggregate fio target for the configured devices."""
    devices_cfg = config["devices"]
    device_paths = [device_map[pci_addr] for pci_addr in devices_cfg["pci_addresses"]]

    if devices_cfg["use_raid"]:
        raid_device = create_raid(device_paths, devices_cfg["raid_chunk_size"])
        return raid_device, raid_device

    if len(device_paths) > 1:
        target_device = ":".join(device_paths)
        logger.info("Multi-device mode (no RAID): %s", target_device)
        return target_device, None

    return device_paths[0], None


def prepare_all_devices(config: dict) -> tuple[str, str | None]:
    """Backward-compatible helper for the single aggregate target."""
    devices_cfg = config["devices"]
    device_map = prepare_devices(
        pci_addresses=devices_cfg["pci_addresses"],
        format_before_test=devices_cfg["format_before_test"],
    )
    return build_aggregate_target(config, device_map)


def create_raid(device_paths: list[str], chunk_size: str) -> str:
    """Create a RAID0 array from the given device paths."""
    logger.info("Creating RAID0 from %s with chunk=%s", device_paths, chunk_size)
    args = ["--chunk", chunk_size] + device_paths
    output = _run_script("raid0_create.sh", args)

    kv = _parse_kv(output)
    raid_device = kv.get("RAID_DEVICE")
    if not raid_device:
        raise DeviceError("raid0_create.sh did not return RAID_DEVICE")

    logger.info("RAID0 created: %s", raid_device)
    return raid_device


def teardown_raid(raid_device: str):
    """Stop and remove a RAID array."""
    logger.info("Tearing down RAID %s", raid_device)
    _run_script("raid0_delete.sh", [raid_device])
    logger.info("RAID %s removed", raid_device)
