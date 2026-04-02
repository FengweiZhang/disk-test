# NVMe Performance Test Tool - Design Specification

## Overview

A Python-based NVMe disk performance testing tool that measures bandwidth, IOPS, and latency using fio. The tool reads a JSON configuration file, prepares devices (format/bind/RAID), generates and executes fio jobs, collects results into CSV, and generates plots.

## Project Structure

```
nvme-test/
├── config.json              # Test configuration (JSON)
├── main.py                  # Entry point
├── nvme_test/
│   ├── __init__.py
│   ├── config.py            # JSON config parsing & validation
│   ├── device.py            # Format & RAID setup/teardown
│   ├── fio.py               # Fio job file generation & execution
│   ├── results.py           # Parse fio JSON output -> CSV
│   └── plot.py              # Matplotlib plotting
├── scripts/
│   ├── format_nvme_device.sh   # Format & bind NVMe device (from Geminifs)
│   ├── bind_nvme_device.sh     # Bind PCI device to nvme driver (from Geminifs)
│   ├── raid0_create.sh         # Create RAID0 array (from Geminifs, add -y flag)
│   └── raid0_delete.sh         # Delete RAID0 array (from Geminifs, add -y flag)
├── output/                     # Created at runtime
│   └── <test_name>_<YYYYMMDD_HHMMSS>/
│       ├── config.json         # Copy of config used for this run
│       ├── fio_jobs/           # Generated .fio job files
│       ├── fio_raw/            # Raw fio JSON outputs
│       ├── csv/                # Aggregated CSV results
│       └── plots/              # Generated plot images
└── requirements.txt            # matplotlib, numpy
```

## Configuration

The tool is driven by a JSON config file. All test parameters are configurable.

### Example `config.json`

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

### Config Fields

| Field | Type | Description |
|-------|------|-------------|
| `test_name` | string | Name for this test run; used in output directory naming |
| `devices.pci_addresses` | string[] | PCI BDF addresses of NVMe devices |
| `devices.format_before_test` | bool | Whether to format devices before testing |
| `devices.use_raid` | bool | Whether to create RAID0 from multiple devices |
| `devices.raid_chunk_size` | string | RAID0 stripe size (e.g., "64K") |
| `fio.block_sizes` | string[] | IO block sizes to test |
| `fio.numjobs` | int[] | Number of parallel jobs |
| `fio.iodepth` | int[] | IO queue depths |
| `fio.workloads` | string[] | Fio workload types |
| `fio.runtime` | int | Test duration in seconds |
| `fio.ramp_time` | int | Ramp-up time in seconds |
| `fio.direct` | int | 1 = bypass OS cache |
| `fio.ioengine` | string | Fio IO engine |
| `fio.size` | string | Test file size |
| `output.base_dir` | string | Base output directory |
| `output.plot_format` | string | Plot image format ("png" or "pdf") |

## Device Management (`device.py`)

### Flow

1. **Device preparation** (for each PCI address):
   - If `format_before_test: true`: call `scripts/format_nvme_device.sh <pci_addr> -y`
     - Formats the device and ensures it is bound to the nvme driver
   - If `format_before_test: false`: call `scripts/bind_nvme_device.sh <pci_addr>`
     - Checks if already bound to nvme driver; if not, attempts to bind
     - If already bound, proceeds with existing binding
     - If binding fails, exits with error message

2. **Resolve device paths**: After binding, resolve each PCI address to `/dev/nvmeXnY` by reading sysfs (`/sys/bus/pci/devices/<pci_addr>/nvme/nvmeX/nvmeXnY`)

3. **RAID setup** (if `use_raid: true` and 2+ devices):
   - Call `scripts/raid0_create.sh <device1> <device2> ... -y` with configured chunk size
   - Capture the created `/dev/mdX` path from script output
   - Return `/dev/mdX` as the test target device

4. **Test target resolution**:
   - Single device, no RAID: return `/dev/nvmeXnY` directly
   - Multiple devices with RAID: return `/dev/mdX`

5. **Cleanup** (after test completes):
   - If RAID was created: call `scripts/raid0_delete.sh <md_name> -y`

### Script Modifications

All scripts are adapted from Geminifs originals for programmatic (Python subprocess) use. Key principles:

- **Non-interactive**: No confirmation prompts. All scripts run without user input.
- **Machine-parseable output**: Print key results as `KEY=VALUE` lines on stdout so Python can parse them. Human-readable status messages go to stderr.
- **No color codes**: Remove ANSI color escapes (not useful when captured by subprocess).
- **Proper exit codes**: 0 = success, non-zero = failure. Stderr contains error details.

#### `format_nvme_device.sh`

Based on Geminifs version. Modifications:
- Remove interactive confirmation prompt entirely (original `-y` flag logic removed; script always runs non-interactively)
- Print `NVME_DEV=nvmeX` and `DEVICE_PATH=/dev/nvmeXnY` to stdout after successful format
- Status/progress messages to stderr
- Remove emoji characters from output

#### `bind_nvme_device.sh`

Based on Geminifs version. Modifications:
- Print `NVME_DEV=nvmeX` and `DEVICE_PATH=/dev/nvmeXnY` to stdout after successful bind (or if already bound)
- Status/progress messages to stderr
- Remove emoji characters from output
- Remove `sleep 1` wait; Python caller handles any needed delay

#### `raid0_create.sh`

Based on Geminifs version. Modifications:
- Remove interactive confirmation prompt entirely
- Accept `--chunk <size>` flag to override default chunk size
- Remove ANSI color codes
- Print `RAID_DEVICE=/dev/mdX` to stdout after successful creation
- Status/progress messages to stderr
- Remove "Next Steps" instructions from output (Python handles filesystem creation)

