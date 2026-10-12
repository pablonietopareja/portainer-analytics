#!/usr/bin/env python3
"""Read-only Portainer collector, telemetry normalization and HTTP response helpers."""

from __future__ import annotations

import copy
import datetime as dt
import json
import logging
import re
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler

import requests
from urllib3.exceptions import InsecureRequestWarning

from telemetry import extend_stats

LOG = logging.getLogger("portainer-console")


def utcnow():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def config(clean=True):
    """Return first-use defaults; connection credentials are configured in the UI."""
    return {
        "url": "",
        # Empty first-use input, not a built-in credential.
        "token": "",  # nosec B105
        "verify": True,
        "timeout": 8,
    }


class ApiError(Exception):
    pass


class Client:
    def __init__(self, cfg):
        self.cfg = cfg
        self.local = threading.local()
        if not cfg["verify"]:
            requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

    def get(self, path, params=None, raw=False, target=None):
        if not self.cfg["url"] or not self.cfg["token"]:
            raise ApiError("Configure a Portainer server and API token in the web interface.")
        if not hasattr(self.local, "session"):
            self.local.session = requests.Session()
            self.local.session.headers["X-API-Key"] = self.cfg["token"]
            self.local.session.trust_env = False
        try:
            response = self.local.session.get(
                self.cfg["url"] + path,
                params=params,
                timeout=(self.cfg["timeout"], self.cfg["timeout"]),
                verify=self.cfg["verify"],
                allow_redirects=False,
                headers={"X-PortainerAgent-Target": target} if target else None,
            )
            if not 200 <= response.status_code < 300:
                messages = {
                    401: "Invalid credentials",
                    403: "Permission denied",
                    404: "Resource unavailable",
                    502: "Environment unreachable",
                    503: "Environment unreachable",
                }
                raise ApiError(
                    f"{messages.get(response.status_code, 'Portainer error')} (HTTP {response.status_code})"
                )
            if response.status_code == 204:
                return b"" if raw else None
            return response.content if raw else response.json()
        except requests.Timeout:
            raise ApiError("Request timed out") from None
        except requests.RequestException:
            raise ApiError("Cannot connect to Portainer") from None
        except ValueError:
            raise ApiError("Portainer returned a non-JSON response") from None


def number(value):
    return value if type(value) in (int, float) and value >= 0 else None


def container_metadata(raw):
    state, limits = raw.get("State") or {}, raw.get("HostConfig") or {}
    started = state.get("StartedAt")
    try:
        uptime = (
            max(
                0,
                (
                    dt.datetime.now(dt.timezone.utc)
                    - dt.datetime.fromisoformat(started.replace("Z", "+00:00"))
                ).total_seconds(),
            )
            if state.get("Running")
            else None
        )
    except TypeError, ValueError, AttributeError:
        uptime = None
    health = (state.get("Health") or {}).get("Status")
    quota, period, nano = limits.get("CpuQuota"), limits.get("CpuPeriod"), limits.get("NanoCpus")
    cpu_limit = nano / 1e9 if nano else quota / period if quota and quota > 0 and period else None
    return {
        "restart_count": number(raw.get("RestartCount")),
        "oom_killed": int(state["OOMKilled"]) if type(state.get("OOMKilled")) is bool else None,
        "healthy": int(health == "healthy") if health else None,
        "unhealthy": int(health == "unhealthy") if health else None,
        "health_starting": int(health == "starting") if health else None,
        "uptime_seconds": uptime,
        "memory_configured_limit": number(limits.get("Memory")),
        "cpu_limit_cores": cpu_limit,
        "pids_configured_limit": number(limits.get("PidsLimit")),
        "started_at": started,
    }


def sum_known(values):
    values = list(values)
    if not values:
        return 0
    return sum(values) if all(v is not None for v in values) else None


def stack_name(labels):
    for key in (
        "io.portainer.stack.name",
        "com.docker.compose.project",
        "com.docker.stack.namespace",
    ):
        if labels.get(key):
            return labels[key]
    return None


