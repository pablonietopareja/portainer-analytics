"""Metric catalog, dashboard validation and allowlisted public projections."""

from __future__ import annotations

import math
import re
import uuid

from telemetry import EXTRA_METRICS

METRICS = {
    "cpu_percent": {
        "label": "CPU usage",
        "unit": "percent",
        "help": "100% equals one logical CPU.",
    },
    "memory_bytes": {
        "label": "Memory working set",
        "unit": "bytes",
        "help": "Container RAM excluding valid inactive file cache.",
    },
    "cache_bytes": {
        "label": "Inactive memory cache",
        "unit": "bytes",
        "help": "Inactive file cache in RAM; not build cache.",
    },
    "rx_rate": {
        "label": "Network receive",
        "unit": "rate",
        "help": "Sum of container interfaces; includes internal traffic.",
    },
    "tx_rate": {
        "label": "Network transmit",
        "unit": "rate",
        "help": "Sum of container interfaces; includes internal traffic.",
    },
    "pids": {
        "label": "Processes / threads",
        "unit": "count",
        "help": "Current kernel task count, including threads.",
    },
    "writable_bytes": {
        "label": "Writable storage",
        "unit": "bytes",
        "help": "Writable container layers; excludes images and volumes.",
    },
    "running": {
        "label": "Running containers",
        "unit": "count",
        "help": "Number of running containers.",
    },
    "total": {
        "label": "Container count",
        "unit": "count",
        "help": "All containers, including stopped containers.",
    },
    "cpu_host_percent": {
        "label": "CPU / host capacity",
        "unit": "percent",
        "help": "Container CPU divided by logical host CPUs.",
    },
    "memory_host_percent": {
        "label": "Memory / host capacity",
        "unit": "percent",
        "help": "Container RAM divided by installed host RAM.",
    },
    "layers_bytes": {
        "label": "Unique image layers",
        "unit": "bytes",
        "help": "Docker-accounted unique layers, not virtual image sizes.",
    },
    "volumes_bytes": {
        "label": "Volume storage",
        "unit": "bytes",
        "help": "Unknown if any volume size is unavailable.",
    },
    "build_cache_bytes": {
        "label": "Build cache storage",
        "unit": "bytes",
        "help": "Nonshared Docker build cache.",
    },
}
COMMON = list(METRICS)[:9]
HOST = list(METRICS)[9:]
METRICS.update(EXTRA_METRICS)
METRICS.update(
    {
        key: {"label": label, "unit": unit, "help": help}
        for key, label, unit, help in (
            (
                "restart_count",
                "Container restarts",
                "count",
                "Docker restart counter, refreshed with inventory.",
            ),
            (
                "oom_killed",
                "OOM-killed containers",
                "count",
                "Last state reports an OOM kill; not cumulative OOM events.",
            ),
            (
                "healthy",
                "Healthy containers",
                "count",
                "Containers passing a configured healthcheck.",
            ),
            (
                "unhealthy",
                "Unhealthy containers",
                "count",
                "Containers failing a configured healthcheck.",
            ),
            (
                "health_starting",
                "Healthchecks starting",
                "count",
                "Containers whose configured healthcheck is starting.",
            ),
            (
                "uptime_seconds",
                "Container uptime",
                "seconds",
                "Time since the current container start; stopped containers are unavailable.",
            ),
            (
                "memory_configured_limit",
                "Configured memory limit",
                "bytes",
                "HostConfig.Memory; zero means no explicit limit.",
            ),
            (
                "cpu_limit_cores",
                "Configured CPU quota",
                "count",
                "CPU quota expressed in logical cores; unavailable if unlimited.",
            ),
            (
                "pids_configured_limit",
                "Configured process limit",
                "count",
                "Configured PIDs limit; an unlimited value is unavailable.",
            ),
            (
                "cache_reclaimable_bytes",
                "Reclaimable build cache",
                "bytes",
                "Docker-reported unused, nonshared build cache.",
            ),
            (
                "host_memory_total",
                "Installed host memory",
                "bytes",
                "Capacity of the Docker node returned by /info, not container usage.",
            ),
            (
                "host_cpus",
                "Host logical CPUs",
                "count",
                "Capacity of the Docker node returned by /info.",
            ),
            ("images_count", "Images", "count", "Images discovered in the environment inventory."),
            (
                "volumes_count",
                "Volumes",
                "count",
                "Volumes discovered in the environment inventory.",
            ),
            (
                "networks_count",
                "Networks",
                "count",
                "Networks discovered in the environment inventory.",
            ),
            (
                "stacks_count",
                "Stacks",
                "count",
                "Portainer stacks and projects discovered from Docker labels.",
            ),
            (
                "services_count",
                "Swarm services",
                "count",
                "Services returned by the Swarm manager; unavailable on non-manager engines.",
            ),
            (
                "nodes_count",
                "Swarm nodes",
                "count",
                "Nodes returned by the Swarm manager; unavailable on non-manager engines.",
            ),
            ("stopped", "Stopped containers", "count", "Containers with an exited state."),
            ("paused", "Paused containers", "count", "Containers with a paused state."),
            ("restarting", "Restarting containers", "count", "Containers with a restarting state."),
            (
                "image_bytes",
                "Virtual image size",
                "bytes",
                "Virtual image size; summing images may double-count shared layers.",
            ),
            (
                "image_shared_bytes",
                "Shared image layers",
                "bytes",
                "Shared layer bytes reported by Docker for this image.",
            ),
            (
                "volume_size_bytes",
                "Volume size",
                "bytes",
                "Volume driver reported size; missing is not zero.",
            ),
            (
                "references",
                "Resource references",
                "count",
                "Container references to this image or volume.",
            ),
            (
                "desired_tasks",
                "Desired service tasks",
                "count",
                "Desired Swarm service tasks reported by the manager.",
            ),
            (
                "running_tasks",
                "Running service tasks",
                "count",
                "Running Swarm service tasks reported by the manager.",
            ),
            (
                "completed_tasks",
                "Completed service tasks",
                "count",
                "Completed tasks reported in ServiceStatus, when available.",
            ),
            (
                "node_cpus",
                "Node logical CPUs",
                "count",
                "Swarm node NanoCPUs normalized to logical cores.",
            ),
            (
                "node_memory_bytes",
                "Node memory capacity",
                "bytes",
                "Installed memory capacity reported in Swarm node resources.",
            ),
            (
                "node_ready",
                "Node ready",
                "count",
                "One if the Swarm node is ready, zero for another known state.",
            ),
            (
                "docker_fs_total_bytes",
                "Docker filesystem capacity",
                "bytes",
                "Capacity of the partition hosting Docker data, from compatible Portainer Agents.",
            ),
            (
                "docker_fs_available_bytes",
                "Docker filesystem available",
                "bytes",
                "Bytes available to unprivileged processes on Docker's partition.",
            ),
            (
                "docker_fs_unavailable_bytes",
                "Docker filesystem used / reserved",
                "bytes",
                "Capacity minus available bytes; includes reserved blocks and non-Docker data.",
            ),
            (
                "docker_artifact_bytes",
                "Agent Docker artifact bytes",
                "bytes",
                "Agent-reported Docker artifact total; excludes non-Docker data.",
            ),
            (
                "physical_disk_bytes",
                "Physical disk capacity",
                "bytes",
                "Hardware disk capacity from Portainer Agent host inventory; not used/free space.",
            ),
        )
    }
)
CONTAINER_ONLY = {
    "memory_limit_percent",
    "pids_limit_percent",
    "cpu_throttled_percent",
    "memory_limit_bytes",
    "pids_limit",
    "uptime_seconds",
    "memory_configured_limit",
    "cpu_limit_cores",
    "pids_configured_limit",
}
for key in CONTAINER_ONLY:
    METRICS[key]["additive"] = False
