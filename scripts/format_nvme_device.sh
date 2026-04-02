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
    for ns in /sys/class/nvme/"$nvme_dev"/nvme*n*; do
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