def stats_metrics(raw, previous=None, elapsed=None):
    current = raw.get("cpu_stats") or {}
    before = raw.get("precpu_stats") or {}
    cpu = None
    cores = current.get("online_cpus") or len(
        (current.get("cpu_usage") or {}).get("percpu_usage") or []
    )
    c0 = (before.get("cpu_usage") or {}).get("total_usage")
    c1 = (current.get("cpu_usage") or {}).get("total_usage")
    s0, s1 = before.get("system_cpu_usage"), current.get("system_cpu_usage")
    if previous:
        try:
            t1 = dt.datetime.fromisoformat(raw["read"].replace("Z", "+00:00"))
            t0 = dt.datetime.fromisoformat(previous["sample_at"].replace("Z", "+00:00"))
            elapsed = (t1 - t0).total_seconds()
        except KeyError, TypeError, ValueError, AttributeError:
            pass
    if (not s0 or not c0) and previous:
        c0, s0 = previous.get("cpu_total"), previous.get("system_cpu_total")
    if (
        all(isinstance(x, (int, float)) for x in (c0, c1, s0, s1))
        and s1 > s0
        and c1 >= c0
        and cores
    ):
        cpu = (c1 - c0) / (s1 - s0) * cores * 100
    elif (
        previous
        and elapsed
        and elapsed > 0
        and c1 is not None
        and previous.get("cpu_total") is not None
    ):
        delta = c1 - previous["cpu_total"]
        if delta >= 0:
            cpu = delta / (elapsed * 1e9) * 100
    memory = raw.get("memory_stats") or {}
    ms = memory.get("stats") or {}
    usage = number(memory.get("usage"))
    inactive = number(ms.get("total_inactive_file", ms.get("inactive_file")))
    # Docker CLI retains raw usage when the inactive counter is absent or inconsistent.
    working = (
        usage - inactive
        if usage is not None and inactive is not None and inactive < usage
        else usage
    )
    if usage is None:
        inactive = None
    networks = raw.get("networks")
    rx = sum_known(number(v.get("rx_bytes")) for v in networks.values()) if networks else None
    tx = sum_known(number(v.get("tx_bytes")) for v in networks.values()) if networks else None
    blk = (raw.get("blkio_stats") or {}).get("io_service_bytes_recursive")
    reads = (
        sum(number(x.get("value")) or 0 for x in blk if str(x.get("op")).lower() == "read")
        if blk is not None
        else None
    )
    writes = (
        sum(number(x.get("value")) or 0 for x in blk if str(x.get("op")).lower() == "write")
        if blk is not None
        else None
    )
    out = {
        "cpu_percent": cpu,
        "cpu_total": c1,
        "system_cpu_total": s1,
        "memory_bytes": working,
        "memory_raw_bytes": usage,
        "cache_bytes": inactive,
        "memory_limit": number(memory.get("limit")),
        "rx_bytes": rx,
        "tx_bytes": tx,
        "block_read_bytes": reads,
        "block_write_bytes": writes,
        "pids": number((raw.get("pids_stats") or {}).get("current")),
        "sample_at": raw.get("read"),
        "rx_rate": None,
        "tx_rate": None,
    }
    for key in ("rx", "tx"):
        old = (previous or {}).get(key + "_bytes")
        new = out[key + "_bytes"]
        if elapsed and elapsed > 0 and old is not None and new is not None and new >= old:
            out[key + "_rate"] = (new - old) / elapsed
    out.update(extend_stats(raw, previous, elapsed, out))
    return out


def normalize_df(df):
    """Normalize legacy and v1.52+ Engine responses without summing shared layers."""
    if not isinstance(df, dict):
        return df
    df = dict(df)
    mapping = {
        "Images": ("ImageUsage", "ImagesUsage"),
        "Containers": ("ContainerUsage", "ContainersUsage"),
        "Volumes": ("VolumeUsage", "VolumesUsage"),
        "BuildCache": ("BuildCacheUsage",),
    }
    for name, aliases in mapping.items():
        for alias in aliases:
            if isinstance(df.get(alias), dict):
                df[name] = df[alias].get("Items") or []
                df[aliases[0]] = df[alias]
                break
    return df


