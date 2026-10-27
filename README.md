# splunk-homelab-dashboards

A Splunk app with two Dashboard Studio views over homelab metrics.

- **Storage Capacity and Health** (`storage_capacity_health`): pool fill against
  thresholds, size, used and free, days to full, pool health and scrub results,
  pool I/O, and SMART status per node and device.
- **Homelab Overview** (`homelab_overview`): cluster totals, then CPU, memory,
  load, network, GPU and pool fill per node.

The views contain no hostnames, addresses, serial numbers or pool layouts.
Selectors are populated from the metrics.

## Usage

Open the app from the Splunk navigation bar. Set the time range, then pick a
node, pool or SMART device. Each selector defaults to all values (`*`).

Pool fill bands: green below 70%, yellow from 70% to below 80%, orange from 80%
to below 90%, red at 90% and above.

Days to full is a linear regression over daily free-byte samples from the last
seven days. It shows no value when free space is not shrinking.

## Data

- `node_cpu_seconds_total`, `node_memory_*`, `node_load1`, `node_network_*`:
  index `host_metrics`, dimension `host`.
- `pve_zpool_*`: index `host_metrics` (assumed), dimension `pool`, plus `state`
  on `pve_zpool_health`.
- `smartmon_*`: index `host_metrics` (assumed), dimensions `host`, `device`,
  `disk`.
- `node_gpu_*`: index not confirmed, so searches use `index=*`; dimension `host`
  (assumed).

`host_metrics` and the `host` dimension come from the `ZFS ARC pressure` and
`object store volume fill` searches in `splunk-homelab-alerts`. No index
definition for `host_metrics` exists in `splunk-homelab-indexes`. The pool and
SMART index assignment and the GPU metric names were not checked against a live
instance.

## Installation

```sh
tar -cf splunk-homelab-dashboards.tar splunk-homelab-dashboards
```

## Tests

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
```

The tests parse each view as XML and parse the embedded Dashboard Studio JSON.
They do not render the dashboards or query Splunk.

## Contributing

Conventional-commit subjects.

## License

No license file is included yet.