COUNTS = [
    "restart_count",
    "oom_killed",
    "healthy",
    "unhealthy",
    "health_starting",
    "stopped",
    "paused",
    "restarting",
]
GROUP = COMMON + [k for k in EXTRA_METRICS if k not in CONTAINER_ONLY] + COUNTS
KINDS = {
    "container": GROUP + sorted(CONTAINER_ONLY),
    "stack": GROUP,
    "network": GROUP,
    "environment": GROUP
    + HOST
    + [
        "cache_reclaimable_bytes",
        "host_memory_total",
        "host_cpus",
        "images_count",
        "volumes_count",
        "networks_count",
        "stacks_count",
        "services_count",
        "nodes_count",
        "docker_fs_total_bytes",
        "docker_fs_available_bytes",
        "docker_fs_unavailable_bytes",
        "docker_artifact_bytes",
    ],
    "image": ["image_bytes", "image_shared_bytes", "references"],
    "volume": ["volume_size_bytes", "references"],
    "service": ["desired_tasks", "running_tasks", "completed_tasks"],
    "node": ["node_cpus", "node_memory_bytes", "node_ready"],
    "disk": ["physical_disk_bytes"],
}
KINDS = {kind: list(dict.fromkeys(keys)) for kind, keys in KINDS.items()}