def storage_summary(df):
    if not isinstance(df, dict):
        return {"available": False}
    volumes = df.get("Volumes") or []
    cache = df.get("BuildCache") or []
    df = normalize_df(df)
    modern = "ImageUsage" in df
    if modern:
        return {
            "available": True,
            "layers_bytes": number((df.get("ImageUsage") or {}).get("TotalSize", 0)),
            "writable_bytes": number((df.get("ContainerUsage") or {}).get("TotalSize", 0)),
            "volumes_bytes": number((df.get("VolumeUsage") or {}).get("TotalSize", 0)),
            "cache_bytes": number((df.get("BuildCacheUsage") or {}).get("TotalSize", 0)),
            "cache_reclaimable_bytes": number(
                (df.get("BuildCacheUsage") or {}).get("Reclaimable", 0)
            ),
            "volume_unknown_count": None,
            "host_total_bytes": None,
            "host_used_bytes": None,
        }
    return {
        "available": True,
        "layers_bytes": number(df.get("LayersSize")),
        "writable_bytes": sum_known(number(x.get("SizeRw", 0)) for x in df.get("Containers") or []),
        "volumes_bytes": sum_known(number((x.get("UsageData") or {}).get("Size")) for x in volumes),
        "volume_known_bytes": sum(
            number((x.get("UsageData") or {}).get("Size")) or 0 for x in volumes
        ),
        "volume_unknown_count": sum(
            number((x.get("UsageData") or {}).get("Size")) is None for x in volumes
        ),
        "cache_bytes": sum_known(number(x.get("Size", 0)) for x in cache if not x.get("Shared")),
        "cache_reclaimable_bytes": sum_known(
            number(x.get("Size", 0)) for x in cache if not x.get("InUse") and not x.get("Shared")
        ),
        "host_total_bytes": None,
        "host_used_bytes": None,
    }


SECRET = re.compile(
    r"password|passwd|secret|token|api.?key|authorization|credential|private.?key|cookie", re.I
)


def redact(value, key=""):
    if SECRET.search(key):
        return "[hidden]"
    if key.lower() == "env" and isinstance(value, list):
        return [str(x).split("=", 1)[0] + "=[hidden]" for x in value]
    if isinstance(value, dict):
        return {k: redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, key) for v in value]
    if isinstance(value, str):
        value = re.sub(r"ptr_[A-Za-z0-9+/=_-]+", "[hidden]", value)
        value = re.sub(r"(?i)(https?://)[^/\s:@]+:[^/\s@]+@", r"\1[hidden]@", value)
        value = re.sub(
            r"""(?i)((?:password|passwd|token|secret|api[_-]?key)["']?\s*[=:]\s*["']?)[^\s,;"'}]+""",
            r"\1[hidden]",
            value,
        )
        value = re.sub(r"(?i)\b(Bearer|Basic)\s+[A-Za-z0-9+/_.=-]+", r"\1 [hidden]", value)
    return value


def decode_logs(content):
    out, i = [], 0
    while i + 8 <= len(content) and content[i] in (0, 1, 2) and content[i + 1 : i + 4] == b"\0\0\0":
        size = int.from_bytes(content[i + 4 : i + 8], "big")
        if i + 8 + size > len(content):
            break
        out.append(content[i + 8 : i + 8 + size])
        i += 8 + size
    data = b"".join(out) if out and i == len(content) else content
    text = data.decode("utf-8", "replace")
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
    text = re.sub(
        r"(?i)((?:password|token|secret|api[_-]?key)\s*[=:]\s*)[^\s,;]+", r"\1[hidden]", text
    )
    return redact(text)[-150000:]


