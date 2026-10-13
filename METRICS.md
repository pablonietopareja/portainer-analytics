# Metrics reference — alpha.3

Portainer Analytics reads Docker telemetry and inventory through the Portainer server API. It does not execute commands on the host or modify Docker resources. The default target interval is 5 seconds for container stats, approximately 30 seconds for inventory and 60 seconds for storage and optional Portainer Agent capabilities. Actual collection depends on upstream latency and API permissions.

## Monitored resources

| Resource | Available data |
| --- | --- |
| Containers | CPU usage and time, user/kernel CPU, quota throttling, working and raw memory, memory limits and faults, process/thread counts, network bytes and rates, packets/errors/drops, block I/O, writable storage, health, uptime, restarts and lifecycle state |
| Stacks and networks | Container counts and additive telemetry for members, where a meaningful aggregation is available |
| Environment | Inventory counts, container aggregates, applicable host/container fractions, image layers, writable layers, volumes and build-cache measurements |
| Images and volumes | Image virtual/shared size and references; available volume-driver size and references |
| Swarm services and nodes | Reported task counts, node readiness, CPU capacity and memory capacity |
| Portainer Agent host data | Supported hardware and disk inventories; on compatible Agents, Docker filesystem capacity and artifact totals |

The UI shows only fields that the available Docker/Portainer API actually returns. Optional APIs may be denied, unsupported or missing on a particular Agent version.

## Native Docker metric discovery

Alongside normalized measures, I expose a bounded catalog of numeric fields returned under Docker stats objects such as `cpu_stats`, `precpu_stats`, `memory_stats`, `pids_stats`, `networks`, `blkio_stats`, `storage_stats` and `num_procs`. The **Container → Resources → Advanced** view and dashboard metric selector can surface these additional values.

Native fields keep their original API units. CPU time units differ between Linux and Windows; normalized CPU-time metrics convert them to seconds. Numeric discovery is limited to 512 leaves per container, depth 10 and 4096 visited nodes to protect smaller edge gateways. Array positions and optional paths may change between Engine versions or samples.

## Interpretation rules

- **CPU:** 100% equals one logical CPU core; a container can exceed 100% on multicore hardware. Aggregating containers across Swarm nodes does not justify dividing by one node's CPU capacity.
- **Memory:** working-set usage normally excludes eligible inactive file cache. This is not total host memory usage. Container limits may reflect host capacity when no explicit limit is configured.
- **Missing counters:** stopped containers have no current stats. Unsupported counters, the first sample of a rate and counter resets are represented as unavailable, not zero.
- **Cgroups:** cgroup v1 and v2 expose different memory and block I/O fields. An OOM-related counter may have different semantics from an OOM-killed lifecycle state.
- **Rates and sums:** network and block I/O rates depend on elapsed sampling time. Totals use matching original timestamps before plotting. Ratios, individual limits and native counters are not always additive.
- **Storage:** image sizes can share layers; summing per-image virtual size can double-count physical bytes. Docker filesystem capacity is not equivalent to free space on every host partition.
- **Agent hardware:** information belongs to the selected Agent node, not automatically to every host in a Swarm fleet.
- **Out of scope:** host CPU/RAM outside containers, CPU temperature, GPU usage, switch telemetry and arbitrary application metrics require additional exporters or APIs.

## History and retention

Recent normalized measurements are buffered in memory. Only metrics referenced by saved dashboards are written to SQLite, with a rolling **24-hour** history window. Raw metric history begins when that metric is selected in a saved dashboard. Gaps remain gaps in charts; the system does not invent samples to make a curve continuous.

This approach controls writes to edge storage, but it is not intended as a long-term monitoring database or full observability backend. Saved dashboards accept up to 64 panels with up to 16 selected sources per panel.

## References

- [Portainer API access](https://docs.portainer.io/api/access)
- [Docker container statistics](https://docs.docker.com/reference/cli/docker/container/stats/)
- [Docker Engine stats types](https://github.com/moby/moby/blob/master/api/types/container/stats.go)
- [Portainer Agent source and capabilities](https://github.com/portainer/agent)

Implementation-specific normalization and interpretation are covered by the repository's synthetic regression tests. Live availability still depends on the deployed Docker, Portainer and Agent versions.
