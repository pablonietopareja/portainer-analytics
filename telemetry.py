"""Optional Docker stats telemetry, with missing data preserved as unknown.

Raw numeric metrics intentionally retain their Engine field names and units.
No string-valued stats, configuration, labels, environment, or logs are copied.
"""

from __future__ import annotations

import math


def _metric(label, unit, help):
    return {"label": label, "unit": unit, "help": help}


EXTRA_METRICS = {
    "memory_raw_bytes": _metric(
        "Memory including cache",
        "bytes",
        "Linux cgroup usage before subtracting inactive file cache.",
    ),
    "memory_limit_bytes": _metric(
        "Reported memory limit",
        "bytes",
        "Docker reports host memory when no lower container limit is configured. Not additive host capacity.",
    ),
    "memory_limit_percent": _metric(
        "Memory / reported limit",
        "percent",
        "Working set divided by the reported Docker memory limit.",
    ),
    "memory_peak_bytes": _metric(
        "Peak memory usage", "bytes", "Reported maximum usage; often unavailable with cgroup v2."
    ),
    "memory_failures": _metric(
        "Memory limit / OOM events",
        "count",
        "Docker failcnt: limit hits on cgroup v1; OOM events on cgroup v2. Not a count of killed processes.",
    ),
    "memory_rss_bytes": _metric(
        "Resident anonymous memory",
        "bytes",
        "cgroup v1 total_rss/rss or cgroup v2 anon; these accounting definitions differ slightly.",
    ),
    "memory_file_bytes": _metric(
        "File memory cache",
        "bytes",
        "cgroup v1 total_cache/cache or cgroup v2 file; includes active and inactive file pages.",
    ),
    "memory_mapped_bytes": _metric(
        "Mapped file memory", "bytes", "Memory mapped files, when reported by the runtime."
    ),
    "memory_dirty_bytes": _metric(
        "Dirty file memory", "bytes", "File pages modified but not yet written to backing storage."
    ),
    "memory_writeback_bytes": _metric(
        "Memory in writeback", "bytes", "File pages currently being written to backing storage."
    ),
    "memory_swap_bytes": _metric(
        "Swap usage",
        "bytes",
        "Only available when Docker explicitly includes a swap counter; no estimate from limits.",
    ),
    "memory_page_faults": _metric(
        "Page faults", "count", "Cumulative minor and major page faults reported by the cgroup."
    ),
    "memory_major_faults": _metric(
        "Major page faults", "count", "Cumulative major page faults requiring storage access."
    ),
    "memory_page_fault_rate": _metric(
        "Page faults / second",
        "count_rate",
        "Counter increase per second; unavailable on first sample or counter reset.",
    ),
    "memory_major_fault_rate": _metric(
        "Major faults / second", "count_rate", "Major page fault counter increase per second."
    ),
    "memory_commit_bytes": _metric(
        "Windows committed memory",
        "bytes",
        "Windows committed bytes; distinct from private working set.",
    ),
    "memory_commit_peak_bytes": _metric(
        "Windows peak committed memory", "bytes", "Windows peak committed bytes."
    ),
    "pids_limit": _metric(
        "Process / thread limit",
        "count",
        "Linux cgroup hard PID limit. An unlimited or absent limit is unavailable.",
    ),
    "pids_limit_percent": _metric(
        "Processes / thread limit", "percent", "Current Linux PIDs divided by a finite hard limit."
    ),
    "cpu_time_seconds": _metric(
        "CPU time",
        "seconds",
        "Cumulative CPU execution time, normalized to seconds on Linux and Windows.",
    ),
    "cpu_user_seconds": _metric(
        "CPU user time",
        "seconds",
        "Cumulative user-mode CPU time. Hyper-V may not provide this counter.",
    ),
    "cpu_kernel_seconds": _metric(
        "CPU kernel time",
        "seconds",
        "Cumulative kernel-mode CPU time. Hyper-V may not provide this counter.",
    ),
    "cpu_user_percent": _metric(
        "CPU user usage",
        "percent",
        "User CPU time per wall-clock second; 100% equals one logical CPU.",
    ),
    "cpu_kernel_percent": _metric(
        "CPU kernel usage",
        "percent",
        "Kernel CPU time per wall-clock second; 100% equals one logical CPU.",
    ),
    "cpu_periods": _metric(
        "CPU quota periods", "count", "Cumulative Linux CPU quota enforcement periods."
    ),
    "cpu_throttled_periods": _metric(
        "CPU throttled periods",
        "count",
        "Cumulative periods in which the container exhausted its CPU quota.",
    ),
    "cpu_throttled_seconds": _metric(
        "CPU throttled time",
        "seconds",
        "Cumulative Linux throttled time; can span multiple runnable threads.",
    ),
    "cpu_throttled_percent": _metric(
        "CPU periods throttled",
        "percent",
        "Throttled quota periods / total quota periods in the sample interval. Not host utilization.",
    ),
    "cpu_throttled_rate": _metric(
        "CPU throttled periods / second",
        "count_rate",
        "Increase in throttled period counter per second.",
    ),
    "cpu_throttled_time_rate": _metric(
        "CPU throttled seconds / second",
        "count_rate",
        "Throttled time accumulated per wall-clock second; can exceed one across threads.",
    ),
    "rx_bytes": _metric(
        "Network received total",
        "bytes",
        "Cumulative bytes received across container interfaces; may include internal or shared namespace traffic.",
    ),
    "tx_bytes": _metric(
        "Network transmitted total",
        "bytes",
        "Cumulative bytes sent across container interfaces; may include internal or shared namespace traffic.",
    ),
    "block_read_bytes": _metric(
        "Block storage read total",
        "bytes",
        "Cumulative bytes read from block devices, not disk capacity or writable-layer size.",
    ),
    "block_write_bytes": _metric(
        "Block storage written total",
        "bytes",
        "Cumulative bytes written to block devices, not disk capacity or writable-layer size.",
    ),
    "block_read_rate": _metric(
        "Block storage read", "rate", "Block read counter increase per second."
    ),
    "block_write_rate": _metric(
        "Block storage write", "rate", "Block write counter increase per second."
    ),
    "block_read_ops": _metric(
        "Block read operations",
        "count",
        "Cumulative read operations. Usually unavailable on cgroup v2 through Docker.",
    ),
    "block_write_ops": _metric(
        "Block write operations",
        "count",
        "Cumulative write operations. Usually unavailable on cgroup v2 through Docker.",
    ),
    "block_read_ops_rate": _metric(
        "Block read operations / second",
        "count_rate",
        "Read operations per second; requires a supplied operations counter.",
    ),
    "block_write_ops_rate": _metric(
        "Block write operations / second",
        "count_rate",
        "Write operations per second; requires a supplied operations counter.",
    ),
}
for _direction, _name in (("rx", "Receive"), ("tx", "Transmit")):
    for _counter, _label in (
        ("packets", "packets"),
        ("errors", "errors"),
        ("dropped", "dropped packets"),
    ):
        EXTRA_METRICS[f"{_direction}_{_counter}"] = _metric(
            f"{_name} {_label}",
            "count",
            "Cumulative sum across container interfaces. Network error counters are unavailable on Windows.",
        )
        EXTRA_METRICS[f"{_direction}_{_counter}_rate"] = _metric(
            f"{_name} {_label} / second",
            "count_rate",
            "Counter increase per second across container interfaces.",
        )