class Collector:
    def __init__(self, client, interval=5, inventory_interval=30, storage_interval=60):
        self.client = client
        self.interval = max(2, interval)
        self.inventory_interval = max(10, inventory_interval)
        self.storage_interval = max(30, storage_interval)
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.state = {
            "started_at": utcnow(),
            "updated_at": None,
            "sequence": 0,
            "status": "connecting",
            "error": None,
            "interval": self.interval,
            "inventory_interval": self.inventory_interval,
            "storage_interval": self.storage_interval,
            "environments": [],
            "read_only": True,
        }
        self.cache = {}
        self.pool = ThreadPoolExecutor(max_workers=12, thread_name_prefix="portainer-io")
        self.thread = threading.Thread(target=self.run, name="portainer-poll", daemon=True)

    def start(self):
        self.thread.start()

    def snapshot(self):
        with self.lock:
            return copy.deepcopy(self.state)

    def docker(self, eid, path, params=None, raw=False):
        version = self.cache.get(eid, {}).get("api_version")
        prefix = f"v{version}/" if version else ""
        match = re.match(r"containers/([^/]+)/", path)
        target = self.cache.get(eid, {}).get("targets", {}).get(match[1]) if match else None
        return self.client.get(
            f"/api/endpoints/{eid}/docker/{prefix}{path}",
            params,
            raw,
            **({"target": target} if target else {}),
        )

    def check_stop(self):
        if self.stop.is_set():
            raise ApiError("Console stopped")

    def run(self):
        while not self.stop.is_set():
            if not self.client.cfg.get("url") or not self.client.cfg.get("token"):
                with self.lock:
                    self.state.update(status="unconfigured", error=None)
                self.stop.wait(1)
                continue
            start = time.monotonic()
            try:
                endpoints = self.client.get("/api/endpoints")
                if isinstance(endpoints, dict):
                    endpoints = endpoints.get("value", [])
                self.check_stop()
                stacks_error = None
                try:
                    stacks = self.client.get("/api/stacks")
                    if not isinstance(stacks, list):
                        stacks = []
                except ApiError as exc:
                    stacks, stacks_error = [], str(exc)
                environments = []
                with ThreadPoolExecutor(max_workers=min(4, max(1, len(endpoints)))) as envpool:
                    jobs = {
                        envpool.submit(self.collect, e, stacks, stacks_error): e for e in endpoints
                    }
                    for job in as_completed(jobs):
                        e = jobs[job]
                        try:
                            environments.append(job.result())
                        except Exception as exc:
                            LOG.error(
                                "Collection failed for environment %s (%s)",
                                e.get("Id"),
                                type(exc).__name__,
                            )
                            old = self.cache.get(e.get("Id"), {}).get("output")
                            failed = (
                                copy.deepcopy(old)
                                if old
                                else {"id": e.get("Id"), "name": e.get("Name"), "containers": []}
                            )
                            failed.update(
                                status="offline",
                                error=str(exc)
                                if isinstance(exc, ApiError)
                                else "Could not collect environment data",
                            )
                            environments.append(failed)
                with self.lock:
                    states = [e["status"] for e in environments]
                    status = (
                        "offline"
                        if states and all(s == "offline" for s in states)
                        else "degraded"
                        if any(s != "live" for s in states)
                        else "live"
                    )
                    self.state.update(
                        environments=sorted(environments, key=lambda x: x["id"]),
                        status=status,
                        error=None,
                        updated_at=utcnow(),
                        sequence=self.state["sequence"] + 1,
                        cycle_seconds=round(time.monotonic() - start, 2),
                    )
            except Exception as exc:
                with self.lock:
                    self.state.update(
                        status="offline",
                        error=str(exc)
                        if isinstance(exc, ApiError)
                        else "Could not refresh Portainer",
                    )
            self.stop.wait(max(0.2, self.interval - (time.monotonic() - start)))

    def collect(self, endpoint, stacks, stacks_error):
        self.check_stop()
        eid = endpoint["Id"]
        item = self.cache.setdefault(
            eid, {"history": deque(maxlen=180), "previous": {}, "inventory_at": 0, "storage_at": 0}
        )
        if endpoint.get("Type") not in (1, 2, 4):
            return {
                "id": eid,
                "name": endpoint.get("Name"),
                "type": endpoint.get("Type"),
                "status": "unsupported",
                "error": "This environment does not provide a Docker API supported by this console.",
                "containers": [],
                "history": [],
            }
        now = time.monotonic()
        inventory_refreshed = False
        errors = []
        if stacks_error:
            errors.append({"resource": "stacks", "message": stacks_error})
        if now - item["inventory_at"] >= self.inventory_interval:
            if not item.get("api_version"):
                ver = self.client.get(f"/api/endpoints/{eid}/docker/version")

                def vt(s):
                    return tuple(int(p) for p in s.split("."))

                target = max(
                    vt(ver.get("MinAPIVersion", "1.24")),
                    min(vt(ver.get("ApiVersion", "1.47")), (1, 47)),
                )
                item["api_version"] = ".".join(map(str, target))
                item["version"] = ver
            calls = {
                "info": ("info", None),
                "containers": ("containers/json", {"all": "true"}),
                "images": ("images/json", {"all": "true"}),
                "volumes": ("volumes", None),
                "networks": ("networks", None),
            }
            self.check_stop()
            results = {
                self.pool.submit(self.docker, eid, path, params): name
                for name, (path, params) in calls.items()
            }
            inv_errors = []
            for job in as_completed(results):
                name = results[job]
                try:
                    item[name] = job.result()
                except ApiError as exc:
                    inv_errors.append({"resource": name, "message": str(exc)})
                    if name in ("info", "containers"):
                        raise
            item["inventory_errors"] = inv_errors
            item["inventory_at"] = now
            item["inventory_updated_at"] = utcnow()
            inventory_refreshed = True
            info = item.get("info") or {}
            if (info.get("Swarm") or {}).get("ControlAvailable"):
                for key in ("services", "nodes"):
                    try:
                        item[key] = self.docker(
                            eid, key, {"status": "true"} if key == "services" else None
                        )
                    except ApiError as exc:
                        inv_errors.append({"resource": key, "message": str(exc)})
        errors.extend(item.get("inventory_errors", []))
        self.check_stop()
        if now - item["storage_at"] >= self.storage_interval:
            try:
                item["df"] = normalize_df(self.docker(eid, "system/df", {"verbose": "true"}))
                item["storage_error"] = None
                item["storage_updated_at"] = utcnow()
            except ApiError as exc:
                item["storage_error"] = str(exc)
            item["storage_at"] = now
        if item.get("storage_error"):
            errors.append({"resource": "storage", "message": item["storage_error"]})
        if (
            endpoint.get("Type") in (2, 4)
            and now - item.get("agent_at", 0) >= self.storage_interval
        ):
            item["agent_at"] = now
            target = (item.get("info") or {}).get("Name")
            capabilities = {}
            for name, path in (("host", "info"), ("storage", "docker-storage")):
                try:
                    data = self.client.get(
                        f"/api/endpoints/{eid}/docker/v2/host/{path}", target=target
                    )
                    item["agent_" + name] = data if isinstance(data, dict) else {}
                    capabilities[name] = "available" if isinstance(data, dict) else "unavailable"
                except ApiError:
                    item["agent_" + name] = {}
                    capabilities[name] = "unsupported or not permitted"
            item["agent_capabilities"] = capabilities
        raw_containers = item.get("containers") or []
        item["targets"] = {
            c["Id"]: ((c.get("Portainer") or {}).get("Agent") or {}).get("NodeName")
            for c in raw_containers
        }
        if inventory_refreshed:
            metadata, metadata_errors = {}, {}
            jobs = {
                self.pool.submit(self.docker, eid, f"containers/{c['Id']}/json"): c["Id"]
                for c in raw_containers
            }
            for job in as_completed(jobs):
                cid = jobs[job]
                try:
                    metadata[cid] = container_metadata(job.result())
                except ApiError as exc:
                    metadata_errors[cid] = str(exc)
            item["metadata"], item["metadata_errors"] = metadata, metadata_errors
        self.check_stop()
        stat_jobs = {
            self.pool.submit(
                self.docker,
                eid,
                f"containers/{c['Id']}/stats",
                {"stream": "false", "one-shot": "true"},
            ): c["Id"]
            for c in raw_containers
            if c.get("State") == "running"
        }
        stats, stat_errors = {}, {}
        for job in as_completed(stat_jobs):
            cid = stat_jobs[job]
            try:
                raw = job.result()
                measured = time.monotonic()
                previous = item["previous"].get(cid)
                elapsed = measured - previous["time"] if previous else None
                stats[cid] = stats_metrics(raw, previous, elapsed)
                item["previous"][cid] = dict(stats[cid], time=measured)
            except ApiError as exc:
                stat_errors[cid] = str(exc)
        valid_ids = {c["Id"] for c in raw_containers if c.get("State") == "running"}
        item["previous"] = {cid: v for cid, v in item["previous"].items() if cid in valid_ids}
        df = item.get("df") or {}
        dfcontainers = {c["Id"]: c for c in df.get("Containers") or []}
        containers = []
        for c in raw_containers:
            labels = c.get("Labels") or {}
            cid = c["Id"]
            sizes = dfcontainers.get(cid, {})
            containers.append(
                {
                    "id": cid,
                    "name": (c.get("Names") or [cid[:12]])[0].lstrip("/"),
                    "image": c.get("Image"),
                    "image_id": c.get("ImageID"),
                    "state": c.get("State"),
                    "status": c.get("Status"),
                    "created": c.get("Created"),
                    "stack": stack_name(labels),
                    "service": labels.get("com.docker.compose.service")
                    or labels.get("com.docker.swarm.service.name"),
                    "ports": c.get("Ports") or [],
                    "mounts": [
                        {k: m.get(k) for k in ("Type", "Name", "Source", "Destination", "RW")}
                        for m in c.get("Mounts") or []
                    ],
                    "networks": [
                        {"name": n, "ip": v.get("IPAddress"), "gateway": v.get("Gateway")}
                        for n, v in ((c.get("NetworkSettings") or {}).get("Networks") or {}).items()
                    ],
                    "writable_bytes": number(sizes.get("SizeRw", 0))
                    if cid in dfcontainers
                    else None,
                    "rootfs_bytes": number(sizes.get("SizeRootFs")),
                    "stats": stats.get(cid),
                    "stats_error": stat_errors.get(cid),
                    "node_name": item["targets"].get(cid),
                    "telemetry": item.get("metadata", {}).get(cid, {}),
                    "metadata_error": item.get("metadata_errors", {}).get(cid),
                }
            )
        containers.sort(key=lambda x: (x["state"] != "running", x["name"].lower()))
        info = item.get("info") or {}
        active = [c for c in containers if c["state"] == "running"]

        def total(field):
            return sum_known((c.get("stats") or {}).get(field) for c in active)

        cpu = total("cpu_percent")
        mem = total("memory_bytes")
        hostmem = number(info.get("MemTotal"))
        cpus = number(info.get("NCPU"))
        multi_node = len({c["node_name"] for c in containers if c.get("node_name")}) > 1
        metrics = {
            "cpu_percent": cpu,
            "cpu_host_percent": cpu / cpus if cpu is not None and cpus else None,
            "memory_bytes": mem,
            "memory_raw_bytes": total("memory_raw_bytes"),
            "cache_bytes": total("cache_bytes"),
            "memory_host_percent": mem / hostmem * 100 if mem is not None and hostmem else None,
            "rx_rate": total("rx_rate"),
            "tx_rate": total("tx_rate"),
            "pids": total("pids"),
            "running": len(active),
            "total": len(containers),
            "stats_available": len(stats),
            "stats_expected": len(active),
        }
        if multi_node:
            metrics["cpu_host_percent"] = metrics["memory_host_percent"] = None
        metrics["memory_available"] = sum(
            (c.get("stats") or {}).get("memory_bytes") is not None for c in active
        )
        metrics["cpu_available"] = sum(
            (c.get("stats") or {}).get("cpu_percent") is not None for c in active
        )
        sampled_at = utcnow()
        item["history"].append(dict(metrics, time=sampled_at))
        dfimages = {x["Id"]: x for x in df.get("Images") or []}
        images = []
        for image in item.get("images") or []:
            use = dfimages.get(image["Id"], {})
            images.append(
                {
                    "id": image["Id"],
                    "tags": image.get("RepoTags") or [],
                    "size": number(image.get("Size")),
                    "shared_size": number(use.get("SharedSize")),
                    "containers": len([c for c in containers if c["image_id"] == image["Id"]]),
                    "created": image.get("Created"),
                    "labels": redact(image.get("Labels") or {}),
                }
            )
        usage = {v["Name"]: v.get("UsageData") or {} for v in df.get("Volumes") or []}
        volumes = []
        for v in (item.get("volumes") or {}).get("Volumes") or []:
            u = usage.get(v["Name"], v.get("UsageData") or {})
            volumes.append(
                {
                    "name": v["Name"],
                    "driver": v.get("Driver"),
                    "scope": v.get("Scope"),
                    "mountpoint": v.get("Mountpoint"),
                    "created": v.get("CreatedAt"),
                    "size": number(u.get("Size")),
                    "references": number(u.get("RefCount")),
                    "containers": [
                        c["name"]
                        for c in containers
                        if any(m.get("Name") == v["Name"] for m in c["mounts"])
                    ],
                    "labels": redact(v.get("Labels") or {}),
                }
            )
        networks = [
            {
                "id": n.get("Id"),
                "name": n.get("Name"),
                "driver": n.get("Driver"),
                "scope": n.get("Scope"),
                "internal": n.get("Internal"),
                "attachable": n.get("Attachable"),
                "ipam": (n.get("IPAM") or {}).get("Config") or [],
                "containers": [
                    c["name"]
                    for c in containers
                    if any(x["name"] == n.get("Name") for x in c["networks"])
                ],
            }
            for n in item.get("networks") or []
        ]
        stackmap = {}
        for s in stacks:
            if s.get("EndpointId", s.get("EndpointID")) == eid:
                stackmap[s["Name"]] = {
                    "id": s.get("Id"),
                    "name": s["Name"],
                    "type": s.get("Type"),
                    "status": s.get("Status"),
                    "source": "Portainer",
                    "created": s.get("CreationDate"),
                }
        for c in containers:
            if c["stack"] and c["stack"] not in stackmap:
                stackmap[c["stack"]] = {
                    "id": None,
                    "name": c["stack"],
                    "source": "Docker labels",
                    "type": 2,
                    "status": None,
                }
        for name, s in stackmap.items():
            members = [c for c in containers if c["stack"] == name]
            running = [c for c in members if c["state"] == "running"]
            s.update(
                containers=[c["id"] for c in members],
                running=len(running),
                total=len(members),
                memory_bytes=sum_known((c.get("stats") or {}).get("memory_bytes") for c in running),
                cpu_percent=sum_known((c.get("stats") or {}).get("cpu_percent") for c in running),
                writable_bytes=sum_known(c.get("writable_bytes") for c in members),
            )
        services = [
            {
                "id": s.get("ID"),
                "name": (s.get("Spec") or {}).get("Name"),
                "image": (
                    ((s.get("Spec") or {}).get("TaskTemplate") or {}).get("ContainerSpec") or {}
                ).get("Image"),
                "mode": (s.get("Spec") or {}).get("Mode"),
                "ports": (s.get("Endpoint") or {}).get("Ports") or [],
                "update": s.get("UpdateStatus"),
                "desired_tasks": number(
                    (s.get("ServiceStatus") or {}).get(
                        "DesiredTasks",
                        (((s.get("Spec") or {}).get("Mode") or {}).get("Replicated") or {}).get(
                            "Replicas"
                        ),
                    )
                ),
                "running_tasks": number((s.get("ServiceStatus") or {}).get("RunningTasks")),
                "completed_tasks": number((s.get("ServiceStatus") or {}).get("CompletedTasks")),
            }
            for s in item.get("services") or []
        ]
        nodes = [
            {
                "id": n.get("ID"),
                "name": (n.get("Description") or {}).get("Hostname") or n.get("ID"),
                "hostname": (n.get("Description") or {}).get("Hostname"),
                "status": (n.get("Status") or {}).get("State"),
                "role": (n.get("Spec") or {}).get("Role"),
                "availability": (n.get("Spec") or {}).get("Availability"),
                "resources": (n.get("Description") or {}).get("Resources"),
            }
            for n in item.get("nodes") or []
        ]
        out = {
            "id": eid,
            "name": endpoint.get("Name"),
            "type": endpoint.get("Type"),
            "portainer_status": endpoint.get("Status"),
            "status": "degraded" if errors or stat_errors else "live",
            "updated_at": sampled_at,
            "errors": errors,
            "inventory_updated_at": item.get("inventory_updated_at"),
            "storage_updated_at": item.get("storage_updated_at"),
            "host": {
                "name": info.get("Name"),
                "os": info.get("OperatingSystem"),
                "architecture": info.get("Architecture"),
                "kernel": info.get("KernelVersion"),
                "cpus": cpus,
                "memory_total": hostmem,
                "docker_version": info.get("ServerVersion"),
                "api_version": item.get("api_version"),
                "storage_driver": info.get("Driver"),
                "docker_root": info.get("DockerRootDir"),
                "cgroup_version": info.get("CgroupVersion"),
                "logging_driver": info.get("LoggingDriver"),
                "swarm": (info.get("Swarm") or {}).get("LocalNodeState"),
                "warnings": info.get("Warnings") or [],
                "memory_accounting": info.get("MemoryLimit"),
                "multi_node": multi_node,
                "swarm_manager": bool((info.get("Swarm") or {}).get("ControlAvailable")),
                "host_memory_used": None,
                "host_disk_used": None,
            },
            "metrics": metrics,
            "history": list(item["history"]),
            "containers": containers,
            "stacks": sorted(stackmap.values(), key=lambda s: s["name"]),
            "images": images,
            "volumes": volumes,
            "networks": networks,
            "storage": storage_summary(item.get("df")),
            "build_cache": [
                {
                    "id": c.get("ID"),
                    "type": c.get("Type"),
                    "size": number(c.get("Size")),
                    "in_use": c.get("InUse"),
                    "shared": c.get("Shared"),
                    "created": c.get("CreatedAt"),
                    "last_used": c.get("LastUsedAt"),
                    "usage_count": c.get("UsageCount"),
                }
                for c in df.get("BuildCache") or []
            ],
            "services": services,
            "nodes": nodes,
        }
        agent_storage = item.get("agent_storage") or {}
        capacity, available = (
            number(agent_storage.get("totalBytes")),
            number(agent_storage.get("availableBytes")),
        )
        out["agent_storage"] = {
            "docker_fs_total_bytes": capacity,
            "docker_fs_available_bytes": available,
            "docker_fs_unavailable_bytes": capacity - available
            if capacity is not None and available is not None and available <= capacity
            else None,
            "docker_artifact_bytes": number(agent_storage.get("dockerBytes")),
        }
        out["agent_capabilities"] = item.get("agent_capabilities") or {
            "host": "not an Agent environment",
            "storage": "not an Agent environment",
        }
        out["physical_disks"] = [
            {"name": f"disk-{i + 1}", "vendor": d.get("Vendor"), "size": number(d.get("Size"))}
            for i, d in enumerate((item.get("agent_host") or {}).get("PhysicalDisks") or [])
        ]
        out["pci_devices"] = [
            {"vendor": d.get("Vendor"), "name": d.get("Name")}
            for d in (item.get("agent_host") or {}).get("PCIDevices") or []
        ]
        item["output"] = out
        return out

    def close(self):
        self.stop.set()
        # Cancel queued work immediately; active requests still have bounded timeouts.
        self.pool.shutdown(wait=False, cancel_futures=True)
        self.thread.join()
        self.pool.shutdown(wait=True, cancel_futures=True)


