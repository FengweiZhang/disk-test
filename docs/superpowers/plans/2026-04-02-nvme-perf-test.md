# NVMe Performance Test Tool - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python tool that orchestrates NVMe performance testing via fio, collecting bandwidth/IOPS/latency results into CSV and generating plots.

**Architecture:** Modular Python package (`nvme_test/`) with separate modules for config parsing, device management (calling shell scripts via subprocess), fio job generation/execution, result aggregation, and plotting. Shell scripts adapted from Geminifs for non-interactive programmatic use. A `main.py` entry point orchestrates the full pipeline.

**Tech Stack:** Python 3.8+, matplotlib, numpy, fio, bash scripts (format/bind/RAID)

---

## File Structure

| File | Responsibility |
|------|---------------|
| `main.py` | Entry point: parse args, load config, orchestrate full pipeline |
| `nvme_test/__init__.py` | Package marker (empty) |
| `nvme_test/config.py` | Load and validate `config.json` |
| `nvme_test/device.py` | Call shell scripts for format/bind/RAID, parse KEY=VALUE output |
| `nvme_test/fio.py` | Generate `.fio` job files, execute fio, return raw JSON paths |
| `nvme_test/results.py` | Parse fio JSON output files into rows, write CSV |
| `nvme_test/plot.py` | Read CSV, generate bandwidth/IOPS line plots and latency bar charts |
| `scripts/format_nvme_device.sh` | Format NVMe device by PCI address (non-interactive, KEY=VALUE output) |
| `scripts/bind_nvme_device.sh` | Bind PCI device to nvme driver (non-interactive, KEY=VALUE output) |
| `scripts/raid0_create.sh` | Create RAID0 array (non-interactive, KEY=VALUE output) |
| `scripts/raid0_delete.sh` | Stop/remove RAID0 array (non-interactive) |
| `config.json` | Example default configuration |
| `requirements.txt` | Python dependencies |

---

### Task 1: Project scaffolding and config module

**Files:**
- Create: `nvme_test/__init__.py`
- Create: `nvme_test/config.py`
- Create: `config.json`
- Create: `requirements.txt`

- [ ] **Step 1: Create `requirements.txt`**

```
matplotlib
numpy
```

- [ ] **Step 2: Create `nvme_test/__init__.py`**

```python
```

(Empty file, package marker only.)

- [ ] **Step 3: Create example `config.json`**

```json
{
  "test_name": "single_nvme_baseline",
  "devices": {
    "pci_addresses": ["0000:50:00.0"],
    "format_before_test": true,
    "use_raid": false,
    "raid_chunk_size": "64K"
  },
  "fio": {
    "block_sizes": ["4K", "16K", "64K", "256K"],
    "numjobs": [1, 2, 4],
    "iodepth": [1, 4, 16, 32, 64, 128],
    "workloads": ["read", "write", "randread", "randwrite"],
    "runtime": 30,
    "ramp_time": 10,
    "direct": 1,
    "ioengine": "libaio",
    "size": "100%"
  },
  "output": {
    "base_dir": "./output",
    "plot_format": "png"
  }
}
```

- [ ] **Step 4: Create `nvme_test/config.py`**

```python
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
```

- [ ] **Step 5: Commit**

```bash
git add requirements.txt config.json nvme_test/__init__.py nvme_test/config.py
git commit -m "feat: add project scaffolding and config module"
```

---

### Task 2: Shell scripts (adapted for programmatic use)

**Files:**
- Create: `scripts/format_nvme_device.sh`
- Create: `scripts/bind_nvme_device.sh`
- Create: `scripts/raid0_create.sh`
- Create: `scripts/raid0_delete.sh`

These scripts are adapted from the Geminifs originals at `/home/zfw/nvme-over-ub/Geminifs/scripts/`. All interactive prompts are removed, ANSI colors are removed, status messages go to stderr, and machine-parseable `KEY=VALUE` results go to stdout.

- [ ] **Step 1: Create `scripts/bind_nvme_device.sh`**