def is_raw_metric(metric):
    return (
        isinstance(metric, str)
        and len(metric) <= 388
        and bool(
            re.fullmatch(
                r"raw\.(?:cpu_stats|precpu_stats|memory_stats|pids_stats|networks|blkio_stats|storage_stats|num_procs)(?:\.[A-Za-z0-9_~:/-]+)*",
                metric,
            )
        )
    )


def metric_info(metric):
    if metric in METRICS:
        return METRICS[metric]
    if not is_raw_metric(metric):
        raise ValueError("Unknown metric.")
    return {
        "label": "Docker raw / " + metric[4:],
        "unit": "native",
        "additive": False,
        "help": "Native numeric Docker stats field: "
        + metric[4:]
        + ". Units follow the Engine API; array indices and interface/device paths are source-specific. No interpolation or unit conversion.",
    }


def metric_catalog(snapshot, dashboards=()):
    metrics = dict(METRICS)
    kinds = {k: list(v) for k, v in KINDS.items()}
    discovered = {
        "raw." + key
        for env in snapshot.get("environments", [])
        for c in env.get("containers", [])
        for key in (c.get("stats") or {}).get("raw_metrics", {})
    }
    discovered.update(
        w["metric"] for d in dashboards for w in d["widgets"] if is_raw_metric(w["metric"])
    )
    for key in sorted(discovered):
        if is_raw_metric(key):
            metrics[key] = metric_info(key)
            kinds["container"].append(key)
    return {"metrics": metrics, "kinds": kinds, "visuals": VISUALS, "colors": COLORS}


VISUALS = ("line", "stat", "gauge", "bar", "table")
COLORS = ("green", "blue", "amber", "violet", "cyan")


def bounded_string(value, label, maximum=160, empty=False):
    if (
        not isinstance(value, str)
        or len(value.strip()) > maximum
        or (not empty and not value.strip())
    ):
        raise ValueError(f"{label} must be between {0 if empty else 1} and {maximum} characters.")
    return value.strip()


