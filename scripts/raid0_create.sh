#!/bin/bash

# Create a RAID 0 array from multiple NVMe devices selected by PCI BDF or block device path.
# Non-interactive, for programmatic use.
# Stdout: KEY=VALUE results (RAID_DEVICE, MEMBER_DEVICES, FILESYSTEM)
# Stderr: status/progress messages
# Exit 0 on success, non-zero on failure.
#
# Usage: ./raid0_create.sh [--chunk SIZE] [--filesystem TYPE|--no-filesystem] [--raid-device /dev/mdX] <PCI_BDF|/dev/nvmeXnY> ...
# Example: ./raid0_create.sh --chunk 256K 0000:50:00.0 0000:51:00.0

set -euo pipefail

log() { echo "$@" >&2; }

CHUNK_SIZE="64K"
FILESYSTEM="ext4"
FORMAT_FILESYSTEM=1
RAID_DEVICE=""
INPUTS=()
DEVICES=()

usage() {
    local status="${1:-1}"
    log "Usage: $0 [--chunk SIZE] [--filesystem TYPE|--no-filesystem] [--raid-device /dev/mdX] <PCI_BDF|/dev/nvmeXnY> ..."
    log "Example: $0 --chunk 256K 0000:50:00.0 0000:51:00.0"
    log "Default chunk size: 64K"
    log "Default filesystem initialization: ext4"
    exit "$status"
}

validate_pci_bdf() {
    local pci_bdf="$1"
    if [[ ! "$pci_bdf" =~ ^[0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-9a-fA-F]$ ]]; then
        log "Error: Invalid PCI BDF format: $pci_bdf"
        log "Expected: XXXX:XX:XX.X (e.g., 0000:50:00.0)"
        exit 1
    fi
}

normalize_pci_bdf() {
    local pci_bdf="$1"
    echo "${pci_bdf,,}"
}

resolve_pci_to_device_path() {
    local pci_bdf="$1"
    pci_bdf=$(normalize_pci_bdf "$pci_bdf")

    validate_pci_bdf "$pci_bdf"

    if [[ ! -d "/sys/bus/pci/devices/$pci_bdf" ]]; then
        log "Error: PCI device $pci_bdf not found in system"
        exit 1
    fi

    local class_file="/sys/bus/pci/devices/$pci_bdf/class"
    if [[ ! -f "$class_file" ]]; then
        log "Error: Cannot read device class for $pci_bdf"
        exit 1
    fi

    local device_class
    device_class=$(<"$class_file")
    if [[ "$device_class" != "0x010802" ]]; then
        log "Error: PCI device $pci_bdf is not an NVMe controller (class: $device_class)"
        exit 1
    fi

    local driver_link="/sys/bus/pci/devices/$pci_bdf/driver"
    if [[ ! -L "$driver_link" || "$(basename "$(readlink "$driver_link")")" != "nvme" ]]; then
        log "Error: PCI device $pci_bdf is not bound to the nvme driver"
        log "Run scripts/bind_nvme_device.sh $pci_bdf first if the device is not ready"
        exit 1
    fi

    local nvme_name=""
    nvme_name=$(find /sys/bus/pci/devices/"$pci_bdf"/nvme -mindepth 1 -maxdepth 1 -name "nvme*" -print -quit 2>/dev/null || true)
    if [[ -z "$nvme_name" ]]; then
        log "Error: Could not resolve NVMe controller for PCI $pci_bdf"
        exit 1
    fi
    nvme_name=$(basename "$nvme_name")

    local ns_name=""
    local ns
    for ns in /sys/class/nvme/"$nvme_name"/nvme*n*; do
        if [[ -d "$ns" ]]; then
            ns_name=$(basename "$ns")
            break
        fi
    done

    if [[ -z "$ns_name" ]]; then
        log "Error: No namespaces found for NVMe controller $nvme_name (PCI $pci_bdf)"
        exit 1
    fi

    echo "/dev/$ns_name"
}

