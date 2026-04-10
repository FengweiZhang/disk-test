# Multi-Device fio Testing (No RAID)

## Overview

When `use_raid: false` and `pci_addresses` contains 2+ devices, use fio's native colon-separated `filename` syntax to test all devices in parallel without creating a RAID array.

## Trigger Condition

| `use_raid` | Device Count | Behavior |
|-----------|-------------|----------|
| `true` | 2+ | RAID0 (existing, unchanged) |
| `false` | 1 | Single device (existing, unchanged) |
| `false` | 2+ | **New: fio multi-device via colon-separated filename** |

## Design

### Core Change: device.py

In `prepare_all_devices()`, when `use_raid` is `false`:
- **Current:** returns `device_paths[0]` (first device only, rest ignored)
- **New:** if `len(device_paths) > 1`, returns `":".join(device_paths)` (e.g. `/dev/nvme0n1:/dev/nvme1n1`)

The return type remains `tuple[str, str | None]`. The colon-separated string is treated as a single `filename` value by fio.

### fio Job File Effect

Single device (unchanged):
```ini
filename=/dev/nvme0n1
```

Multi-device without RAID (new):
```ini
filename=/dev/nvme0n1:/dev/nvme1n1
```

fio distributes IO across all listed devices. Combined with the existing `group_reporting` directive, the JSON output contains a single aggregated `jobs[0]` entry with total bandwidth/IOPS and averaged latency.

### Downstream Modules — No Changes Required

- **fio.py**: `filename={device}` writes the colon-separated string directly. No logic change.
- **results.py**: `data["jobs"][0]` parsing works because `group_reporting` aggregates all threads/devices into one entry. Bandwidth and IOPS are totals; latency stats are aggregated means/percentiles.
- **plot.py**: Input CSV format unchanged.
- **main.py**: Return type unchanged `(str, None)`.
- **config.py**: No new fields. Existing validation sufficient.

### Documentation Updates

1. **README.md**: Add a "Multi-disk without RAID" example config and update the `devices` section table to describe the multi-device behavior.
2. **config_multi_device.json**: Add a sample config file demonstrating `use_raid: false` with 2 devices.

### Sample Config

```json
{
  "test_name": "dual_nvme_no_raid",
  "devices": {
    "pci_addresses": ["0000:50:00.0", "0000:51:00.0"],
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

## Files Modified

| File | Change |
|------|--------|
| `nvme_test/device.py` | `prepare_all_devices()`: join device paths with `:` when multi-device and no RAID |
| `README.md` | Add multi-device usage description and example config |
| `config_multi_device.json` | New sample config file |