```bash
#!/bin/bash

# Bind a PCI device to the nvme driver (non-interactive, for programmatic use).
# Stdout: KEY=VALUE results (NVME_DEV, DEVICE_PATH)
# Stderr: status/progress messages
# Exit 0 on success, non-zero on failure.
#
# Usage: ./bind_nvme_device.sh <PCI_BDF>
# Example: ./bind_nvme_device.sh 0000:50:00.0

set -e

log() { echo "$@" >&2; }

usage() {
    log "Usage: $0 <PCI_BDF>"
    log "Example: $0 0000:50:00.0"
    exit 1
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log "Error: This script must be run as root (use sudo)"
        exit 1
    fi
}

validate_pci_bdf() {
    local pci_bdf="$1"
    if [[ ! "$pci_bdf" =~ ^[0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-9a-fA-F]$ ]]; then
        log "Error: Invalid PCI BDF format. Expected: XXXX:XX:XX.X (e.g., 0000:50:00.0)"
        exit 1
    fi
}

check_device_exists() {
    local pci_bdf="$1"
    if [[ ! -d "/sys/bus/pci/devices/$pci_bdf" ]]; then
        log "Error: PCI device $pci_bdf not found in system"
        exit 1
    fi
    log "PCI device $pci_bdf found"
}

get_device_class() {
    local pci_bdf="$1"
    local class_file="/sys/bus/pci/devices/$pci_bdf/class"
    if [[ ! -f "$class_file" ]]; then
        log "Error: Cannot read device class for $pci_bdf"
        exit 1
    fi
    cat "$class_file"
}

is_nvme_device() {
    local pci_bdf="$1"
    local device_class
    device_class=$(get_device_class "$pci_bdf")
    [[ "$device_class" == "0x010802" ]]
}

get_current_driver() {
    local pci_bdf="$1"
    local driver_link="/sys/bus/pci/devices/$pci_bdf/driver"
    if [[ -L "$driver_link" ]]; then
        basename "$(readlink "$driver_link")"
    else
        echo "none"
    fi
}

unbind_current_driver() {
    local pci_bdf="$1"
    local current_driver="$2"
    if [[ "$current_driver" != "none" ]]; then
        log "Unbinding $pci_bdf from current driver: $current_driver"
        echo "$pci_bdf" > "/sys/bus/pci/drivers/$current_driver/unbind"
        log "Unbound from $current_driver"
    fi
}

bind_to_nvme() {
    local pci_bdf="$1"
    log "Binding $pci_bdf to nvme driver..."

    local vendor_id device_id
    vendor_id=$(cat "/sys/bus/pci/devices/$pci_bdf/vendor")
    device_id=$(cat "/sys/bus/pci/devices/$pci_bdf/device")
    vendor_id=${vendor_id#0x}
    device_id=${device_id#0x}

    if ! grep -q "$vendor_id $device_id" /sys/bus/pci/drivers/nvme/new_id 2>/dev/null; then
        echo "$vendor_id $device_id" > /sys/bus/pci/drivers/nvme/new_id 2>/dev/null || true
    fi

    echo "$pci_bdf" > /sys/bus/pci/drivers/nvme/bind
    log "Bound to nvme driver"
}

# Find the /dev/nvmeXnY path for a given PCI BDF after binding.
resolve_device_path() {
    local pci_bdf="$1"

    # Wait briefly for the driver to register the device
    local retries=10
    local nvme_name=""
    for ((i=0; i<retries; i++)); do
        nvme_name=$(find /sys/bus/pci/devices/"$pci_bdf"/nvme -maxdepth 1 -name "nvme*" 2>/dev/null | head -1)
        if [[ -n "$nvme_name" ]]; then
            nvme_name=$(basename "$nvme_name")
            break
        fi
        sleep 0.5
    done

    if [[ -z "$nvme_name" ]]; then
        log "Error: Could not resolve NVMe device name for $pci_bdf"
        exit 1
    fi

    # Find the first namespace
    local ns_name=""
    for ns in /sys/class/nvme/"$nvme_name"/"${nvme_name}"n*; do
        if [[ -d "$ns" ]]; then
            ns_name=$(basename "$ns")
            break
        fi
    done

    if [[ -z "$ns_name" ]]; then
        log "Error: No namespaces found for $nvme_name"
        exit 1
    fi

    echo "NVME_DEV=$nvme_name"
    echo "DEVICE_PATH=/dev/$ns_name"
}

main() {
    local pci_bdf="$1"
    if [[ -z "$pci_bdf" ]]; then
        usage
    fi

    check_root
    validate_pci_bdf "$pci_bdf"
    check_device_exists "$pci_bdf"

    if ! is_nvme_device "$pci_bdf"; then
        local device_class
        device_class=$(get_device_class "$pci_bdf")
        log "Error: Device $pci_bdf is NOT an NVMe device (class: $device_class)"
        exit 1
    fi

    local current_driver
    current_driver=$(get_current_driver "$pci_bdf")
    log "Current driver: $current_driver"

    if [[ "$current_driver" == "nvme" ]]; then
        log "Device already bound to nvme driver"
    else
        unbind_current_driver "$pci_bdf" "$current_driver"
        bind_to_nvme "$pci_bdf"
    fi

    resolve_device_path "$pci_bdf"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
```