def safe_inspect(raw):
    """Operational fields only. Never expose environment values or command-line secrets."""
    host = raw.get("HostConfig") or {}
    cfg = raw.get("Config") or {}
    state = raw.get("State") or {}
    clean_state = {
        k: state.get(k)
        for k in (
            "Status",
            "Running",
            "Paused",
            "Restarting",
            "OOMKilled",
            "Dead",
            "Pid",
            "ExitCode",
            "StartedAt",
            "FinishedAt",
        )
    }
    if state.get("Health"):
        clean_state["Health"] = {k: state["Health"].get(k) for k in ("Status", "FailingStreak")}
    return redact(
        {
            "Id": raw.get("Id"),
            "Name": raw.get("Name"),
            "Created": raw.get("Created"),
            "Image": raw.get("Image"),
            "State": clean_state,
            "RestartCount": raw.get("RestartCount"),
            "Platform": raw.get("Platform"),
            "Mounts": raw.get("Mounts"),
            "NetworkSettings": {
                "Ports": (raw.get("NetworkSettings") or {}).get("Ports"),
                "Networks": (raw.get("NetworkSettings") or {}).get("Networks"),
            },
            "Config": {
                "Image": cfg.get("Image"),
                "Hostname": cfg.get("Hostname"),
                "User": cfg.get("User"),
                "WorkingDir": cfg.get("WorkingDir"),
                "ExposedPorts": cfg.get("ExposedPorts"),
                "Env": cfg.get("Env"),
                "Labels": cfg.get("Labels"),
            },
            "HostConfig": {
                k: host.get(k)
                for k in (
                    "Memory",
                    "MemorySwap",
                    "MemoryReservation",
                    "NanoCpus",
                    "CpuQuota",
                    "CpuPeriod",
                    "CpusetCpus",
                    "PidsLimit",
                    "RestartPolicy",
                    "NetworkMode",
                    "ReadonlyRootfs",
                    "Privileged",
                    "CapAdd",
                    "CapDrop",
                    "SecurityOpt",
                    "LogConfig",
                )
            },
        }
    )


class Handler(BaseHTTPRequestHandler):
    server_version = "EdgeConsole"

    def log_message(self, fmt, *args):
        if len(args) > 1 and str(args[1]) not in ("200", "304"):
            LOG.info("HTTP %s", args[1])

    def send(self, payload, status=200, mime="application/json; charset=utf-8"):
        data = (
            json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
            if "json" in mime
            else payload
        )
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store" if "json" in mime else "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
        )
        self.end_headers()
        try:
            self.wfile.write(data)
        except BrokenPipeError, ConnectionResetError, ConnectionAbortedError:
            pass