def validate_dashboard(raw):
    if not isinstance(raw, dict):
        raise ValueError("A dashboard object is required.")
    eid = raw.get("environment_id")
    if type(eid) is not int or eid < 1:
        raise ValueError("Choose an environment.")
    source = bounded_string(raw.get("source_id"), "Connection identity", 64)
    widgets = raw.get("widgets")
    if not isinstance(widgets, list) or len(widgets) > 64:
        raise ValueError("A dashboard supports up to 64 panels.")
    result = {
        "name": bounded_string(raw.get("name"), "Dashboard name", 100),
        "description": bounded_string(raw.get("description", ""), "Description", 500, True),
        "source_id": source,
        "environment_id": eid,
        "widgets": [],
        "range_minutes": raw.get("range_minutes", 15),
        "refresh_seconds": raw.get("refresh_seconds", 5),
        "theme": raw.get("theme", "system"),
    }
    if result["range_minutes"] not in (5, 15, 60, 360, 1440) or result["refresh_seconds"] not in (
        5,
        10,
        30,
        60,
    ):
        raise ValueError("Choose a supported time range and refresh interval.")
    if result["theme"] not in ("light", "dark", "system"):
        raise ValueError("Invalid dashboard theme.")
    seen = set()
    for w in widgets:
        if not isinstance(w, dict):
            raise ValueError("Invalid panel.")
        kind, metric = w.get("kind"), w.get("metric")
        if kind not in KINDS or not (
            metric in KINDS[kind] or kind == "container" and is_raw_metric(metric)
        ):
            raise ValueError("The metric is not supported for this resource.")
        ids = w.get("sources")
        if not isinstance(ids, list) or not 1 <= len(ids) <= 16:
            raise ValueError("Choose between 1 and 16 resources per panel.")
        ids = list(dict.fromkeys(bounded_string(i, "Resource name", 256) for i in ids))
        identity = bounded_string(w.get("id", uuid.uuid4().hex), "Panel ID", 64)
        if not re.fullmatch(r"[A-Za-z0-9_-]+", identity) or identity in seen:
            raise ValueError("Panel IDs must be unique.")
        seen.add(identity)
        panel = {
            "id": identity,
            "title": bounded_string(w.get("title"), "Panel title", 120),
            "kind": kind,
            "sources": ids,
            "metric": metric,
            "visual": w.get("visual", "line"),
            "width": w.get("width", 6),
            "height": w.get("height", 260),
            "aggregate": w.get("aggregate", "compare"),
            "color": w.get("color", "green"),
            "min": w.get("min", 0),
            "max": w.get("max", 100),
            "threshold": w.get("threshold"),
        }
        if (
            panel["visual"] not in VISUALS
            or panel["width"] not in (4, 6, 8, 12)
            or panel["height"] not in (200, 260, 340, 420)
        ):
            raise ValueError("Invalid panel appearance.")
        if panel["aggregate"] not in ("sum", "compare") or panel["color"] not in COLORS:
            raise ValueError("Invalid panel options.")
        if (
            len(ids) > 1
            and panel["aggregate"] == "sum"
            and metric_info(metric).get("additive") is False
        ):
            raise ValueError(
                "This metric must be compared individually; adding its values is not meaningful."
            )
        if panel["visual"] == "gauge" and len(ids) > 1 and panel["aggregate"] != "sum":
            raise ValueError("A gauge with multiple resources must use Sum selected resources.")
        for key in ("min", "max", "threshold"):
            v = panel[key]
            if key == "threshold" and v is None:
                continue
            if type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 1e18:
                raise ValueError("Panel limits must be finite numbers.")
        if panel["max"] <= panel["min"]:
            raise ValueError("Maximum must be greater than minimum.")
        result["widgets"].append(panel)
    return result


def strict_sum(values):
    values = list(values)
    return None if any(v is None for v in values) else sum(values)