#### `raid0_delete.sh`

Based on Geminifs version. Modifications:
- Remove interactive confirmation prompt entirely
- Remove ANSI color codes
- Status/progress messages to stderr
- Exit code 0 on success, non-zero on failure

### Python Parsing Contract

`device.py` parses script stdout for `KEY=VALUE` lines:
- From format/bind scripts: extract `DEVICE_PATH` to get the `/dev/nvmeXnY` path
- From raid0_create: extract `RAID_DEVICE` to get the `/dev/mdX` path
- Stderr is logged for debugging but not parsed for control flow

## Fio Job Generation & Execution (`fio.py`)

### Job File Generation

For each combination of (workload, block_size, numjobs, iodepth), generate a `.fio` job file.

Example `randread_4K_nj1_qd32.fio`:

```ini
[global]
ioengine=libaio
direct=1
runtime=30
ramp_time=10
time_based
group_reporting
size=100%

[randread_4K_nj1_qd32]
rw=randread
bs=4K
numjobs=1
iodepth=32
filename=/dev/nvme0n1
```

For RAID mode, `filename` points to the RAID device (e.g., `/dev/md0`).

### Naming Convention

Job file name: `<workload>_<bs>_nj<numjobs>_qd<iodepth>.fio`

### Execution

1. Generate all `.fio` files into `<test_dir>/fio_jobs/`
2. Execute each fio job sequentially: `fio <jobfile> --output-format=json --output=<test_dir>/fio_raw/<name>.json`
3. After each job completes, parse the JSON output and append results to an in-memory list
4. After all jobs complete, write the aggregated CSV

## Result Collection (`results.py`)

### CSV Output

File: `<test_dir>/csv/results.csv`

Columns:

| Column | Description |
|--------|-------------|
| `workload` | read, write, randread, randwrite |
| `block_size` | IO block size (e.g., 4K, 64K) |
| `numjobs` | Number of parallel jobs |
| `iodepth` | IO queue depth |
| `bw_MBps` | Bandwidth in MB/s |
| `iops` | IO operations per second |
| `lat_avg_us` | Average latency in microseconds |
| `lat_p50_us` | P50 latency in microseconds |
| `lat_p99_us` | P99 latency in microseconds |
| `lat_max_us` | Maximum latency in microseconds |

### Parsing

Extract values from fio JSON output:
- Bandwidth: `jobs[0].read.bw` or `jobs[0].write.bw` (convert from KB/s to MB/s)
- IOPS: `jobs[0].read.iops` or `jobs[0].write.iops`
- Latency: `jobs[0].read.clat_ns` or `jobs[0].write.clat_ns` (convert from ns to us)
  - Average: `clat_ns.mean`
  - Percentiles: `clat_ns.percentile["50.000000"]`, `clat_ns.percentile["99.000000"]`
  - Max: `clat_ns.max`

## Plotting (`plot.py`)

### Bandwidth & IOPS Plots (Line plots)

- One chart per (workload_type, metric)
- X-axis: iodepth (1, 4, 16, 32, 64, 128)
- Y-axis: bandwidth (MB/s) or IOPS
- Separate lines for each (block_size, numjobs) combination (e.g., "4K_nj1", "4K_nj4", "64K_nj1")
- Lines with markers, legend outside the chart
- Total: 4 workloads x 2 metrics = 8 charts

File naming: `<workload>_bandwidth.png`, `<workload>_iops.png`

### Latency Plots (Bar charts with error bars)

- One chart per (workload_type, block_size)
- X-axis: iodepth
- Grouped bars for each numjobs value
- Bar height = average latency (us)
- Error bar cap = P99 latency
- Total: 4 workloads x 4 block_sizes = 16 charts

File naming: `<workload>_<bs>_latency.png`

All plots saved to `<test_dir>/plots/`.

## Main Execution Flow (`main.py`)

```
1.  Parse config.json
2.  Create output directory: output/<test_name>_<YYYYMMDD_HHMMSS>/
3.  Copy config.json into the output directory (for reproducibility)
4.  Device preparation (format or bind each PCI device)
5.  Resolve device paths from PCI addresses
6.  RAID setup (if configured)
7.  Generate all fio job files -> <test_dir>/fio_jobs/
8.  Execute fio jobs sequentially, saving raw JSON -> <test_dir>/fio_raw/
9.  Aggregate results -> <test_dir>/csv/results.csv
10. Generate plots -> <test_dir>/plots/
11. RAID teardown (if RAID was created)
12. Print summary (test directory path, total time, number of tests run)
```

### Error Handling

- **Device/RAID errors**: Fatal. Exit immediately with clear error message.
- **Fio job errors**: Log the error, skip that data point, continue with remaining jobs.
- **Plotting errors**: Log and continue. Missing data points are simply omitted from plots.

## Dependencies

- Python 3.8+
- `matplotlib` (plotting)
- `numpy` (data manipulation)
- `fio` (system tool, must be installed)
- `mdadm` (system tool, only if using RAID)
- `nvme-cli` (system tool, for format operations)

### `requirements.txt`

```
matplotlib
numpy
```

## Test Matrix Size

With the default configuration:
- 4 block sizes x 3 numjobs x 6 iodepths x 4 workloads = **288 fio jobs**
- At 40s per job (30s runtime + 10s ramp), total estimated time: ~3.2 hours
- Output: 1 CSV file, 8 BW/IOPS charts, 16 latency charts