- [ ] **Step 2: Create `scripts/format_nvme_device.sh`**

```bash
#!/bin/bash

# Format and sanitize an NVMe device by PCI address (non-interactive, for programmatic use).
# First binds the device to the nvme driver if not already bound, then formats.
# Stdout: KEY=VALUE results (NVME_DEV, DEVICE_PATH)
# Stderr: status/progress messages
# Exit 0 on success, non-zero on failure.
#
# Usage: ./format_nvme_device.sh <PCI_BDF>
# Example: ./format_nvme_device.sh 0000:50:00.0

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log() { echo "$@" >&2; }

usage() {
    log "Usage: $0 <PCI_BDF>"
    log "Example: $0 0000:50:00.0"
    exit 1
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log "Error: This script must be run as root (use sudo)"
        exit 1
    fi
}

check_nvme_cli() {
    if ! command -v nvme &> /dev/null; then
        log "Error: nvme-cli is not installed"
        exit 1
    fi
}

main() {
    local pci_bdf="$1"
    if [[ -z "$pci_bdf" ]]; then
        usage
    fi

    check_root
    check_nvme_cli

    log "=== Formatting NVMe device at PCI $pci_bdf ==="

    # Step 1: Bind device to nvme driver (captures KEY=VALUE output)
    local bind_output
    bind_output=$("$SCRIPT_DIR/bind_nvme_device.sh" "$pci_bdf")

    # Parse the device name from bind output
    local nvme_dev=""
    local device_path=""
    while IFS='=' read -r key value; do
        case "$key" in
            NVME_DEV) nvme_dev="$value" ;;
            DEVICE_PATH) device_path="$value" ;;
        esac
    done <<< "$bind_output"

    if [[ -z "$nvme_dev" || -z "$device_path" ]]; then
        log "Error: Failed to resolve device after binding"
        exit 1
    fi

    log "Device bound: $nvme_dev at $device_path"

    # Step 2: Format each namespace with secure erase
    local dev_path="/dev/$nvme_dev"
    for ns in /sys/class/nvme/"$nvme_dev"/"${nvme_dev}"n*; do
        if [[ -d "$ns" ]]; then
            local ns_name="/dev/$(basename "$ns")"
            log "Formatting $ns_name (this may take a while)..."
            if nvme format "$ns_name" -f --ses=1; then
                log "Formatted $ns_name successfully"
            else
                log "Error: Failed to format $ns_name"
                exit 1
            fi
        fi
    done

    # Output machine-parseable results
    echo "NVME_DEV=$nvme_dev"
    echo "DEVICE_PATH=$device_path"

    log "=== Format completed ==="
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
```

- [ ] **Step 3: Create `scripts/raid0_create.sh`**