def metric_values(environment, kind, resource):
    if not environment or environment.get("status") in ("offline", "unsupported"):
        return None
    if kind == "environment":
        if resource != "host":
            return None
        metrics = environment.get("metrics") or {}
        storage = environment.get("storage") or {}
        values = member_values(environment.get("containers") or [], False)
        values.update({k: metrics.get(k) for k in ("cpu_host_percent", "memory_host_percent")})
        values.update(
            {k: storage.get(k) for k in ("writable_bytes", "layers_bytes", "volumes_bytes")}
        )
        values["build_cache_bytes"] = storage.get("cache_bytes")
        values["cache_reclaimable_bytes"] = storage.get("cache_reclaimable_bytes")
        host = environment.get("host") or {}
        values.update(host_memory_total=host.get("memory_total"), host_cpus=host.get("cpus"))
        values.update(
            {
                key + "_count": len(environment[key]) if key in environment else None
                for key in ("images", "volumes", "networks", "stacks", "services", "nodes")
            }
        )
        if not host.get("swarm_manager"):
            values["nodes_count"] = values["services_count"] = None
        values.update(environment.get("agent_storage") or {})
        return values
    if kind in ("image", "volume", "service", "node", "disk"):
        collection = {
            "image": "images",
            "volume": "volumes",
            "service": "services",
            "node": "nodes",
            "disk": "physical_disks",
        }[kind]
        item = next(
            (
                v
                for v in environment.get(collection, [])
                if v.get("id" if kind == "image" else "name") == resource
            ),
            None,
        )
        if not item:
            return None
        if kind == "image":
            return {
                "image_bytes": item.get("size"),
                "image_shared_bytes": item.get("shared_size"),
                "references": item.get("containers"),
            }
        if kind == "volume":
            return {"volume_size_bytes": item.get("size"), "references": item.get("references")}
        if kind == "service":
            return {k: item.get(k) for k in KINDS[kind]}
        if kind == "disk":
            return {"physical_disk_bytes": item.get("size")}
        capacity = item.get("resources") or {}
        return {
            "node_cpus": capacity["NanoCPUs"] / 1e9
            if capacity.get("NanoCPUs") is not None
            else None,
            "node_memory_bytes": capacity.get("MemoryBytes"),
            "node_ready": int(item["status"] == "ready") if item.get("status") else None,
        }
    containers = environment.get("containers") or []
    if kind == "container":
        members = [c for c in containers if c["name"] == resource]
        if not members:
            return None
    elif kind == "stack":
        if not any(s["name"] == resource for s in environment.get("stacks") or []):
            return None
        members = [c for c in containers if c.get("stack") == resource]
    elif kind == "network":
        if not any(n["name"] == resource for n in environment.get("networks") or []):
            return None
        members = [
            c for c in containers if any(n["name"] == resource for n in c.get("networks") or [])
        ]
    else:
        return None
    return member_values(members, kind == "container")


def member_values(members, single=False):
    active = [c for c in members if c.get("state") == "running"]
    fields = list(dict.fromkeys(COMMON[:6] + list(EXTRA_METRICS)))
    values = {k: strict_sum((c.get("stats") or {}).get(k) for c in active) for k in fields}
    # A stopped container has no live telemetry; count metrics remain meaningful.
    if single and not active:
        values = {k: None for k in values}
    values.update(
        writable_bytes=strict_sum(c.get("writable_bytes") for c in members),
        running=len(active),
        total=len(members),
    )
    for field in ("restart_count", "oom_killed", "healthy", "unhealthy", "health_starting"):
        values[field] = strict_sum((c.get("telemetry") or {}).get(field) for c in members)
    for field in ("stopped", "paused", "restarting"):
        values[field] = sum(
            c.get("state") == ("exited" if field == "stopped" else field) for c in members
        )
    if single:
        values.update(members[0].get("telemetry") or {})
        values.update(
            {
                "raw." + key: value
                for key, value in (members[0].get("stats") or {}).get("raw_metrics", {}).items()
            }
        )
    else:
        for field in CONTAINER_ONLY:
            values.pop(field, None)
    return values


def resources(environment):
    yield "environment", "host"
    for kind, key in (
        ("container", "containers"),
        ("stack", "stacks"),
        ("network", "networks"),
        ("image", "images"),
        ("volume", "volumes"),
        ("service", "services"),
        ("node", "nodes"),
        ("disk", "physical_disks"),
    ):
        for item in environment.get(key) or []:
            yield kind, item["id" if kind == "image" else "name"]
