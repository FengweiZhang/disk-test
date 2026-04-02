import json
import sys
from pathlib import Path


REQUIRED_FIELDS = {
    "test_name": str,
    "devices": dict,
    "fio": dict,
    "output": dict,
}

REQUIRED_DEVICE_FIELDS = {
    "pci_addresses": list,
    "format_before_test": bool,
    "use_raid": bool,
    "raid_chunk_size": str,
}

REQUIRED_FIO_FIELDS = {
    "block_sizes": list,
    "numjobs": list,
    "iodepth": list,
    "workloads": list,
    "runtime": int,
    "ramp_time": int,
    "direct": int,
    "ioengine": str,
    "size": str,
}

REQUIRED_OUTPUT_FIELDS = {
    "base_dir": str,
    "plot_format": str,
}

VALID_WORKLOADS = {"read", "write", "randread", "randwrite"}


def load_config(config_path: str) -> dict:
    """Load and validate a JSON config file. Returns the config dict or exits on error."""
    path = Path(config_path)
    if not path.exists():
        print(f"Error: Config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    with open(path) as f:
        config = json.load(f)

    _validate(config)
    return config


def _validate(config: dict):
    """Validate config structure and value constraints. Exits on error."""
    # Top-level fields
    for field, expected_type in REQUIRED_FIELDS.items():
        if field not in config:
            _err(f"Missing required field: '{field}'")
        if not isinstance(config[field], expected_type):
            _err(f"Field '{field}' must be {expected_type.__name__}, got {type(config[field]).__name__}")

    # devices section
    devices = config["devices"]
    for field, expected_type in REQUIRED_DEVICE_FIELDS.items():
        if field not in devices:
            _err(f"Missing required field: 'devices.{field}'")
        if not isinstance(devices[field], expected_type):
            _err(f"Field 'devices.{field}' must be {expected_type.__name__}")

    if len(devices["pci_addresses"]) == 0:
        _err("'devices.pci_addresses' must contain at least one address")

    if devices["use_raid"] and len(devices["pci_addresses"]) < 2:
        _err("RAID requires at least 2 devices in 'devices.pci_addresses'")

    # fio section
    fio = config["fio"]
    for field, expected_type in REQUIRED_FIO_FIELDS.items():
        if field not in fio:
            _err(f"Missing required field: 'fio.{field}'")
        if not isinstance(fio[field], expected_type):
            _err(f"Field 'fio.{field}' must be {expected_type.__name__}")

    for wl in fio["workloads"]:
        if wl not in VALID_WORKLOADS:
            _err(f"Invalid workload '{wl}'. Valid: {VALID_WORKLOADS}")

    if fio["runtime"] <= 0:
        _err("'fio.runtime' must be positive")

    # output section
    output = config["output"]
    for field, expected_type in REQUIRED_OUTPUT_FIELDS.items():
        if field not in output:
            _err(f"Missing required field: 'output.{field}'")
        if not isinstance(output[field], expected_type):
            _err(f"Field 'output.{field}' must be {expected_type.__name__}")

    if output["plot_format"] not in ("png", "pdf"):
        _err("'output.plot_format' must be 'png' or 'pdf'")


def _err(msg: str):
    print(f"Config error: {msg}", file=sys.stderr)
    sys.exit(1)