def _finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError, ValueError:
        return False


def finite_number(value):
    return value if _finite(value) and value >= 0 else None


def _object(value):
    return value if isinstance(value, dict) else {}


def _first(source, *keys):
    for key in keys:
        value = finite_number(source.get(key))
        if value is not None:
            return value
    return None


def _sum(values):
    values = list(values)
    return sum(values) if values and all(value is not None for value in values) else None


def _op_total(rows, operation):
    if not isinstance(rows, list):
        return None
    return _sum(
        finite_number(row.get("value"))
        for row in rows
        if isinstance(row, dict) and str(row.get("op")).lower() == operation
    )


def _rate(current, previous, elapsed):
    current, previous = finite_number(current), finite_number(previous)
    if (
        current is None
        or previous is None
        or finite_number(elapsed) is None
        or elapsed <= 0
        or current < previous
    ):
        return None
    result = (current - previous) / elapsed
    return result if math.isfinite(result) else None


def flatten_numeric_stats(raw, limit=512):
    """Flatten recognized numeric telemetry only; bounded depth, leaves and nodes.

    Keys escape '~', '/' and '.' as ~0, ~1, ~2, respectively. Arrays use
    decimal index segments. Values retain native Engine units, without sums.
    """
    output = {}
    visited = 0

    def walk(value, path, depth):
        nonlocal visited
        visited += 1
        if len(output) >= limit or visited > 4096 or depth > 10 or len(path) > 384:
            return
        if _finite(value):
            output[path] = value
        elif isinstance(value, dict):
            for key, child in value.items():
                if not isinstance(key, str) or len(key) > 96:
                    continue
                segment = key.replace("~", "~0").replace("/", "~1").replace(".", "~2")
                walk(child, f"{path}.{segment}", depth + 1)
                if len(output) >= limit or visited > 4096:
                    break
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}.{index}", depth + 1)
                if len(output) >= limit or visited > 4096:
                    break

    for group in (
        "cpu_stats",
        "precpu_stats",
        "memory_stats",
        "pids_stats",
        "networks",
        "blkio_stats",
        "storage_stats",
        "num_procs",
    ):
        if group in raw:
            walk(raw[group], group, 0)
    return output


