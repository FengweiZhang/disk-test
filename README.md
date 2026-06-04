# NVMe Performance Test Tool

A Python-based NVMe disk performance testing tool using fio. Tests bandwidth, IOPS, and latency across configurable block sizes, thread counts, and IO depths.

## Prerequisites

- Python 3.8+
- `fio` installed (`apt install fio`)
- `nvme-cli` installed (`apt install nvme-cli`)
- `mdadm` installed if using RAID (`apt install mdadm`)
- Root/sudo access (required for device operations and fio direct IO)

```bash
pip install -r requirements.txt
```

## Usage

```bash
sudo python main.py -c config.json
```

The tool will:
1. Prepare NVMe devices (format or bind based on config)
2. Expand the run into aggregate and/or per-device scenarios
3. Optionally create a RAID0 array for the aggregate scenario
4. Generate and run fio jobs for each scenario's full test matrix
5. Collect results into CSV files
6. Generate per-scenario plots and optional cross-device comparison plots
7. Clean up RAID if created

### Output

Results are saved to `output/<test_name>_<YYYYMMDD_HHMMSS>/`.

For configs without an `execution` section, the output remains compatible with the existing aggregate-only behavior, but is now nested under `aggregate/`:

```
output/single_nvme_baseline_20260402_143022/
├── config.json
├── run_summary.json
└── aggregate/
    ├── fio_jobs/
    ├── fio_raw/
    ├── csv/
    │   └── results.csv
    └── plots/
```

For combined aggregate + per-device runs:

```
output/per_device_and_aggregate_20260419_120000/
├── config.json
├── run_summary.json
├── aggregate/
│   ├── fio_jobs/
│   ├── fio_raw/
│   ├── csv/results.csv
│   └── plots/
├── per_device/
│   ├── 0000_50_00_0/
│   │   ├── fio_jobs/
│   │   ├── fio_raw/
│   │   ├── csv/results.csv
│   │   └── plots/
│   └── 0000_51_00_0/
│       ├── fio_jobs/
│       ├── fio_raw/
│       ├── csv/results.csv
│       └── plots/
└── comparison/
    ├── csv/
    │   ├── all_results.csv
    │   ├── best_points.csv
    │   └── fixed_points.csv
    └── plots/
```

## Configuration

All test parameters are defined in a JSON config file. See `config.json` for a full example.

### Top-level

| Field | Type | Description |
|-------|------|-------------|
| `test_name` | string | Name for this test run. Used in the output directory name. |

### `devices` section

| Field | Type | Description |
|-------|------|-------------|
| `pci_addresses` | string[] | PCI BDF addresses of NVMe devices (e.g., `["0000:50:00.0"]`). |
| `format_before_test` | bool | If `true`, format and secure-erase each device before testing. If `false`, only bind to the nvme driver. |
| `use_raid` | bool | If `true`, create a software RAID0 array from all listed devices. Requires at least 2 devices. If `false` with 2+ devices, uses fio's native multi-device mode (colon-separated `filename`) to test all devices in parallel without RAID. |
| `raid_chunk_size` | string | RAID0 stripe/chunk size (e.g., `"64K"`, `"256K"`). Only used when `use_raid` is `true`. |

### `execution` section

The `execution` section is optional. If omitted, the tool behaves as an aggregate-only run:

```json
{
  "execution": {
    "run_aggregate": true,
    "run_per_device": false,
    "prepare_mode": "once",
    "comparison_summary": {
      "best_points": false,
      "fixed_points": []
    }
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `run_aggregate` | bool | If `true`, run the existing aggregate scenario. For multiple devices this means RAID0 when `devices.use_raid` is `true`, otherwise fio native multi-device mode. |
| `run_per_device` | bool | If `true`, run the full fio matrix separately for each PCI address in `devices.pci_addresses`. |
| `prepare_mode` | string | `"once"` prepares all devices once at run start. `"per_test"` prepares the devices needed by each scenario before that scenario starts. |
| `comparison_summary.best_points` | bool | If `true`, write best bandwidth, best IOPS, and best latency summaries and overview plots. |
| `comparison_summary.fixed_points` | object[] | Fixed fio matrix points to compare across targets. Each item has `name`, `workload`, `block_size`, `numjobs`, and `iodepth`. |

### `fio` section

| Field | Type | Description |
|-------|------|-------------|
| `block_sizes` | string[] | IO block sizes to test (e.g., `["4K", "16K", "64K", "256K"]`). |
| `numjobs` | int[] | Number of parallel fio worker threads (e.g., `[1, 2, 4]`). |
| `iodepth` | int[] | IO queue depths (e.g., `[1, 4, 16, 32, 64, 128]`). |
| `workloads` | string[] | Fio workload types. Valid values: `"read"`, `"write"`, `"randread"`, `"randwrite"`. |
| `runtime` | int | Duration of each test in seconds. |
| `ramp_time` | int | Warm-up time before measurement starts, in seconds. |
| `direct` | int | `1` to bypass OS page cache (O_DIRECT), `0` to use cached IO. |
| `ioengine` | string | Fio IO engine (e.g., `"libaio"`, `"io_uring"`). |
| `size` | string | Test region size per job (e.g., `"100%"` for entire device, `"1G"` for 1 GB). |

The total number of fio jobs = `len(block_sizes)` x `len(numjobs)` x `len(iodepth)` x `len(workloads)`.

### `output` section

| Field | Type | Description |
|-------|------|-------------|
| `base_dir` | string | Base directory for test outputs (e.g., `"./output"`). |
| `plot_format` | string | Plot image format: `"png"` or `"pdf"`. |

### Example configs

**Full test** (288 jobs, ~3.2 hours):

```json
{
  "test_name": "single_nvme_baseline",
  "devices": {
    "pci_addresses": ["0000:50:00.0"],
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

**Quick functional test** (8 jobs, ~1 minute):

```json
{
  "test_name": "quick_functional_test",
  "devices": {
    "pci_addresses": ["0000:cc:00.0"],
    "format_before_test": false,
    "use_raid": false,
    "raid_chunk_size": "64K"
  },
  "fio": {
    "block_sizes": ["4K", "64K"],
    "numjobs": [1],
    "iodepth": [1, 16],
    "workloads": ["randread", "randwrite"],
    "runtime": 5,
    "ramp_time": 2,
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

**Multi-disk RAID0 test**:

```json
{
  "test_name": "raid0_2disk",
  "devices": {
    "pci_addresses": ["0000:50:00.0", "0000:51:00.0"],
    "format_before_test": true,
    "use_raid": true,
    "raid_chunk_size": "256K"
  },
  "fio": {
    "block_sizes": ["4K", "64K", "256K"],
    "numjobs": [1, 4],
    "iodepth": [1, 16, 64, 128],
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

Manual RAID script usage also accepts PCI BDFs directly. The default RAID0 chunk size is `64K`, and the new RAID device is initialized as `ext4` by default:

```bash
sudo scripts/raid0_create.sh 0000:50:00.0 0000:51:00.0
sudo scripts/raid0_create.sh --chunk 256K --raid-device /dev/md10 0000:50:00.0 0000:51:00.0
sudo scripts/raid0_create.sh --no-filesystem 0000:50:00.0 0000:51:00.0
sudo scripts/raid0_delete.sh 0000:50:00.0 0000:51:00.0
```

`raid0_delete.sh` zeros member md superblocks by default after stopping the array. Use `--no-zero-superblock` to only stop the md device.

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

**Per-device only**:

```json
{
  "test_name": "per_device_only",
  "devices": {
    "pci_addresses": ["0000:50:00.0", "0000:51:00.0"],
    "format_before_test": false,
    "use_raid": false,
    "raid_chunk_size": "64K"
  },
  "execution": {
    "run_aggregate": false,
    "run_per_device": true,
    "prepare_mode": "once",
    "comparison_summary": {
      "best_points": true,
      "fixed_points": []
    }
  },
  "fio": {
    "block_sizes": ["4K", "64K"],
    "numjobs": [1],
    "iodepth": [1, 16],
    "workloads": ["randread", "randwrite"],
    "runtime": 5,
    "ramp_time": 2,
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

**Per-device + aggregate with comparison summaries**:

See `config_per_device_compare.json` for a compact example that runs every listed NVMe individually, runs the aggregate target, writes best-result summaries, and compares a fixed `4K/randread/numjobs=4/iodepth=64` test point.

## CSV Output

Each scenario results CSV (`aggregate/csv/results.csv` or `per_device/<pci>/csv/results.csv`) contains one row per fio job:

| Column | Description |
|--------|-------------|
| `workload` | read, write, randread, or randwrite |
| `block_size` | IO block size (e.g., 4K, 64K) |
| `numjobs` | Number of parallel workers |
| `iodepth` | IO queue depth |
| `bw_MBps` | Bandwidth in MB/s |
| `iops` | IO operations per second |
| `lat_avg_us` | Average latency in microseconds |
| `lat_p50_us` | P50 (median) latency in microseconds |
| `lat_p99_us` | P99 latency in microseconds |
| `lat_max_us` | Maximum latency in microseconds |

Comparison CSVs are written under `comparison/csv/`:

| File | Description |
|------|-------------|
| `all_results.csv` | Merged scenario results with `target_id`, `target_label`, and `target_type` metadata columns. |
| `best_points.csv` | One row per target/workload/summary type for best bandwidth, best IOPS, and best average latency. |
| `fixed_points.csv` | One row per configured fixed comparison point per target. |

## Plots

**Bandwidth & IOPS** (line plots): One chart per workload type. X-axis = IO depth, separate lines for each (block_size, numjobs) combination.

**Latency** (line plots): One chart per workload. Average latency is plotted as the line, with a semi-transparent band up to P99 latency.

**Comparison overview plots** are written under `comparison/plots/` when enabled:

- `best_bandwidth_overview.<format>`
- `best_iops_overview.<format>`
- `best_latency_overview.<format>`
- `<fixed_point_name>_overview.<format>`

Comparison images include an embedded configuration table:

- Fixed-point overview plots show `name`, `workload`, `block_size`, `numjobs`, and `iodepth`.
- Best overview plots show the `workload`, `target`, `block_size`, `numjobs`, and `iodepth` that produced each best value.

## Run Summary

Every run writes `run_summary.json` at the run root. It records:

- run start/end time and total duration
- `prepare_mode`
- every scenario's status, target label, job counts, CSV path, and plots directory
- comparison status, included targets, generated CSVs, generated plots, and missing fixed points if any
