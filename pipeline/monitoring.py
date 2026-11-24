from datetime import timedelta
from urllib.parse import quote

import httpx
from django.conf import settings
from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Min
from django.utils import timezone

from mice.celery import app
from pipeline.config import GROUPS
from pipeline.models import Attempt, Dispatch, WorkItem


def snapshot():
    now = timezone.now()
    counts = {
        (row["queue"], row["status"]): row["total"]
        for row in WorkItem.objects.values("queue", "status").annotate(total=Count("id"))
    }
    oldest = {
        row["queue"]: row["oldest"]
        for row in WorkItem.objects.filter(status="PENDING")
        .values("queue")
        .annotate(oldest=Min("created_at"))
    }
    completed = {
        row["queue"]: row["total"]
        for row in WorkItem.objects.filter(status="DONE", finished_at__gte=now - timedelta(hours=1))
        .values("queue")
        .annotate(total=Count("id"))
    }
    duration = ExpressionWrapper(F("finished_at") - F("started_at"), output_field=DurationField())
    durations = {
        row["job__queue"]: row["average"].total_seconds()
        for row in Attempt.objects.filter(finished_at__gte=now - timedelta(hours=1), error="")
        .values("job__queue")
        .annotate(average=Avg(duration))
        if row["average"] is not None
    }
    broker, workers = {"available": False, "queues": {}}, {"available": False, "items": {}}
    if settings.MICE_RABBIT_API_URL:
        try:
            with httpx.Client(timeout=2, trust_env=False, follow_redirects=False) as client:
                response = client.get(
                    settings.MICE_RABBIT_API_URL.rstrip("/")
                    + "/api/queues/"
                    + quote(settings.MICE_RABBIT_VHOST, safe=""),
                    auth=(settings.MICE_RABBIT_USER, settings.MICE_RABBIT_PASSWORD),
                )
                response.raise_for_status()
                broker = {
                    "available": True,
                    "queues": {
                        row["name"]: {
                            "ready": row.get("messages_ready", 0),
                            "unacknowledged": row.get("messages_unacknowledged", 0),
                            "consumers": row.get("consumers", 0),
                            "state": row.get("state", "unknown"),
                        }
                        for row in response.json()
                    },
                }
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            broker["error"] = "RabbitMQ management unavailable"
    else:
        broker["error"] = "RabbitMQ management not configured"
    try:
        replies = app.control.inspect(timeout=1).ping() or {}
        workers = {"available": bool(replies), "items": replies}
    except Exception:
        workers["error"] = "Celery workers unavailable"
    rows = []
    for group in GROUPS:
        rows.append(
            {
                "name": group,
                "pending": counts.get((group, "PENDING"), 0),
                "running": counts.get((group, "RUNNING"), 0),
                "dead": counts.get((group, "DEAD"), 0),
                "oldest_seconds": round((now - oldest[group]).total_seconds()) if group in oldest else None,
                "completed_hour": completed.get(group, 0),
                "average_seconds": durations.get(group),
                "broker": broker["queues"].get(group),
            }
        )
    return {
        "queues": rows,
        "broker": broker,
        "workers": workers,
        "unpublished": Dispatch.objects.filter(published_at__isnull=True).count(),
        "publish_errors": Dispatch.objects.filter(published_at__isnull=True).exclude(error="").count(),
        "generated_at": now.isoformat(),
    }