def extend_stats(raw, previous=None, elapsed=None, normalized_base=None):
    """Return additional fields and platform corrections for stats_metrics().

    previous is the previous complete normalized result. elapsed must be the
    positive Engine sample-time interval (caller may use monotonic fallback).
    Merge this mapping into normalized_base before retaining the next sample.
    """
    raw, previous, base = _object(raw), _object(previous), _object(normalized_base)
    memory = _object(raw.get("memory_stats"))
    ms = _object(memory.get("stats"))
    cpu = _object(raw.get("cpu_stats"))
    usage = _object(cpu.get("cpu_usage"))
    windows = raw.get("os_type") == "windows" or (
        not raw.get("os_type")
        and any(k in memory for k in ("privateworkingset", "commitbytes", "commitpeakbytes"))
    )
    scale = 1e7 if windows else 1e9
    out = {key: None for key in EXTRA_METRICS}
    out["raw_metrics"] = flatten_numeric_stats(raw)
    out.update(
        memory_raw_bytes=finite_number(memory.get("usage")),
        memory_limit_bytes=finite_number(memory.get("limit")),
        memory_peak_bytes=finite_number(memory.get("max_usage")),
        memory_failures=finite_number(memory.get("failcnt")),
        memory_rss_bytes=_first(ms, "total_rss", "rss", "anon"),
        memory_file_bytes=_first(ms, "total_cache", "cache", "file"),
        memory_mapped_bytes=_first(ms, "total_mapped_file", "mapped_file", "file_mapped"),
        memory_dirty_bytes=_first(ms, "total_dirty", "dirty", "file_dirty"),
        memory_writeback_bytes=_first(ms, "total_writeback", "writeback", "file_writeback"),
        memory_swap_bytes=_first(ms, "total_swap", "swap"),
        memory_page_faults=_first(ms, "total_pgfault", "pgfault"),
        memory_major_faults=_first(ms, "total_pgmajfault", "pgmajfault"),
        memory_commit_bytes=finite_number(memory.get("commitbytes")),
        memory_commit_peak_bytes=finite_number(memory.get("commitpeakbytes")),
    )
    if windows:
        out.update(
            memory_bytes=finite_number(memory.get("privateworkingset")),
            cache_bytes=None,
            memory_raw_bytes=None,
            memory_limit=None,
            memory_limit_bytes=None,
            pids=None,
        )
    working = out.get("memory_bytes", base.get("memory_bytes"))
    if finite_number(working) is not None and out["memory_limit_bytes"]:
        out["memory_limit_percent"] = working / out["memory_limit_bytes"] * 100
    pids = _object(raw.get("pids_stats"))
    pidlimit = finite_number(pids.get("limit")) if not windows else None
    out["pids_limit"] = pidlimit if pidlimit else None
    if out["pids_limit"] and finite_number(pids.get("current")) is not None:
        out["pids_limit_percent"] = pids["current"] / out["pids_limit"] * 100
    for source, target in (
        ("total_usage", "cpu_time_seconds"),
        ("usage_in_usermode", "cpu_user_seconds"),
        ("usage_in_kernelmode", "cpu_kernel_seconds"),
    ):
        number = finite_number(usage.get(source))
        out[target] = number / scale if number is not None else None
    if windows:
        # Keep this console's one-core=100% convention, unlike Windows CLI's
        # host-normalized percentage. Correct the old Linux-nanosecond fallback.
        out["cpu_percent"] = None
        cpu_rate = _rate(usage.get("total_usage"), previous.get("cpu_total"), elapsed)
        if cpu_rate is not None:
            out["cpu_percent"] = cpu_rate / scale * 100
    for mode in ("user", "kernel"):
        rate = _rate(out[f"cpu_{mode}_seconds"], previous.get(f"cpu_{mode}_seconds"), elapsed)
        out[f"cpu_{mode}_percent"] = rate * 100 if rate is not None else None
    if not windows:
        throttling = _object(cpu.get("throttling_data"))
        out["cpu_periods"] = finite_number(throttling.get("periods"))
        out["cpu_throttled_periods"] = finite_number(throttling.get("throttled_periods"))
        time = finite_number(throttling.get("throttled_time"))
        out["cpu_throttled_seconds"] = time / 1e9 if time is not None else None
        periods = _rate(out["cpu_periods"], previous.get("cpu_periods"), elapsed)
        throttled = _rate(
            out["cpu_throttled_periods"], previous.get("cpu_throttled_periods"), elapsed
        )
        if periods and throttled is not None and throttled <= periods:
            out["cpu_throttled_percent"] = throttled / periods * 100
        out["cpu_throttled_rate"] = throttled
        out["cpu_throttled_time_rate"] = _rate(
            out["cpu_throttled_seconds"], previous.get("cpu_throttled_seconds"), elapsed
        )
    interfaces = _object(raw.get("networks"))
    for direction in ("rx", "tx"):
        for counter in ("bytes", "packets", "errors", "dropped"):
            key = f"{direction}_{counter}"
            out[key] = _sum(finite_number(_object(v).get(key)) for v in interfaces.values())
            if windows and counter == "errors":
                out[key] = None
            ratekey = f"{direction}_rate" if counter == "bytes" else f"{key}_rate"
            out[ratekey] = _rate(out[key], previous.get(key), elapsed)
    io = _object(raw.get("blkio_stats"))
    storage = _object(raw.get("storage_stats"))
    for op in ("read", "write"):
        out[f"block_{op}_bytes"] = (
            finite_number(storage.get(f"{op}_size_bytes"))
            if windows
            else _op_total(io.get("io_service_bytes_recursive"), op)
        )
        out[f"block_{op}_ops"] = (
            finite_number(storage.get(f"{op}_count_normalized"))
            if windows
            else _op_total(io.get("io_serviced_recursive"), op)
        )
        for suffix, result in (("bytes", f"block_{op}_rate"), ("ops", f"block_{op}_ops_rate")):
            key = f"block_{op}_{suffix}"
            out[result] = _rate(out[key], previous.get(key), elapsed)
    for counter, result in (
        ("memory_page_faults", "memory_page_fault_rate"),
        ("memory_major_faults", "memory_major_fault_rate"),
    ):
        out[result] = _rate(out[counter], previous.get(counter), elapsed)
    return out