```bash
#!/bin/bash

# Create a RAID 0 array from multiple NVMe block devices (non-interactive, for programmatic use).
# Stdout: KEY=VALUE results (RAID_DEVICE)
# Stderr: status/progress messages
# Exit 0 on success, non-zero on failure.
#
# Usage: ./raid0_create.sh [--chunk SIZE] /dev/nvme0n1 /dev/nvme1n1 ...
# Example: ./raid0_create.sh --chunk 256K /dev/nvme0n1 /dev/nvme1n1

set -e

log() { echo "$@" >&2; }

CHUNK_SIZE="64K"
DEVICES=()

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --chunk)
            CHUNK_SIZE="$2"
            shift 2
            ;;
        *)
            DEVICES+=("$1")
            shift
            ;;
    esac
done

if [[ $EUID -ne 0 ]]; then
    log "Error: This script must be run as root (use sudo)"
    exit 1
fi

if ! command -v mdadm &> /dev/null; then
    log "Error: 'mdadm' is not installed"
    exit 1
fi

if [[ ${#DEVICES[@]} -lt 2 ]]; then
    log "Error: At least two block devices are required"
    log "Usage: $0 [--chunk SIZE] /dev/nvme0n1 /dev/nvme1n1 ..."
    exit 1
fi

# Safety checks
log "Running safety checks..."
for device in "${DEVICES[@]}"; do
    if [[ ! -b "$device" ]]; then
        log "Error: $device does not exist or is not a block device"
        exit 1
    fi
    if findmnt -n --source "$device" --first-only > /dev/null 2>&1; then
        log "Error: $device is currently mounted"
        exit 1
    fi
done
log "Safety checks passed"

# Find available /dev/mdX
RAID_DEVICE=""
i=0
while true; do
    if [[ -e "/dev/md${i}" ]]; then
        i=$((i + 1))
        if [[ $i -gt 255 ]]; then
            log "Error: No available /dev/mdX device (0-255 all in use)"
            exit 1
        fi
    else
        RAID_DEVICE="/dev/md${i}"
        break
    fi
done

log "Creating RAID 0 at $RAID_DEVICE with chunk=$CHUNK_SIZE using ${#DEVICES[@]} devices..."

NUM_DEVICES=${#DEVICES[@]}
DEVICE_LIST="${DEVICES[*]}"

mdadm --create "$RAID_DEVICE" \
      --level=0 \
      --raid-devices=${NUM_DEVICES} \
      ${DEVICE_LIST} \
      --chunk=${CHUNK_SIZE} \
      --run \
      --verbose >&2

log "RAID 0 array created successfully at $RAID_DEVICE"

# Output machine-parseable result
echo "RAID_DEVICE=$RAID_DEVICE"
```

- [ ] **Step 4: Create `scripts/raid0_delete.sh`**

```bash
#!/bin/bash

# Stop and remove a software RAID (md) device (non-interactive, for programmatic use).
# Stderr: status/progress messages
# Exit 0 on success, non-zero on failure.
#
# Usage: ./raid0_delete.sh <raid_device>
# Example: ./raid0_delete.sh md0
#          ./raid0_delete.sh /dev/md0

set -e

log() { echo "$@" >&2; }

if [[ $EUID -ne 0 ]]; then
    log "Error: This script must be run as root (use sudo)"
    exit 1
fi

if [[ "$#" -ne 1 ]]; then
    log "Error: Provide a RAID device name as argument"
    log "Usage: $0 <raid_device_name>"
    log "Example: $0 md0"
    exit 1
fi

RAID_INPUT="$1"

# Accept both "md0" and "/dev/md0"
if [[ "$RAID_INPUT" == /dev/* ]]; then
    DEVICE_PATH="$RAID_INPUT"
else
    DEVICE_PATH="/dev/$RAID_INPUT"
fi

if [[ ! -b "$DEVICE_PATH" ]]; then
    log "Error: RAID device $DEVICE_PATH not found"
    exit 1
fi

log "Stopping RAID array $DEVICE_PATH..."

mdadm --stop "$DEVICE_PATH" 2>&1 >&2

log "RAID array $DEVICE_PATH stopped and removed"
```

- [ ] **Step 5: Make scripts executable and commit**

```bash
chmod +x scripts/format_nvme_device.sh scripts/bind_nvme_device.sh scripts/raid0_create.sh scripts/raid0_delete.sh
git add scripts/
git commit -m "feat: add shell scripts adapted for programmatic use"
```

---

### Task 3: Device management module

**Files:**
- Create: `nvme_test/device.py`

- [ ] **Step 1: Create `nvme_test/device.py`**

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add nvme_test/device.py
git commit -m "feat: add device management module"
```

---

### Task 4: Fio job generation and execution module

**Files:**
- Create: `nvme_test/fio.py`

- [ ] **Step 1: Create `nvme_test/fio.py`**

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add nvme_test/fio.py
git commit -m "feat: add fio job generation and execution module"
```

---

### Task 5: Results aggregation module

**Files:**
- Create: `nvme_test/results.py`

- [ ] **Step 1: Create `nvme_test/results.py`**

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add nvme_test/results.py
git commit -m "feat: add results aggregation module"
```

---

### Task 6: Plotting module

**Files:**
- Create: `nvme_test/plot.py`

- [ ] **Step 1: Create `nvme_test/plot.py`**

```python
import csv
import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

logger = logging.getLogger(__name__)


