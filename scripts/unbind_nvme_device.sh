#!/bin/bash

# Unbind a PCI NVMe device from its current driver (non-interactive, for programmatic use).
# Stdout: KEY=VALUE results (PREV_DRIVER)
# Stderr: status/progress messages
# Exit 0 on success, non-zero on failure.
#
# Usage: ./unbind_nvme_device.sh [--clear-override] <PCI_BDF>
# Example: ./unbind_nvme_device.sh 0000:e3:00.0
#
# By default a driver_override pin is reported but left intact — the device
# will re-bind to the pinned driver on next probe. Pass --clear-override (or
# CLEAR_DRIVER_OVERRIDE=1) to also clear the pin, leaving the device unbound
# until explicitly re-bound.

set -e

log() { echo "$@" >&2; }

usage() {
    log "Usage: $0 [--clear-override] <PCI_BDF>"
    log "Example: $0 0000:e3:00.0"
    log ""
    log "Options:"
    log "  --clear-override   Also clear a driver_override pin so the device stays"
    log "                     unbound on next probe. Equivalent to CLEAR_DRIVER_OVERRIDE=1."
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
        log "Error: Invalid PCI BDF format. Expected: XXXX:XX:XX.X (e.g., 0000:e3:00.0)"
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

handle_driver_override() {
    local pci_bdf="$1"
    local override_file="/sys/bus/pci/devices/$pci_bdf/driver_override"
    [[ -f "$override_file" ]] || return 0

    local override
    override=$(cat "$override_file")
    if [[ -z "$override" || "$override" == "(null)" ]]; then
        return 0
    fi

    if [[ "$CLEAR_DRIVER_OVERRIDE" == "1" ]]; then
        log "Clearing driver_override pin '$override' for $pci_bdf"
        if ! echo "" > "$override_file" 2>/dev/null; then
            log "Error: Failed to clear driver_override for $pci_bdf"
            exit 1
        fi
        log "driver_override cleared"
    else
        log "Warning: driver_override is pinned to '$override' — device may re-bind on next probe."
        log "         Re-run with --clear-override (or CLEAR_DRIVER_OVERRIDE=1) to prevent that."
    fi
}

unbind_current_driver() {
    local pci_bdf="$1"
    local current_driver="$2"
    if [[ "$current_driver" == "none" ]]; then
        log "Device $pci_bdf is not bound to any driver — nothing to unbind"
        return 0
    fi
    log "Unbinding $pci_bdf from driver: $current_driver"
    if ! echo "$pci_bdf" > "/sys/bus/pci/drivers/$current_driver/unbind" 2>/dev/null; then
        log "Error: Failed to unbind $pci_bdf from $current_driver"
        exit 1
    fi
    log "Unbound from $current_driver"
}

main() {
    CLEAR_DRIVER_OVERRIDE="${CLEAR_DRIVER_OVERRIDE:-0}"
    local pci_bdf=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --clear-override)
                CLEAR_DRIVER_OVERRIDE=1
                shift
                ;;
            -h|--help)
                usage
                ;;
            -*)
                log "Error: Unknown option: $1"
                usage
                ;;
            *)
                pci_bdf="$1"
                shift
                ;;
        esac
    done

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

    unbind_current_driver "$pci_bdf" "$current_driver"
    handle_driver_override "$pci_bdf"

    echo "PREV_DRIVER=$current_driver"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
