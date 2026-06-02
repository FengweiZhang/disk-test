#!/bin/bash

# Stop and remove a software RAID (md) device selected by md device, PCI BDF, or member block device.
# Non-interactive, for programmatic use.
# Stderr: status/progress messages
# Exit 0 on success, non-zero on failure.
#
# Usage: ./raid0_delete.sh [--no-zero-superblock] <raid_device|PCI_BDF|/dev/nvmeXnY> [...]
# Example: ./raid0_delete.sh md0
#          ./raid0_delete.sh /dev/md0
#          ./raid0_delete.sh 0000:50:00.0 0000:51:00.0

set -euo pipefail

log() { echo "$@" >&2; }

ZERO_SUPERBLOCK=1
INPUTS=()
RAID_DEVICES=()
MEMBER_DEVICES=()

usage() {
    local status="${1:-1}"
    log "Usage: $0 [--no-zero-superblock] <raid_device|PCI_BDF|/dev/nvmeXnY> [...]"
    log "Example: $0 md0"
    log "         $0 /dev/md0"
    log "         $0 0000:50:00.0 0000:51:00.0"
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

canonical_block_device() {
    local device="$1"
    if [[ ! -b "$device" ]]; then
        log "Error: $device does not exist or is not a block device"
        exit 1
    fi
    readlink -f "$device"
}

is_md_device() {
    local device="$1"
    local base
    base=$(basename "$(canonical_block_device "$device")")
    [[ -d "/sys/class/block/$base/md" ]]
}

add_unique() {
    local value="$1"
    shift
    local existing
    for existing in "$@"; do
        if [[ "$existing" == "$value" ]]; then
            return
        fi
    done
    echo "$value"
}

add_raid_device() {
    local raid_device="$1"
    local unique
    unique=$(add_unique "$raid_device" "${RAID_DEVICES[@]}")
    if [[ -n "$unique" ]]; then
        RAID_DEVICES+=("$unique")
    fi
}

add_member_device() {
    local member_device="$1"
    local unique
    unique=$(add_unique "$member_device" "${MEMBER_DEVICES[@]}")
    if [[ -n "$unique" ]]; then
        MEMBER_DEVICES+=("$unique")
    fi
}

resolve_input() {
    local input="$1"
    local device_path

    if [[ "$input" == /dev/* ]]; then
        device_path=$(canonical_block_device "$input")
        if is_md_device "$device_path"; then
            add_raid_device "$device_path"
        else
            add_member_device "$device_path"
        fi
        return
    fi

    if [[ "$input" =~ ^md[0-9]+$ ]]; then
        device_path=$(canonical_block_device "/dev/$input")
        add_raid_device "$device_path"
        return
    fi

    device_path=$(resolve_pci_to_device_path "$input")
    device_path=$(canonical_block_device "$device_path")
    add_member_device "$device_path"
}

find_member_holder_raids() {
    local member_device="$1"
    local base
    base=$(basename "$member_device")

    local holder
    for holder in /sys/class/block/"$base"/holders/md*; do
        if [[ -d "$holder" ]]; then
            echo "/dev/$(basename "$holder")"
        fi
    done
}

collect_raid_members() {
    local raid_device="$1"
    local base
    base=$(basename "$(canonical_block_device "$raid_device")")

    local slave
    for slave in /sys/class/block/"$base"/slaves/*; do
        if [[ -e "$slave" ]]; then
            add_member_device "/dev/$(basename "$slave")"
        fi
    done
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --zero-superblock)
            ZERO_SUPERBLOCK=1
            shift
            ;;
        --no-zero-superblock)
            ZERO_SUPERBLOCK=0
            shift
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

if [[ ${#INPUTS[@]} -lt 1 ]]; then
    log "Error: Provide a RAID device, PCI BDF, or member block device"
    usage
fi

if [[ $EUID -ne 0 ]]; then
    log "Error: This script must be run as root (use sudo)"
    exit 1
fi

if ! command -v mdadm &> /dev/null; then
    log "Error: 'mdadm' is not installed"
    exit 1
fi

for input in "${INPUTS[@]}"; do
    resolve_input "$input"
done

for member_device in "${MEMBER_DEVICES[@]}"; do
    log "Resolving RAID array for member $member_device..."
    found=0
    while IFS= read -r raid_device; do
        if [[ -n "$raid_device" ]]; then
            add_raid_device "$raid_device"
            found=1
        fi
    done < <(find_member_holder_raids "$member_device")

    if [[ "$found" -eq 0 ]]; then
        log "Error: No active md RAID array found for member $member_device"
        exit 1
    fi
done

if [[ ${#RAID_DEVICES[@]} -lt 1 ]]; then
    log "Error: No RAID devices resolved from input"
    exit 1
fi

if [[ ${#MEMBER_DEVICES[@]} -gt 0 && ${#RAID_DEVICES[@]} -gt 1 ]]; then
    log "Error: Member inputs resolve to multiple RAID arrays: ${RAID_DEVICES[*]}"
    exit 1
fi

if [[ "$ZERO_SUPERBLOCK" -eq 1 ]]; then
    for raid_device in "${RAID_DEVICES[@]}"; do
        collect_raid_members "$raid_device"
    done
fi

for raid_device in "${RAID_DEVICES[@]}"; do
    if [[ ! -b "$raid_device" ]]; then
        log "Error: RAID device $raid_device not found"
        exit 1
    fi

    if ! is_md_device "$raid_device"; then
        log "Error: $raid_device is not an md RAID device"
        exit 1
    fi

    log "Stopping RAID array $raid_device..."
    mdadm --stop "$raid_device" >&2
    log "RAID array $raid_device stopped and removed"
done

if [[ "$ZERO_SUPERBLOCK" -eq 1 ]]; then
    for member_device in "${MEMBER_DEVICES[@]}"; do
        log "Zeroing md superblock on $member_device..."
        mdadm --zero-superblock "$member_device" >&2
    done
fi
