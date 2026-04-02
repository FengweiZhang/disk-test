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
