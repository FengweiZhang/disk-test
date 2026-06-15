#!/bin/bash

# Bind a PCI device to the nvme driver (non-interactive, for programmatic use).
# Stdout: KEY=VALUE results (NVME_DEV, DEVICE_PATH)
# Stderr: status/progress messages
# Exit 0 on success, non-zero on failure.
#
# Usage: ./bind_nvme_device.sh [--clear-override] <PCI_BDF>
# Example: ./bind_nvme_device.sh 0000:50:00.0
#
# By default a device pinned via driver_override (e.g. to 'snvme' for GIDS/BaM)
# is reported and left alone. Pass --clear-override (or CLEAR_DRIVER_OVERRIDE=1)
# to clear the pin before binding to nvme.

set -e

log() { echo "$@" >&2; }

usage() {
    log "Usage: $0 [--clear-override] <PCI_BDF>"
    log "Example: $0 0000:50:00.0"
    log ""
    log "Options:"
    log "  --clear-override   Clear a driver_override pin (e.g. 'snvme') before binding."
    log "                     Equivalent to setting CLEAR_DRIVER_OVERRIDE=1."
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
        if ! echo "$pci_bdf" > "/sys/bus/pci/drivers/$current_driver/unbind" 2>/dev/null; then
            log "Error: Failed to unbind $pci_bdf from $current_driver"
            exit 1
        fi
        log "Unbound from $current_driver"
    fi
}

# Inspect driver_override, which can pin the device to a non-nvme driver.
# When driver_override is set (e.g. to 'snvme' for GIDS/BaM), the PCI core
# refuses to bind any other driver and 'echo BDF > nvme/bind' fails with ENODEV.
#
# By default this only reports the pin; it does NOT clear it, so a device
# deliberately handed to GIDS/snvme is not silently stolen back. Set
# CLEAR_DRIVER_OVERRIDE=1 (or pass --clear-override) to opt into clearing.
handle_driver_override() {
    local pci_bdf="$1"
    local override_file="/sys/bus/pci/devices/$pci_bdf/driver_override"
    [[ -f "$override_file" ]] || return 0

    local override
    override=$(cat "$override_file")
    # An empty / "(null)" override means no pin is in effect.
    if [[ -z "$override" || "$override" == "(null)" ]]; then
        return 0
    fi

    if [[ "$CLEAR_DRIVER_OVERRIDE" == "1" ]]; then
        log "Device $pci_bdf has driver_override pinned to '$override'; clearing it (CLEAR_DRIVER_OVERRIDE=1)"
        if ! echo "" > "$override_file" 2>/dev/null; then
            log "Error: Failed to clear driver_override for $pci_bdf"
            exit 1
        fi
    else
        log "Error: Device $pci_bdf has driver_override pinned to '$override'"
        log "       The PCI core will reject binding to nvme while this pin is set."
        log "       Re-run with --clear-override (or CLEAR_DRIVER_OVERRIDE=1) to clear it."
        exit 1
    fi
}

bind_to_nvme() {
    local pci_bdf="$1"
    log "Binding $pci_bdf to nvme driver..."

    handle_driver_override "$pci_bdf"

    local vendor_id device_id
    vendor_id=$(cat "/sys/bus/pci/devices/$pci_bdf/vendor")
    device_id=$(cat "/sys/bus/pci/devices/$pci_bdf/device")
    vendor_id=${vendor_id#0x}
    device_id=${device_id#0x}

    if ! grep -q "$vendor_id $device_id" /sys/bus/pci/drivers/nvme/new_id 2>/dev/null; then
        echo "$vendor_id $device_id" > /sys/bus/pci/drivers/nvme/new_id 2>/dev/null || true
    fi

    # Capture the kernel's error instead of letting 'set -e' abort silently.
    # The command group keeps echo's stdout going to the sysfs file while the
    # outer 2>&1 routes bash's write error to the command substitution.
    local bind_err
    if ! bind_err=$( { echo "$pci_bdf" > /sys/bus/pci/drivers/nvme/bind; } 2>&1 ); then
        log "Error: Failed to bind $pci_bdf to nvme driver: ${bind_err:-write to nvme/bind failed}"
        log "Hint: a stale driver_override or another driver (e.g. snvme) still claiming the device"
        log "      can cause an ENODEV ('No such device') on bind. Current driver: $(get_current_driver "$pci_bdf")"
        exit 1
    fi
    log "Bound to nvme driver"
}

# Find the /dev/nvmeXnY path for a given PCI BDF after binding.
resolve_device_path() {
    local pci_bdf="$1"

    # Wait briefly for the driver to register the device AND at least one
    # namespace. After bind, the kernel creates the controller (nvmeX) first
    # and the namespace (nvmeXnY) slightly later, asynchronously. Retrying only
    # the controller lookup races the namespace creation, so we poll for both
    # together here.
    local retries=10
    local nvme_name=""
    local ns_name=""
    for ((i=0; i<retries; i++)); do
        nvme_name=$(find /sys/bus/pci/devices/"$pci_bdf"/nvme -mindepth 1 -maxdepth 1 -name "nvme*" 2>/dev/null | head -1)
        if [[ -n "$nvme_name" ]]; then
            nvme_name=$(basename "$nvme_name")
            # Find the first namespace (name may not follow <ctrl>nX pattern,
            # e.g. nvme5n3 under nvme3).
            for ns in /sys/class/nvme/"$nvme_name"/nvme*n*; do
                if [[ -d "$ns" ]]; then
                    ns_name=$(basename "$ns")
                    break
                fi
            done
            [[ -n "$ns_name" ]] && break
        fi
        sleep 0.5
    done

    if [[ -z "$nvme_name" ]]; then
        log "Error: Could not resolve NVMe device name for $pci_bdf"
        exit 1
    fi

    if [[ -z "$ns_name" ]]; then
        log "Error: No namespaces found for $nvme_name"
        exit 1
    fi

    echo "NVME_DEV=$nvme_name"
    echo "DEVICE_PATH=/dev/$ns_name"
}

main() {
    # Parse options. CLEAR_DRIVER_OVERRIDE may also be set in the environment.
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
