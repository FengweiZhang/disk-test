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
2. Optionally create a RAID0 array
3. Generate and run fio jobs for the full test matrix
4. Collect results into a CSV file
5. Generate performance plots
6. Clean up RAID if created

### Output

Results are saved to `output/<test_name>_<YYYYMMDD_HHMMSS>/`:

```
output/single_nvme_baseline_20260402_143022/
├── config.json      # Copy of config used for this run
├── fio_jobs/        # Generated .fio job files
├── fio_raw/         # Raw fio JSON outputs and logs
├── csv/
│   └── results.csv  # Aggregated results
└── plots/           # Performance charts (PNG or PDF)
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
| `use_raid` | bool | If `true`, create a software RAID0 array from all listed devices. Requires at least 2 devices. |
| `raid_chunk_size` | string | RAID0 stripe/chunk size (e.g., `"64K"`, `"256K"`). Only used when `use_raid` is `true`. |

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

## CSV Output

The results CSV (`csv/results.csv`) contains one row per fio job:

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

## Plots

**Bandwidth & IOPS** (line plots): One chart per workload type. X-axis = IO depth, separate lines for each (block_size, numjobs) combination.

**Latency** (bar charts): One chart per (workload, block_size). X-axis = IO depth, grouped bars for each numjobs value. Bar height = average latency, error bar = P99 latency.
