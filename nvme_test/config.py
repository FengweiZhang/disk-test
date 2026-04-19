import copy
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

DEFAULT_EXECUTION = {
    "run_aggregate": True,
    "run_per_device": False,
    "prepare_mode": "once",
    "comparison_summary": {
        "best_points": False,
        "fixed_points": [],
    },
}

VALID_WORKLOADS = {"read", "write", "randread", "randwrite"}
VALID_PREPARE_MODES = {"once", "per_test"}


def load_config(config_path: str) -> dict:
    """Load, normalize, and validate a JSON config file."""
    path = Path(config_path)
    if not path.exists():
        print(f"Error: Config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    with open(path) as f:
        config = json.load(f)

    _apply_defaults(config)
    _validate(config)
    return config


def _apply_defaults(config: dict):
    """Apply default values for optional config sections."""
    execution = copy.deepcopy(DEFAULT_EXECUTION)
    user_execution = config.get("execution")
    if user_execution is None:
        config["execution"] = execution
        return

    if not isinstance(user_execution, dict):
        _err("Field 'execution' must be dict")

    for key, value in user_execution.items():
        if key == "comparison_summary":
            continue
        execution[key] = value

    comparison_summary = copy.deepcopy(DEFAULT_EXECUTION["comparison_summary"])
    user_summary = user_execution.get("comparison_summary")
    if user_summary is not None:
        if not isinstance(user_summary, dict):
            _err("Field 'execution.comparison_summary' must be dict")
        comparison_summary.update(user_summary)

    execution["comparison_summary"] = comparison_summary
    config["execution"] = execution


def _validate(config: dict):
    """Validate config structure and value constraints. Exits on error."""
    for field, expected_type in REQUIRED_FIELDS.items():
        if field not in config:
            _err(f"Missing required field: '{field}'")
        if not isinstance(config[field], expected_type):
            _err(f"Field '{field}' must be {expected_type.__name__}, got {type(config[field]).__name__}")

    _validate_devices(config["devices"])
    _validate_fio(config["fio"])
    _validate_output(config["output"])
    _validate_execution(config["execution"], config["fio"])


def _validate_devices(devices: dict):
    for field, expected_type in REQUIRED_DEVICE_FIELDS.items():
        if field not in devices:
            _err(f"Missing required field: 'devices.{field}'")
        if not isinstance(devices[field], expected_type):
            _err(f"Field 'devices.{field}' must be {expected_type.__name__}")

    pci_addresses = devices["pci_addresses"]
    if len(pci_addresses) == 0:
        _err("'devices.pci_addresses' must contain at least one address")

    for index, pci_addr in enumerate(pci_addresses):
        if not isinstance(pci_addr, str):
            _err(f"Field 'devices.pci_addresses[{index}]' must be str")

    if devices["use_raid"] and len(pci_addresses) < 2:
        _err("RAID requires at least 2 devices in 'devices.pci_addresses'")


def _validate_fio(fio: dict):
    for field, expected_type in REQUIRED_FIO_FIELDS.items():
        if field not in fio:
            _err(f"Missing required field: 'fio.{field}'")
        if not isinstance(fio[field], expected_type):
            _err(f"Field 'fio.{field}' must be {expected_type.__name__}")

    if not fio["block_sizes"]:
        _err("'fio.block_sizes' must contain at least one value")
    if not fio["numjobs"]:
        _err("'fio.numjobs' must contain at least one value")
    if not fio["iodepth"]:
        _err("'fio.iodepth' must contain at least one value")
    if not fio["workloads"]:
        _err("'fio.workloads' must contain at least one value")

    for wl in fio["workloads"]:
        if wl not in VALID_WORKLOADS:
            _err(f"Invalid workload '{wl}'. Valid: {VALID_WORKLOADS}")

    if fio["runtime"] <= 0:
        _err("'fio.runtime' must be positive")
    if fio["ramp_time"] < 0:
        _err("'fio.ramp_time' must be non-negative")


def _validate_output(output: dict):
    for field, expected_type in REQUIRED_OUTPUT_FIELDS.items():
        if field not in output:
            _err(f"Missing required field: 'output.{field}'")
        if not isinstance(output[field], expected_type):
            _err(f"Field 'output.{field}' must be {expected_type.__name__}")

    if output["plot_format"] not in ("png", "pdf"):
        _err("'output.plot_format' must be 'png' or 'pdf'")


def _validate_execution(execution: dict, fio: dict):
    expected_types = {
        "run_aggregate": bool,
        "run_per_device": bool,
        "prepare_mode": str,
        "comparison_summary": dict,
    }
    for field, expected_type in expected_types.items():
        if field not in execution:
            _err(f"Missing required field: 'execution.{field}'")
        if not isinstance(execution[field], expected_type):
            _err(f"Field 'execution.{field}' must be {expected_type.__name__}")

    if not execution["run_aggregate"] and not execution["run_per_device"]:
        _err("At least one of 'execution.run_aggregate' or 'execution.run_per_device' must be true")

    if execution["prepare_mode"] not in VALID_PREPARE_MODES:
        _err(f"'execution.prepare_mode' must be one of {VALID_PREPARE_MODES}")

    summary = execution["comparison_summary"]
    if "best_points" not in summary or not isinstance(summary["best_points"], bool):
        _err("Field 'execution.comparison_summary.best_points' must be bool")
    if "fixed_points" not in summary or not isinstance(summary["fixed_points"], list):
        _err("Field 'execution.comparison_summary.fixed_points' must be list")

    fixed_names = set()
    for index, point in enumerate(summary["fixed_points"]):
        _validate_fixed_point(point, index, fio, fixed_names)


def _validate_fixed_point(point: dict, index: int, fio: dict, fixed_names: set[str]):
    if not isinstance(point, dict):
        _err(f"Field 'execution.comparison_summary.fixed_points[{index}]' must be dict")

    required = {
        "name": str,
        "workload": str,
        "block_size": str,
        "numjobs": int,
        "iodepth": int,
    }
    for field, expected_type in required.items():
        if field not in point:
            _err(f"Missing required field: 'execution.comparison_summary.fixed_points[{index}].{field}'")
        if not isinstance(point[field], expected_type):
            _err(
                "Field "
                f"'execution.comparison_summary.fixed_points[{index}].{field}' "
                f"must be {expected_type.__name__}"
            )

    point_name = point["name"]
    if point_name in fixed_names:
        _err(f"Duplicate fixed point name '{point_name}'")
    fixed_names.add(point_name)

    if point["workload"] not in fio["workloads"]:
        _err(f"Fixed point '{point_name}' workload '{point['workload']}' is not in 'fio.workloads'")
    if point["block_size"] not in fio["block_sizes"]:
        _err(f"Fixed point '{point_name}' block_size '{point['block_size']}' is not in 'fio.block_sizes'")
    if point["numjobs"] not in fio["numjobs"]:
        _err(f"Fixed point '{point_name}' numjobs '{point['numjobs']}' is not in 'fio.numjobs'")
    if point["iodepth"] not in fio["iodepth"]:
        _err(f"Fixed point '{point_name}' iodepth '{point['iodepth']}' is not in 'fio.iodepth'")


def _err(msg: str):
    print(f"Config error: {msg}", file=sys.stderr)
    sys.exit(1)
