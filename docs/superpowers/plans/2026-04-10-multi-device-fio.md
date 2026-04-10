# Multi-Device fio Testing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When `use_raid: false` and 2+ devices are configured, use fio's colon-separated `filename` syntax to test all devices in parallel without RAID.

**Architecture:** Single change in `device.py:prepare_all_devices()` to join multiple device paths with `:` instead of returning only the first. All downstream modules (fio.py, results.py, plot.py) require zero changes because fio's `group_reporting` aggregates multi-device output into the same JSON structure.

**Tech Stack:** Python 3.8+, fio, shell scripts

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `nvme_test/device.py` | Modify line 83-84 | Join device paths with `:` for multi-device no-RAID case |
| `config_multi_device.json` | Create | Sample config demonstrating multi-device without RAID |
| `README.md` | Modify lines 56-62, 146+ | Add `use_raid: false` multi-device behavior description and example |

---

### Task 1: Implement multi-device logic in device.py

**Files:**
- Modify: `nvme_test/device.py:80-84`

- [ ] **Step 1: Edit `prepare_all_devices()` to handle multi-device without RAID**

In `nvme_test/device.py`, replace the `else` branch (lines 83-84):

```python
    else:
        return device_paths[0], None
```

with:

```python
    else:
        if len(device_paths) > 1:
            test_device = ":".join(device_paths)
            logger.info("Multi-device mode (no RAID): %s", test_device)
        else:
            test_device = device_paths[0]
        return test_device, None
```

This makes fio receive `filename=/dev/nvme0n1:/dev/nvme1n1` and distribute IO across all devices. With `group_reporting` already enabled in the job template, the JSON output stays a single `jobs[0]` entry.

- [ ] **Step 2: Commit**

```bash
git add nvme_test/device.py
git commit -m "feat: support multi-device fio testing without RAID

When use_raid is false and multiple PCI addresses are configured,
join device paths with ':' for fio's native multi-device filename
syntax instead of using only the first device."
```

---

### Task 2: Add sample config file

**Files:**
- Create: `config_multi_device.json`

- [ ] **Step 1: Create the sample config**

Create `config_multi_device.json`:

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

- [ ] **Step 2: Commit**

```bash
git add config_multi_device.json
git commit -m "docs: add sample config for multi-device fio testing"
```

---

### Task 3: Update README with multi-device documentation

**Files:**
- Modify: `README.md:56-62` (devices table)
- Modify: `README.md:146+` (add example config after existing examples)

- [ ] **Step 1: Update the `devices` section table**

In `README.md`, update the `use_raid` row in the `devices` table (line 61) from:

```markdown
| `use_raid` | bool | If `true`, create a software RAID0 array from all listed devices. Requires at least 2 devices. |
```

to:

```markdown
| `use_raid` | bool | If `true`, create a software RAID0 array from all listed devices. Requires at least 2 devices. If `false` with 2+ devices, uses fio's native multi-device mode (colon-separated `filename`) to test all devices in parallel without RAID. |
```

- [ ] **Step 2: Add multi-device example config to README**

After the existing "Multi-disk RAID0 test" example section (after line 174), add:

```markdown

**Multi-disk without RAID** (fio native multi-device):

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

When `use_raid` is `false` and multiple PCI addresses are listed, fio tests all devices in parallel using its native colon-separated `filename` syntax. No RAID array is created. Results show the aggregated performance across all devices.
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add multi-device fio testing usage to README"
```
