# Metric coverage — Alpha 2

The console reads Docker environments through the Portainer API. It does not execute commands or change Docker resources. Collection targets five seconds for container stats, thirty seconds for inventory/inspect metadata and sixty seconds for Docker storage and optional Agent capabilities. Permissions, runtime type, cgroup version and installed Agent version determine which fields are available.

| Resource | Available monitoring categories |
|---|---|
| Containers | CPU/core, user/kernel time and usage, quota periods and throttling; working/raw/limit/peak/anonymous/file/mapped/dirty/writeback/swap memory; faults and fault rates; Windows private working set and commitment; PIDs/threads and limits; network bytes/packets/errors/drops and rates; block I/O bytes/operations and rates; writable storage; lifecycle state, restarts, OOM state, healthchecks, uptime and configured limits |
| Stacks / networks | Counts and additive container telemetry for their members; network traffic includes all interfaces of those containers |
| Environment | Container aggregates and inventory counts; host capacity and applicable container/host fractions; image layers, writable layers, volumes, build cache and reclaimable cache |
| Images / volumes | Virtual/shared image bytes and references; volume-driver size and references |
| Swarm services / nodes | Desired/running/completed tasks when reported; node CPU/memory capacity and ready state |
| Agent host capabilities | Physical disk capacities/vendor and PCI inventory; compatible recent Agents can report Docker filesystem capacity, available bytes and Docker artifact totals |

## Native numeric discovery

The normalized catalog is complemented by **Docker raw** container metrics discovered from numeric fields under `cpu_stats`, `precpu_stats`, `memory_stats`, `pids_stats`, `networks`, `blkio_stats`, `storage_stats` and `num_procs`. This includes additional cgroup counters, per-interface fields, per-device fields and per-CPU arrays that the running Engine actually sends. Search the metric selector or use **Container → Resources → Advanced** to inspect them.

Raw fields retain native API units. CPU native time units differ between Linux and Windows; normalized CPU time metrics convert them to seconds. Array indices may change between samples, and resource-specific paths should be compared individually. Discovery is bounded to 512 numeric leaves per container, depth 10 and 4096 visited nodes to protect gateway resources. This is not a claim to exhaust every field of every Portainer API or third-party plugin.

## Correct interpretation

- 100% container CPU equals one logical core and can exceed 100%. User/kernel percentages use the same convention. Container/host fractions are disabled when aggregated containers span several Swarm nodes because a single-node capacity would be an invalid denominator.
- Container working-set RAM excludes valid inactive file cache. It does not include unrelated host processes. Memory limits may equal installed host RAM when no explicit limit is set.
- Docker cgroup v2 often omits peak memory and block-operation counts. Its fail counter represents OOM events, whereas cgroup v1 reports limit hits. Unreported fields remain unavailable.
- `OOMKilled` is the last recorded state; it is not an all-time killed-process count. Health values require configured healthchecks. Metadata follows the inventory cadence.
- Stopped containers have no live stats. Missing counters and first-sample/reset rates remain unavailable. Multi-resource sums use original matching timestamps before chart reduction. Gaps remain explicit.
- Ratios, native counters and per-container limits cannot be summed across selected resources. Virtual image sizes may share layers; use environment unique-layer totals for storage accounting.
- Docker-data filesystem available space is for that partition and unprivileged processes. Capacity minus available includes reserved blocks and non-Docker usage; it is not a precise measure of used physical disk blocks.
- Agent host APIs are capability-probed. Unsupported, denied or empty responses remain unavailable. Hardware inventory is for the Agent node selected by Docker `/info`, not an entire Swarm fleet.
- Total host CPU/RAM utilization outside containers, CPU temperature, GPU utilization, network-switch counters and arbitrary application metrics are not provided by ordinary Docker stats. They require an appropriate host/application exporter or another API. Kubernetes/Podman/async Edge environments are not silently interpreted as Docker telemetry.

Recent normalized metrics are buffered in memory. Only metrics referenced by saved dashboards are persisted, for a rolling 24 hours. Native raw history begins once selected in a saved dashboard; its first preview shows the current reading. This limits writes to Raspberry Pi storage. The application does not claim long-term monitoring retention.

## API references

- [Portainer API access and Docker proxy](https://docs.portainer.io/api/access)
- [Docker stats semantics](https://docs.docker.com/reference/cli/docker/container/stats/)
- [Docker Engine stats schema](https://github.com/moby/moby/blob/master/api/types/container/stats.go)
- [Linux stats and cgroup conversion](https://github.com/moby/moby/blob/master/daemon/stats_unix.go)
- [Portainer Agent routing and node target headers](https://github.com/portainer/agent)
- [Agent host hardware API](https://github.com/portainer/agent/blob/develop/http/handler/host/host_info.go)
- [Optional Agent Docker filesystem API](https://github.com/portainer/agent/blob/develop/http/handler/host/host_docker_storage.go)

Agent development sources describe capabilities that may be absent from older deployed versions; successful runtime discovery determines availability.
