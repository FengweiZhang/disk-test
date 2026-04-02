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
