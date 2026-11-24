"""Bounded display series from persisted, explicitly scoped service samples."""
from collections import defaultdict

from django.db.models import F, Window
from django.db.models.functions import RowNumber
from django.utils import timezone

from pipeline.resources import SERVICES, service_state
from records.models import Metric

STATE_LABELS = {
    "missing": "Нет замеров",
    "stale": "Замеры устарели",
    "ready": "Доступен",
    "running": "Поступают замеры",
    "degraded": "Проверка доступности не прошла",
    "completed": "Завершено",
}


def latest_resource_samples():
    return Metric.objects.filter(service__in=SERVICES, values__has_key="sample_at").order_by(
        "service", "-created_at", "-pk",
    ).distinct("service")


def service_series(now=None):
    now = now or timezone.now()
    samples = Metric.objects.filter(service__in=SERVICES, values__has_key="sample_at").annotate(
        row_number=Window(RowNumber(), partition_by=[F("service")], order_by=[F("created_at").desc(), F("pk").desc()]),
    ).filter(row_number__lte=20).order_by("-created_at", "-pk")
    return resource_history(samples, now=now, expected=SERVICES)


def resource_history(samples, *, now=None, expected=()):
    groups = defaultdict(list)
    latest = {}
    for sample in samples:
        values = sample.values
        total = values.get("ram_total") or 0
        used = values.get("ram_used")
        latest.setdefault(sample.service, sample)
        groups[sample.service].append({
            "created_at": sample.created_at,
            "cpu": values.get("cpu_percent"), "cpu_cores": values.get("cpu_cores"),
            "ram_percent": round(used / total * 100, 1) if total and used is not None else None,
            "ram_used": used, "ram_total": total or None,
            "disk_free": values.get("disk_free"), "disk_total": values.get("disk_total"),
            "swap_used": values.get("swap_used"), "gpu": values.get("gpu"),
            "pids_used": values.get("pids_used"), "pids_limit": values.get("pids_limit"),
            "scope": values.get("scope", "unknown"),
        })
    result = []
    for service in sorted(set(groups) | set(expected)):
        rows = groups[service][:20]
        state = service_state(latest.get(service), now) if now else "running"
        result.append({"service": service, "state": state, "label": STATE_LABELS[state],
                       "latest": rows[0] if rows else None, "rows": rows, "series": list(reversed(rows))})
    return result
