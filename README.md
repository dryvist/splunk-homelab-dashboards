# splunk-homelab-dashboards

A Splunk app with Dashboard Studio views over homelab metrics and agent logs.

- **Storage Capacity and Health** (`storage_capacity_health`): pool fill against
  thresholds, size, used and free, days to full, pool health and scrub results,
  pool I/O, and SMART status per node and device.
- **Homelab Overview** (`homelab_overview`): cluster totals, then CPU, memory,
  load, network, GPU and pool fill per node.
- **Agent Activity (Beta)** (`agent_activity`): event counts by agent index and
  sourcetype, cron terminal events and outcomes, errors, and available gateway,
  retain, and recall timings from the `hermes` and `hindsight` indexes.

| Additional beta view | View ID | Required Splunk Enterprise version |
| --- | --- | --- |
| Agent timeline (Beta) | `agent_timeline` | 10.2+ |
| Agent network (Beta) | `agent_network` | 10.4+ |

The operator must verify the installed version before opening these native
Dashboard Studio views. Both default to the last four hours and use a base
search with chain searches over the agent event indexes.

The views contain no hostnames, addresses, serial numbers or pool layouts.
Selectors are populated from the metrics.

## Usage

Open the app from the Splunk navigation bar. Set the time range, then pick a
node, pool or SMART device. Each selector defaults to all values (`*`).

Pool fill bands: green below 70%, yellow from 70% to below 80%, orange from 80%
to below 90%, red at 90% and above.

Days to full is a linear regression over daily free-byte samples from the last
seven days. It shows no value when free space is not shrinking.

Agent Activity uses extracted log fields and JSON extraction. Cron counts assume
one terminal event per run. Timing panels accept only fields with explicit
millisecond or second units and show sample counts; empty panels indicate no
matching measurements. Event names, field mappings, and units need live
validation. Error panels require extracted severity or outcome fields.

### Agent timeline

Unit lanes use `message` in `index=hermes sourcetype=hermes:agent`. A `Starting`
message pairs with the next `Finished`, `Failed`, `Failed to start`,
`Deactivated`, or `Stopped` message for that unit and available host/process
identity. Unit-prefixed `Failed` and `Deactivated` messages are also accepted.
Repeated starts use the latest start; terminal events without a start are
omitted. Pairing assumes one active lifecycle per unit and identity. Missing
identity values group together; mismatched identities cannot pair.

The chain sorts the latest 50,000 matching events in reverse time order, with
lifecycle order, ingest time, and event location as tie-breakers. A bounded
`streamstats` window finds each start's next lifecycle message. An unmatched
latest start extends to the earlier of now or the selected range end, colored
`running`. This means no terminal was observed in range, not confirmed execution.
Other unit colors identify terminal state, including `failed`.

The `model calls` lane requires `model` and `latency` in explicit `s` or `ms`
units. Assuming `_time` marks completion, each call starts at `_time - latency`
and is colored by model. Both start and duration convert to milliseconds.
Memory-trim `duration_ms`, `malloc_trim`, and worker health fields are not used.

The panel renders at most 10,000 intervals. The base search retains chain fields
and remains subject to Splunk's result-retention limits. Starts before the range
are unavailable; measured calls may start before it. Shorten capped ranges.

### Agent network

Nodes represent roles reported together on qualifying events:

- Hermes → plugin: events with `plugin` and `decision`; weight is decisions.
- Hermes → model → provider: events with `model` and an explicit `s` or `ms`
  `latency`; weight is calls. Missing `provider` omits only the second hop.
- Hindsight bank → store: events with `bank` and `store`; weight is retrieval
  log events. Store names are retained. Store timing strings map to the
  Hindsight store role, since a timing value does not identify a store.

Plugin decisions take precedence if a Hermes event also has model fields.
Each qualifying event contributes once per hop and once per participating node.
Counts include duplicate log events; no unique retrieval identifier is available.
Memory-trim and worker pool health measurements do not form relationships.

The base search aggregates event counts before separate edge and node chains.
Each event counts once per participating node. Node diameter and arrow width
scale linearly with their event counts; the tables retain exact counts. The
graph renders at most 1,000 edges. All edge counts and plugin deny counts appear
in the companion table below the graph; graph edges have no text labels.
Search retention and expansion limits can also constrain large ranges; inspect
search warnings and shorten the range.

Native option references: [timeline][timeline], [network graph][network], and
[base and chain searches][chains]. No live searches or rendering are covered by
the local tests; empty panels can mean unmatched fields or unavailable data.

[timeline]: https://help.splunk.com/en/splunk-enterprise/create-dashboards-and-reports/dashboard-studio/10.2/visualizations/timelines
[network]: https://help.splunk.com/en/splunk-enterprise/create-dashboards-and-reports/dashboard-studio/10.4/visualizations/network-graph
[chains]: https://help.splunk.com/en/splunk-enterprise/create-dashboards-and-reports/dashboard-studio/10.4/use-data-sources/chain-searches-together-with-a-base-search-and-chain-searches

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
