"""Period-aware security overview and incident analytics."""

import csv
from datetime import UTC, timedelta

from django.db import connection
from django.db.models import Count, Q
from django.db.models.functions import TruncDay, TruncHour
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from pipeline.models import WorkItem
from pipeline.resource_history import latest_resource_samples
from pipeline.resources import service_state
from records.models import Incident, Message, Outbox
from records.ui_filters import DATE_PARAMETERS, period_bounds, resolve_period
from records.workspace import HIGH_RISK, MEDIUM_RISK, OPEN_STATUSES, access, policy_label, severity


def risk_bands():
    return {
        "high": Q(risk__gte=HIGH_RISK),
        "medium": Q(risk__gte=MEDIUM_RISK, risk__lt=HIGH_RISK),
        "low": Q(risk__lt=MEDIUM_RISK),
    }


def incident_timeline(incidents, hourly):
    bucket = TruncHour if hourly else TruncDay
    series = list(incidents.annotate(bucket=bucket("created_at")).values("bucket").annotate(
        **{key: Count("pk", filter=criteria) for key, criteria in risk_bands().items()},
    ).order_by("bucket"))
    for row in series:
        row["total"] = row["high"] + row["medium"] + row["low"]
        row["segments"] = [{"level": level, "count": row[level]} for level in ("low", "medium", "high")]
    return series


def policy_counts(start, end):
    with connection.cursor() as cursor:
        cursor.execute("""SELECT hit->>'name', count(*)
                       FROM incidents i CROSS JOIN LATERAL jsonb_array_elements(
                           CASE jsonb_typeof(i.policy_hits) WHEN 'array' THEN i.policy_hits ELSE '[]'::jsonb END
                       ) AS hit
                       WHERE i.created_at >= %s AND i.created_at < %s AND hit->>'name' IS NOT NULL
                       GROUP BY hit->>'name' ORDER BY count(*) DESC, hit->>'name'""", [start, end])
        return [{"name": name, "count": count} for name, count in cursor.fetchall()]


def status_cards(queues, now):
    rows = {row.service: service_state(row, now) for row in latest_resource_samples()}

    def recent_state(*names):
        states = {rows.get(name, "missing") for name in names}
        if "degraded" in states:
            return "ERROR"
        return "OK" if states & {"ready", "running"} else "UNKNOWN"

    return [
        {"name": "PostgreSQL", "state": "OK", "tab": "database"},
        {"name": "Очереди", "state": "ERROR" if queues.get("DEAD") else recent_state("rabbitmq"), "tab": "queues"},
        {"name": "BCC / импорт", "state": recent_state("smtp", "directory-import"), "tab": "flow"},
        {"name": "OCR", "state": recent_state("ocr-parser"), "tab": "resources"},
        {"name": "SIEM", "state": "ERROR" if WorkItem.objects.filter(kind="notifications.deliver", status=WorkItem.Status.DEAD).exists() else
         "OK" if Outbox.objects.filter(status="SENT", available_at__gte=now - timedelta(days=1)).exists() else "UNKNOWN",
         "tab": "queues"},
    ]


def export_timeline(timeline):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="mailfire-incidents.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(["Время", "HIGH", "MEDIUM", "LOW"])
    for row in timeline:
        stamp = row["bucket"]
        if timezone.is_naive(stamp):
            stamp = stamp.replace(tzinfo=UTC)
        writer.writerow([stamp.isoformat(), row["high"], row["medium"], row["low"]])
    return response


@require_GET
def overview(request, analytics=False):
    forbidden = access(request)
    if forbidden is not None:
        return forbidden
    now = timezone.now()
    dates = resolve_period(request)
    start, end = period_bounds(dates, now)
    incidents = Incident.objects.filter(created_at__gte=start, created_at__lt=end)
    hourly = end - start <= timedelta(days=2)
    timeline = incident_timeline(incidents, hourly)
    if request.GET.get("export") == "timeline":
        return export_timeline(timeline)
    series = timeline if analytics else timeline[-18:]
    levels = [{"label": label, "key": key, "count": sum(row[key] for row in timeline)}
              for key, label in (("high", "Высокая"), ("medium", "Средняя"), ("low", "Низкая"))]
    queues = dict(WorkItem.objects.values("status").annotate(total=Count("pk")).values_list("status", "total"))
    recent = list(incidents.select_related("message", "policy").defer(
        "message__headers", "message__recipients", "message__error",
    ).order_by("-risk", "-created_at", "-pk")[:8 if analytics else 6])
    for row in recent:
        row.severity = severity(row.risk)
        row.policy_label = policy_label(row)
    policies = policy_counts(start, end)
    total = sum(row["total"] for row in timeline)
    response = render(request, "records/overview.html", {
        "analytics": analytics, "date_query": dates.urlencode(),
        "timeline": series, "timeline_max": max((row["total"] for row in series), default=1),
        "hourly": hourly, "risk_bands": levels, "analytics_total": total, "risk_max": max(total, 1),
        "analytics_review": incidents.filter(status__in=OPEN_STATUSES).count(),
        "analytics_analyzed": Message.objects.filter(
            created_at__gte=start, created_at__lt=end, status="ANALYZED",
        ).count(),
        "analytics_jobs": queues.get("PENDING", 0) + queues.get("RUNNING", 0),
        "analytics_services": status_cards(queues, now), "dead_jobs": queues.get("DEAD", 0),
        "policies": policies if analytics else policies[:6], "policy_max": policies[0]["count"] if policies else 1,
        "priority_incidents": recent,
    })
    if request.headers.get("X-MICE-Period-Poll"):
        response["X-MICE-Period-Poll"] = "true"
    return response
