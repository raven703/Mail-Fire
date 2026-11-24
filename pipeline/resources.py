"""Read bounded Compose probes and derive per-container resource usage."""

import csv
import io
import math
import os
import re
import stat
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from django.conf import settings
from django.utils import timezone

FILE_SERVICES = (
    "db", "rabbitmq", "migrate", "publisher", "smtp", "directory-import", "web", "frontend",
    "beat", "ingestion", "extraction", "ocr", "detection", "ml", "llm", "policy", "notifications",
    "training", "semantic", "neural-training", "neural",
)
REMOTE_SERVICES = (
    ("parser", "MICE_PARSER_URL"), ("ocr-parser", "MICE_OCR_PARSER_URL"), ("converter", "MICE_CONVERTER_URL"),
)
SERVICES = (*FILE_SERVICES, *(name for name, _ in REMOTE_SERVICES), "maintenance")
PROBE_LIMIT = 8192
FRESH_FOR = timedelta(seconds=90)
HISTORY_FOR = timedelta(days=7)
SAMPLE_ROOT = Path("/mice-metrics/samples")
PROBE_PATH = "/run/mice-resource-probe.sh"

COUNTERS = {
    "cpu_usec": "cpu_usec", "cpu_quota": "cpu_quota", "cpu_period": "cpu_period",
    "memory.current": "ram_used", "memory.max": "ram_total", "memory.swap.current": "swap_used",
    "disk_total": "disk_total", "disk_used": "disk_used", "disk_free": "disk_free",
    "pids.current": "pids_used", "pids.max": "pids_limit",
}


def gpu_values(output):
    items = []
    for row in csv.reader(io.StringIO(output)):
        if len(row) != 6:
            raise ValueError("Invalid GPU sample")
        index, name, utilization, used, total, temperature = (value.strip() for value in row)
        utilization, temperature = float(utilization), float(temperature)
        if not math.isfinite(utilization) or not math.isfinite(temperature):
            raise ValueError("Invalid GPU numeric value")
        items.append({"index": int(index), "name": name[:160], "utilization": utilization,
                      "used_mib": int(used), "total_mib": int(total), "temperature": temperature})
    return items


def decode_probe(payload, now):
    if len(payload) > PROBE_LIMIT:
        raise ValueError("Resource probe exceeds size limit")
    pairs = [line.split(" ", 1) for line in payload.decode().splitlines()]
    fields = dict(pair for pair in pairs if len(pair) == 2 and pair[0] != "gpu")
    instance = fields.get("instance", "")
    state = fields.get("state", "")
    if not re.fullmatch(r"[a-zA-Z0-9_.-]{1,100}", instance) or state not in {"ready", "running", "degraded", "completed"}:
        raise ValueError("Invalid resource probe identity")
    timestamp = int(fields.get("at", "0"))
    recorded = datetime.fromtimestamp(timestamp, UTC)
    if timezone.is_naive(now):
        recorded = recorded.replace(tzinfo=None)
    if recorded > now + timedelta(seconds=5) or (recorded < now - FRESH_FOR and state != "completed"):
        raise ValueError("Stale resource probe")
    values = {"scope": "service-cgroup", "instance": instance, "state": state,
              "sample_at": timestamp, "cpu_percent": None}
    for src, dst in COUNTERS.items():
        number = fields.get(src, "")
        values[dst] = int(number) if re.fullmatch(r"[0-9]{1,20}", number) else None
    quota, period = values["cpu_quota"], values["cpu_period"]
    values["cpu_cores"] = quota / period if quota and period else None
    try:
        gpus = gpu_values("\n".join(pair[1] for pair in pairs if len(pair) == 2 and pair[0] == "gpu"))
    except ValueError:
        gpus = []
    values["gpu"] = gpus[:16]
    return recorded, values


def cpu_usage(values, previous):
    if not previous or previous.get("instance") != values["instance"]:
        return None
    usage, old_usage = values["cpu_usec"], previous.get("cpu_usec")
    seconds = values["sample_at"] - previous["sample_at"]
    if usage is None or old_usage is None or usage < old_usage or not 0 < seconds <= FRESH_FOR.total_seconds():
        return None
    return round((usage - old_usage) / (seconds * 10_000 * (values["cpu_cores"] or 1)), 1)


def read_probe(name):
    with os.fdopen(os.open(SAMPLE_ROOT / name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as file:
        if not stat.S_ISREG(os.fstat(file.fileno()).st_mode):
            raise ValueError("Resource probe is not a regular file")
        return file.read(PROBE_LIMIT + 1)


def remote_probe(client, url):
    with client.stream("GET", url.rstrip("/") + "/resources") as response:
        response.raise_for_status()
        payload = bytearray()
        for chunk in response.iter_bytes(chunk_size=1024):
            payload.extend(chunk)
            if len(payload) > PROBE_LIMIT:
                raise ValueError("Resource probe exceeds size limit")
    return bytes(payload)


def collect_probes(now):
    rows = {}
    for name in FILE_SERVICES:
        try:
            rows[name] = decode_probe(read_probe(name), now)
        except (OSError, ValueError, OverflowError):
            continue
    with httpx.Client(timeout=3, trust_env=False, follow_redirects=False) as client:
        for name, setting in REMOTE_SERVICES:
            url = getattr(settings, setting)
            if url:
                try:
                    rows[name] = decode_probe(remote_probe(client, url), timezone.now())
                except (httpx.HTTPError, ValueError, OSError, OverflowError):
                    continue
    try:
        local = subprocess.run(["sh", PROBE_PATH, "print"], capture_output=True, timeout=3, check=True)
        rows["maintenance"] = decode_probe(local.stdout, timezone.now())
    except (OSError, ValueError, OverflowError, subprocess.SubprocessError):
        pass
    return rows


def service_state(row, now):
    if row is None:
        return "missing"
    if row.values.get("state") == "completed":
        return "completed"
    if now - row.created_at > FRESH_FOR:
        return "stale"
    return row.values.get("state", "running")