def _load_csv(csv_path: Path) -> list[dict]:
    """Load CSV results into list of dicts with numeric conversion."""
    rows = []
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["numjobs"] = int(row["numjobs"])
            row["iodepth"] = int(row["iodepth"])
            row["bw_MBps"] = float(row["bw_MBps"])
            row["iops"] = float(row["iops"])
            row["lat_avg_us"] = float(row["lat_avg_us"])
            row["lat_p50_us"] = float(row["lat_p50_us"])
            row["lat_p99_us"] = float(row["lat_p99_us"])
            row["lat_max_us"] = float(row["lat_max_us"])
            rows.append(row)
    return rows


def _filter_rows(rows: list[dict], **kwargs) -> list[dict]:
    """Filter rows matching all given key=value pairs."""
    result = rows
    for key, value in kwargs.items():
        result = [r for r in result if r[key] == value]
    return result


def plot_bandwidth_iops(csv_path: Path, plots_dir: Path, plot_format: str):
    """Generate line plots for bandwidth and IOPS.

    One chart per (workload, metric).
    X-axis: iodepth. Lines: each (block_size, numjobs) combo.
    """
    rows = _load_csv(csv_path)
    plots_dir.mkdir(parents=True, exist_ok=True)

    workloads = sorted(set(r["workload"] for r in rows))
    metrics = [("bw_MBps", "Bandwidth (MB/s)", "bandwidth"), ("iops", "IOPS", "iops")]

    for workload in workloads:
        wl_rows = _filter_rows(rows, workload=workload)
        if not wl_rows:
            continue

        block_sizes = sorted(set(r["block_size"] for r in wl_rows))
        numjobs_list = sorted(set(r["numjobs"] for r in wl_rows))

        for metric_key, ylabel, file_suffix in metrics:
            fig, ax = plt.subplots(figsize=(10, 6))

            for bs in block_sizes:
                for nj in numjobs_list:
                    series = _filter_rows(wl_rows, block_size=bs, numjobs=nj)
                    if not series:
                        continue
                    series.sort(key=lambda r: r["iodepth"])
                    x = [r["iodepth"] for r in series]
                    y = [r[metric_key] for r in series]
                    label = f"{bs}_nj{nj}"
                    ax.plot(x, y, marker="o", label=label)

            ax.set_xlabel("IO Depth")
            ax.set_ylabel(ylabel)
            ax.set_title(f"{workload} - {ylabel}")
            ax.set_xscale("log", base=2)
            ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left")
            fig.tight_layout()

            out_path = plots_dir / f"{workload}_{file_suffix}.{plot_format}"
            fig.savefig(out_path, dpi=150, bbox_inches="tight")
            plt.close(fig)
            logger.info("Saved plot: %s", out_path.name)


def plot_latency(csv_path: Path, plots_dir: Path, plot_format: str):
    """Generate bar charts with error bars for latency.

    One chart per (workload, block_size).
    X-axis: iodepth. Grouped bars: numjobs. Height: avg latency. Error cap: p99.
    """
    rows = _load_csv(csv_path)
    plots_dir.mkdir(parents=True, exist_ok=True)

    workloads = sorted(set(r["workload"] for r in rows))
    block_sizes = sorted(set(r["block_size"] for r in rows))

    for workload in workloads:
        for bs in block_sizes:
            subset = _filter_rows(rows, workload=workload, block_size=bs)
            if not subset:
                continue

            numjobs_list = sorted(set(r["numjobs"] for r in subset))
            iodepths = sorted(set(r["iodepth"] for r in subset))

            fig, ax = plt.subplots(figsize=(10, 6))
            n_groups = len(iodepths)
            n_bars = len(numjobs_list)
            bar_width = 0.8 / max(n_bars, 1)
            x_indices = np.arange(n_groups)

            for i, nj in enumerate(numjobs_list):
                avg_vals = []
                err_vals = []
                for qd in iodepths:
                    match = _filter_rows(subset, numjobs=nj, iodepth=qd)
                    if match:
                        avg_vals.append(match[0]["lat_avg_us"])
                        # Error bar shows distance from avg to p99
                        err_vals.append(match[0]["lat_p99_us"] - match[0]["lat_avg_us"])
                    else:
                        avg_vals.append(0)
                        err_vals.append(0)

                offset = (i - n_bars / 2 + 0.5) * bar_width
                ax.bar(
                    x_indices + offset,
                    avg_vals,
                    bar_width,
                    yerr=err_vals,
                    capsize=3,
                    label=f"nj{nj}",
                )

            ax.set_xlabel("IO Depth")
            ax.set_ylabel("Latency (us)")
            ax.set_title(f"{workload} - {bs} - Latency (avg + p99 error)")
            ax.set_xticks(x_indices)
            ax.set_xticklabels([str(qd) for qd in iodepths])
            ax.legend()
            fig.tight_layout()

            out_path = plots_dir / f"{workload}_{bs}_latency.{plot_format}"
            fig.savefig(out_path, dpi=150, bbox_inches="tight")
            plt.close(fig)
            logger.info("Saved plot: %s", out_path.name)


