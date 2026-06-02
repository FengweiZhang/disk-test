#!/bin/bash

# Generate a read-only NVMe status report for a controller selected by PCI BDF.
#
# Usage: sudo ./nvme_status_report.sh [OPTIONS] <PCI_BDF>
# Example: sudo ./nvme_status_report.sh --health --errors 0000:50:00.0

set -u
set -o pipefail

log() { echo "$@" >&2; }

usage() {
    local exit_code="${1:-1}"
    log "Usage: $0 [OPTIONS] <PCI_BDF>"
    log "Example: $0 --health --errors 0000:50:00.0"
    log ""
    log "Options:"
    log "  --health    Include SMART / health log"
    log "  --errors    Include error log"
    log "  --features  Include feature probes"
    log "  --full      Include full raw nvme-cli output"
    log "  -h, --help  Show this help"
    exit "$exit_code"
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

check_nvme_pci_device() {
    local pci_bdf="$1"
    local class_file="/sys/bus/pci/devices/$pci_bdf/class"
    local device_class="unknown"
    if [[ -f "$class_file" ]]; then
        device_class=$(cat "$class_file")
    fi

    if [[ "$device_class" != "0x010802" ]]; then
        log "Error: PCI device $pci_bdf is not an NVMe controller (class: $device_class)"
        exit 1
    fi

    local current_driver
    current_driver=$(get_current_driver "$pci_bdf")
    if [[ "$current_driver" != "nvme" ]]; then
        log "Error: PCI device $pci_bdf is bound to '$current_driver', not 'nvme'"
        log "Hint: bind it first with scripts/bind_nvme_device.sh if appropriate."
        exit 1
    fi
}

resolve_nvme_controller() {
    local pci_bdf="$1"
    local nvme_dir="/sys/bus/pci/devices/$pci_bdf/nvme"

    if [[ ! -d "$nvme_dir" ]]; then
        log "Error: Could not find NVMe controller under $nvme_dir"
        exit 1
    fi

    local ctrl_path=""
    ctrl_path=$(find "$nvme_dir" -mindepth 1 -maxdepth 1 -name 'nvme*' -print 2>/dev/null | sort | head -1)
    if [[ -z "$ctrl_path" ]]; then
        log "Error: Could not resolve NVMe controller for $pci_bdf"
        exit 1
    fi

    basename "$ctrl_path"
}

collect_namespaces() {
    local nvme_dev="$1"
    local ns_dir

    for ns_dir in /sys/class/nvme/"$nvme_dev"/nvme*n*; do
        if [[ -d "$ns_dir" ]]; then
            basename "$ns_dir"
        fi
    done | sort
}

parse_args() {
    SHOW_HEALTH=0
    SHOW_ERRORS=0
    SHOW_FEATURES=0
    SHOW_FULL=0
    PCI_BDF=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --health)
                SHOW_HEALTH=1
                ;;
            --errors)
                SHOW_ERRORS=1
                ;;
            --features)
                SHOW_FEATURES=1
                ;;
            --full)
                SHOW_FULL=1
                ;;
            -h|--help)
                usage 0
                ;;
            --)
                shift
                break
                ;;
            -*)
                log "Error: Unknown option: $1"
                usage 1
                ;;
            *)
                if [[ -n "$PCI_BDF" ]]; then
                    log "Error: Multiple PCI BDF values provided"
                    usage 1
                fi
                PCI_BDF="$1"
                ;;
        esac
        shift
    done

    if [[ -z "$PCI_BDF" && $# -gt 0 ]]; then
        PCI_BDF="$1"
        shift
    fi

    if [[ -n "$PCI_BDF" && $# -gt 0 ]]; then
        log "Error: Too many positional arguments"
        usage 1
    fi

    if [[ -z "$PCI_BDF" ]]; then
        usage 1
    fi
}

print_selected_lines() {
    local title="$1"
    shift
    local output="$1"
    shift
    local prefixes=("$@")
    local prefix
    local printed=0

    section "$title"
    for prefix in "${prefixes[@]}"; do
        while IFS= read -r line; do
            if [[ -n "$line" ]]; then
                printf '%s\n' "$line"
                printed=1
            fi
        done < <(printf '%s\n' "$output" | awk -v prefix="$prefix" '$0 ~ "^" prefix "([[:space:]]|:)" { print }')
    done

    if [[ $printed -eq 0 ]]; then
        printf '[WARN] No matching fields found.\n'
    fi
}

print_command_output() {
    local title="$1"
    shift
    local output
    if output=$("$@" 2>&1); then
        section "$title"
        printf '%s\n' "$output"
    else
        section "$title"
        printf '%s\n' "$output"
        printf '\n[WARN] Command failed.\n'
    fi
}

section() {
    local title="$1"
    printf '\n'
    printf '================================================================================\n'
    printf '%s\n' "$title"
    printf '================================================================================\n'
}

run_section() {
    local title="$1"
    shift

    section "$title"
    printf '$'
    printf ' %q' "$@"
    printf '\n\n'

    if ! "$@"; then
        printf '\n[WARN] Command failed:'
        printf ' %q' "$@"
        printf '\n'
    fi
}

print_file_value() {
    local label="$1"
    local path="$2"
    local value="N/A"

    if [[ -r "$path" ]]; then
        value=$(cat "$path")
    fi
    printf '%-24s %s\n' "$label:" "$value"
}

print_sysfs_summary() {
    local pci_bdf="$1"
    local nvme_dev="$2"
    shift 2
    local namespaces=("$@")

    section "PCI and sysfs summary"
    printf '%-24s %s\n' "PCI BDF:" "$pci_bdf"
    printf '%-24s %s\n' "Driver:" "$(get_current_driver "$pci_bdf")"
    printf '%-24s %s\n' "Controller:" "/dev/$nvme_dev"
    if [[ ${#namespaces[@]} -gt 0 ]]; then
        local ns_paths=()
        local ns
        for ns in "${namespaces[@]}"; do
            ns_paths+=("/dev/$ns")
        done
        printf '%-24s %s\n' "Namespaces:" "${ns_paths[*]}"
    else
        printf '%-24s %s\n' "Namespaces:" "none"
    fi
    print_file_value "PCI class" "/sys/bus/pci/devices/$pci_bdf/class"
    print_file_value "Vendor ID" "/sys/bus/pci/devices/$pci_bdf/vendor"
    print_file_value "Device ID" "/sys/bus/pci/devices/$pci_bdf/device"
    print_file_value "Subsystem vendor ID" "/sys/bus/pci/devices/$pci_bdf/subsystem_vendor"
    print_file_value "Subsystem device ID" "/sys/bus/pci/devices/$pci_bdf/subsystem_device"
    print_file_value "NUMA node" "/sys/bus/pci/devices/$pci_bdf/numa_node"
}

print_feature() {
    local dev_path="$1"
    local fid="$2"
    local name="$3"
    local output

    printf '\n--- Feature %s: %s ---\n' "$fid" "$name"
    if output=$(nvme get-feature "$dev_path" -f "$fid" -H 2>&1); then
        printf '%s\n' "$output"
    else
        printf '[Unavailable] %s\n' "$output"
    fi
}

print_features() {
    local dev_path="$1"

    section "NVMe get-feature probes"
    printf 'Unsupported or vendor-restricted features are reported as unavailable.\n'

    print_feature "$dev_path" 0x01 "Arbitration"
    print_feature "$dev_path" 0x02 "Power Management"
    print_feature "$dev_path" 0x04 "Temperature Threshold"
    print_feature "$dev_path" 0x05 "Error Recovery"
    print_feature "$dev_path" 0x06 "Volatile Write Cache"
    print_feature "$dev_path" 0x07 "Number of Queues"
    print_feature "$dev_path" 0x08 "Interrupt Coalescing"
    print_feature "$dev_path" 0x09 "Interrupt Vector Configuration"
    print_feature "$dev_path" 0x0a "Write Atomicity Normal"
    print_feature "$dev_path" 0x0b "Asynchronous Event Configuration"
    print_feature "$dev_path" 0x0c "Autonomous Power State Transition"
    print_feature "$dev_path" 0x0d "Host Memory Buffer"
    print_feature "$dev_path" 0x0e "Timestamp"
    print_feature "$dev_path" 0x0f "Keep Alive Timer"
    print_feature "$dev_path" 0x10 "Host Controlled Thermal Management"
    print_feature "$dev_path" 0x11 "Non-Operational Power State Config"
}

print_nvme_list_summary() {
    local namespaces=("$@")
    local output=""
    local line
    local matched=0

    if ! output=$(nvme list 2>&1); then
        section "NVMe list summary"
        printf '%s\n' "$output"
        printf '\n[WARN] nvme list failed.\n'
        return
    fi

    section "NVMe list summary"
    printf '%s\n' "$output" | awk 'NR<=2 { print }'
    for line in "${namespaces[@]}"; do
        if printf '%s\n' "$output" | grep -F -- "$line" >/dev/null 2>&1; then
            printf '%s\n' "$output" | grep -F -- "$line"
            matched=1
        fi
    done

    if [[ $matched -eq 0 ]]; then
        printf '[WARN] No matching namespace rows found in nvme list.\n'
    fi
}

print_id_ctrl_summary() {
    local dev_path="$1"
    local output=""
    if ! output=$(nvme id-ctrl "$dev_path" 2>&1); then
        section "Controller summary: $dev_path"
        printf '%s\n' "$output"
        printf '\n[WARN] nvme id-ctrl failed.\n'
        return
    fi

    print_selected_lines "Controller summary: $dev_path" "$output" \
        "vid" "ssvid" "sn" "mn" "fr" "rab" "ieee" "cmic" "mdts" "ver" \
        "oaes" "ctratt" "oacs" "acl" "aerl" "frmw" "lpa" "elpe" "npss" \
        "apsta" "wctemp" "cctemp" "tnvmcap" "unvmcap" "oncs" "fuses" \
        "fna" "vwc" "awun" "awupf" "sqes" "cqes" "nn" "sgls"
}

print_id_ns_summary() {
    local ns_path="$1"
    local output=""
    if ! output=$(nvme id-ns "$ns_path" 2>&1); then
        section "Namespace summary: $ns_path"
        printf '%s\n' "$output"
        printf '\n[WARN] nvme id-ns failed.\n'
        return
    fi

    print_selected_lines "Namespace summary: $ns_path" "$output" \
        "nsze" "ncap" "nuse" "nsfeat" "nlbaf" "flbas" "mc" "dpc" "dps" \
        "nmic" "rescap" "fpi" "dlfeat" "nawun" "nawupf" "nacwu" "nabsn" \
        "nabo" "nabspf" "noiob" "nvmsetid" "endgid" "lbaf"
}

main() {
    parse_args "$@"
    local pci_bdf="$PCI_BDF"
    validate_pci_bdf "$pci_bdf"
    check_root
    check_nvme_cli
    check_device_exists "$pci_bdf"
    check_nvme_pci_device "$pci_bdf"

    local nvme_dev
    nvme_dev=$(resolve_nvme_controller "$pci_bdf")
    local dev_path="/dev/$nvme_dev"

    if [[ ! -e "$dev_path" ]]; then
        log "Error: Controller device $dev_path does not exist"
        exit 1
    fi

    local namespaces=()
    mapfile -t namespaces < <(collect_namespaces "$nvme_dev")

    section "NVMe status report"
    printf '%-24s %s\n' "Generated at:" "$(date -Is)"
    printf '%-24s %s\n' "Host:" "$(hostname)"
    printf '%-24s %s\n' "nvme-cli:" "$(nvme version 2>/dev/null || echo "unknown")"
    printf '%-24s %s\n' "Mode:" "$([[ $SHOW_FULL -eq 1 ]] && echo full || echo summary)"

    print_sysfs_summary "$pci_bdf" "$nvme_dev" "${namespaces[@]}"

    if [[ $SHOW_FULL -eq 1 ]]; then
        run_section "All NVMe devices" nvme list
        run_section "Controller identify: $dev_path" nvme id-ctrl "$dev_path"
        if [[ ${#namespaces[@]} -eq 0 ]]; then
            section "Namespace identify"
            printf '[WARN] No namespaces found under /sys/class/nvme/%s\n' "$nvme_dev"
        else
            local ns
            for ns in "${namespaces[@]}"; do
                run_section "Namespace identify: /dev/$ns" nvme id-ns "/dev/$ns"
            done
        fi
        run_section "SMART / health log: $dev_path" nvme smart-log "$dev_path"
        print_features "$dev_path"
        run_section "Firmware log: $dev_path" nvme fw-log "$dev_path"
        run_section "Error log: $dev_path" nvme error-log "$dev_path"
    else
        local ns_paths=()
        local ns
        for ns in "${namespaces[@]}"; do
            ns_paths+=("/dev/$ns")
        done
        print_nvme_list_summary "${ns_paths[@]}"
        print_id_ctrl_summary "$dev_path"
        if [[ ${#namespaces[@]} -eq 0 ]]; then
            section "Namespace summary"
            printf '[WARN] No namespaces found under /sys/class/nvme/%s\n' "$nvme_dev"
        else
            for ns in "${namespaces[@]}"; do
                print_id_ns_summary "/dev/$ns"
            done
        fi

        if [[ $SHOW_FEATURES -eq 1 ]]; then
            print_features "$dev_path"
        fi
        if [[ $SHOW_HEALTH -eq 1 ]]; then
            print_command_output "SMART / health log: $dev_path" nvme smart-log "$dev_path"
        fi
        if [[ $SHOW_ERRORS -eq 1 ]]; then
            print_command_output "Error log: $dev_path" nvme error-log "$dev_path"
        fi
    fi

    section "Report complete"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