resolve_input_to_device_path() {
    local input="$1"
    if [[ "$input" == /dev/* ]]; then
        echo "$input"
        return
    fi

    resolve_pci_to_device_path "$input"
}

check_filesystem_tool() {
    local filesystem="$1"

    if [[ "$filesystem" == "ext4" ]]; then
        if ! command -v mkfs.ext4 &> /dev/null; then
            log "Error: 'mkfs.ext4' is not installed"
            exit 1
        fi
        return
    fi

    if [[ "$filesystem" == "xfs" ]]; then
        if ! command -v mkfs.xfs &> /dev/null; then
            log "Error: 'mkfs.xfs' is not installed"
            exit 1
        fi
        return
    fi

    if ! command -v mkfs &> /dev/null; then
        log "Error: 'mkfs' is not installed"
        exit 1
    fi
}

format_raid_filesystem() {
    local raid_device="$1"
    local filesystem="$2"

    if [[ "$filesystem" == "ext4" ]]; then
        log "Initializing filesystem on $raid_device: ext4"
        mkfs.ext4 -F "$raid_device" >&2
        return
    fi

    if [[ "$filesystem" == "xfs" ]]; then
        log "Initializing filesystem on $raid_device: xfs"
        mkfs.xfs -f "$raid_device" >&2
        return
    fi

    log "Initializing filesystem on $raid_device: $filesystem"
    mkfs -t "$filesystem" "$raid_device" >&2
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --chunk)
            if [[ $# -lt 2 ]]; then
                log "Error: --chunk requires a value"
                usage
            fi
            CHUNK_SIZE="$2"
            shift 2
            ;;
        --filesystem|--fs)
            if [[ $# -lt 2 ]]; then
                log "Error: $1 requires a value"
                usage
            fi
            FILESYSTEM="$2"
            if [[ "$FILESYSTEM" == "none" ]]; then
                FORMAT_FILESYSTEM=0
            else
                FORMAT_FILESYSTEM=1
            fi
            shift 2
            ;;
        --no-filesystem|--no-mkfs)
            FORMAT_FILESYSTEM=0
            shift
            ;;
        --raid-device|--md)
            if [[ $# -lt 2 ]]; then
                log "Error: $1 requires a value"
                usage
            fi
            RAID_DEVICE="$2"
            shift 2
            ;;
        -h|--help)
            usage 0
            ;;
        --)
            shift
            while [[ $# -gt 0 ]]; do
                INPUTS+=("$1")
                shift
            done
            ;;
        -*)
            log "Error: Unknown option: $1"
            usage
            ;;
        *)
            INPUTS+=("$1")
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

if [[ ${#INPUTS[@]} -lt 2 ]]; then
    log "Error: At least two NVMe devices are required"
    usage
fi

log "Resolving NVMe inputs..."
for input in "${INPUTS[@]}"; do
    device=$(resolve_input_to_device_path "$input")
    DEVICES+=("$device")
    log "Resolved $input -> $device"
done

# Safety checks
log "Running safety checks..."
declare -A SEEN_DEVICES=()
for device in "${DEVICES[@]}"; do
    if [[ ! -b "$device" ]]; then
        log "Error: $device does not exist or is not a block device"
        exit 1
    fi
    if [[ -n "${SEEN_DEVICES[$device]:-}" ]]; then
        log "Error: Duplicate RAID member device: $device"
        exit 1
    fi
    SEEN_DEVICES["$device"]=1
    if findmnt -n --source "$device" --first-only > /dev/null 2>&1; then
        log "Error: $device is currently mounted"
        exit 1
    fi
done
log "Safety checks passed"

if [[ -n "$RAID_DEVICE" ]]; then
    if [[ "$RAID_DEVICE" != /dev/* ]]; then
        RAID_DEVICE="/dev/$RAID_DEVICE"
    fi
    if [[ -e "$RAID_DEVICE" ]]; then
        log "Error: Requested RAID device already exists: $RAID_DEVICE"
        exit 1
    fi
else
    # Find available /dev/mdX
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
fi

log "Creating RAID 0 at $RAID_DEVICE with chunk=$CHUNK_SIZE using ${#DEVICES[@]} devices..."

NUM_DEVICES=${#DEVICES[@]}

if [[ "$FORMAT_FILESYSTEM" -eq 1 ]]; then
    check_filesystem_tool "$FILESYSTEM"
fi

mdadm --create "$RAID_DEVICE" \
      --level=0 \
      --raid-devices=${NUM_DEVICES} \
      "${DEVICES[@]}" \
      --chunk=${CHUNK_SIZE} \
      --run \
      --verbose >&2

log "RAID 0 array created successfully at $RAID_DEVICE"

if command -v udevadm &> /dev/null; then
    udevadm settle >&2 || true
fi

if [[ "$FORMAT_FILESYSTEM" -eq 1 ]]; then
    format_raid_filesystem "$RAID_DEVICE" "$FILESYSTEM"
    log "Filesystem initialized on $RAID_DEVICE: $FILESYSTEM"
else
    FILESYSTEM="none"
    log "Skipping filesystem initialization on $RAID_DEVICE"
fi

# Output machine-parseable result
echo "RAID_DEVICE=$RAID_DEVICE"
echo "MEMBER_DEVICES=${DEVICES[*]}"
echo "FILESYSTEM=$FILESYSTEM"