def generate_all_plots(csv_path: Path, plots_dir: Path, plot_format: str):
    """Generate all plots from results CSV."""
    plot_bandwidth_iops(csv_path, plots_dir, plot_format)
    plot_latency(csv_path, plots_dir, plot_format)
```

- [ ] **Step 2: Commit**

```bash
git add nvme_test/plot.py
git commit -m "feat: add plotting module"
```

---

### Task 7: Main entry point

**Files:**
- Create: `main.py`

- [ ] **Step 1: Create `main.py`**

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add main.py
git commit -m "feat: add main entry point orchestrating full test pipeline"
```

---

### Task 8: End-to-end dry run validation

Verify the tool runs correctly in a non-destructive way before real hardware testing.

- [ ] **Step 1: Validate config loading**

```bash
python -c "
from nvme_test.config import load_config
cfg = load_config('config.json')
print('Config loaded OK. Test name:', cfg['test_name'])
print('Test matrix size:', len(cfg['fio']['block_sizes']) * len(cfg['fio']['numjobs']) * len(cfg['fio']['iodepth']) * len(cfg['fio']['workloads']), 'jobs')
"
```

Expected: prints test name and matrix size (288 jobs).

- [ ] **Step 2: Validate fio job file generation**

```bash
python -c "
from pathlib import Path
from nvme_test.fio import generate_all_jobs
import json, tempfile, os

with open('config.json') as f:
    cfg = json.load(f)

with tempfile.TemporaryDirectory() as tmpdir:
    jobs_dir = Path(tmpdir) / 'fio_jobs'
    job_files = generate_all_jobs(cfg['fio'], '/dev/null', jobs_dir)
    print(f'Generated {len(job_files)} job files')
    print('Sample job file:')
    print(job_files[0].read_text())
"
```

Expected: 288 job files generated, sample job file content printed with correct fio format.

- [ ] **Step 3: Validate plotting with synthetic data**

Create a small synthetic CSV and verify plots generate without errors:

```bash
python -c "
import csv, tempfile
from pathlib import Path
from nvme_test.plot import generate_all_plots

# Create synthetic CSV
tmpdir = Path(tempfile.mkdtemp())
csv_path = tmpdir / 'results.csv'
plots_dir = tmpdir / 'plots'

columns = ['workload','block_size','numjobs','iodepth','bw_MBps','iops','lat_avg_us','lat_p50_us','lat_p99_us','lat_max_us']
with open(csv_path, 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=columns)
    w.writeheader()
    for wl in ['read', 'randread']:
        for bs in ['4K', '64K']:
            for nj in [1, 2]:
                for qd in [1, 16, 64]:
                    w.writerow({
                        'workload': wl, 'block_size': bs, 'numjobs': nj, 'iodepth': qd,
                        'bw_MBps': qd * nj * 100, 'iops': qd * nj * 1000,
                        'lat_avg_us': 100 + qd, 'lat_p50_us': 90 + qd,
                        'lat_p99_us': 200 + qd * 2, 'lat_max_us': 500 + qd * 5,
                    })

generate_all_plots(csv_path, plots_dir, 'png')
plots = list(plots_dir.glob('*.png'))
print(f'Generated {len(plots)} plots:')
for p in sorted(plots):
    print(f'  {p.name}')
"
```

Expected: 8 plot files (4 BW/IOPS line plots for 2 workloads + 4 latency bar charts for 2 workloads x 2 block sizes).

- [ ] **Step 4: Commit any fixes from validation, if needed**

```bash
git add -A
git commit -m "fix: address issues found during dry run validation"
```

(Skip this step if no fixes were needed.)
