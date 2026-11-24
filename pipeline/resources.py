"""Bounded local resource probes without Docker socket or additional dependencies."""
import csv
import io
import subprocess
from pathlib import Path

import psutil


def gpu_snapshot():
    try:
        result = subprocess.run([
            "nvidia-smi", "--query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu",
            "--format=csv,noheader,nounits",
        ], capture_output=True, text=True, timeout=2, check=True)
        items = []
        for row in csv.reader(io.StringIO(result.stdout)):
            if len(row) != 6:
                raise ValueError("Invalid GPU sample")
            index, name, utilization, used, total, temperature = (value.strip() for value in row)
            items.append({"index": int(index), "name": name[:160], "utilization": float(utilization),
                          "used_mib": int(used), "total_mib": int(total), "temperature": float(temperature)})
        return {"available": bool(items), "items": items}
    except (OSError, subprocess.SubprocessError, ValueError):
        return {"available": False, "items": [], "reason": "GPU not exposed or probe unavailable"}


def cgroup_snapshot(root=Path("/sys/fs/cgroup")):
    values = {}
    for name in ("memory.current", "memory.max", "cpu.max", "cpu.stat", "pids.current", "pids.max"):
        try:
            values[name.replace(".", "_")] = (root / name).read_text()[:1000].strip()
        except OSError:
            values[name.replace(".", "_")] = None
    return values


def local_resources():
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    return {"cpu_percent": psutil.cpu_percent(interval=0.1), "ram_used": memory.used, "ram_total": memory.total,
            "disk_used": disk.used, "disk_total": disk.total, "disk_free": disk.free,
            "swap_used": psutil.swap_memory().used, "process_rss": psutil.Process().memory_info().rss,
            "scope": "current-service; system counters may be host-visible",
            "cgroup": cgroup_snapshot(), "gpu": gpu_snapshot()}