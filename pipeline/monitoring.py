from datetime import timedelta
from urllib.parse import quote

import httpx
from django.conf import settings
from django.db import connection
from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Min
from django.utils import timezone

from mice.celery import app
from pipeline.config import GROUPS
from pipeline.models import Attempt, Dispatch, WorkItem
from records.models import Message


def database_snapshot():
    """Read-only PostgreSQL statistics; deliberately never exposes query text."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_database_size(current_database()), (SELECT count(*) FROM pg_locks WHERE NOT granted)")
        size, waiting = cursor.fetchone()
        cursor.execute("""SELECT relname, pg_total_relation_size(relid), pg_indexes_size(relid),
                       n_live_tup, n_dead_tup, last_autovacuum, last_autoanalyze
                       FROM pg_stat_user_tables ORDER BY pg_total_relation_size(relid) DESC""")
        tables = [dict(zip(("name", "bytes", "index_bytes", "live", "dead", "autovacuum", "autoanalyze"), row, strict=True)) for row in cursor.fetchall()]
        cursor.execute("""SELECT state, wait_event_type, wait_event, count(*)
                       FROM pg_stat_activity WHERE datname=current_database() GROUP BY 1,2,3""")
        connections = [dict(zip(("state", "wait_type", "wait_event", "count"), row, strict=True)) for row in cursor.fetchall()]
    return {"bytes": size, "locks_waiting": waiting, "tables": tables, "connections": connections}


def flow_snapshot():
    with connection.cursor() as cursor:
        cursor.execute("""SELECT date_trunc('hour', e.created_at), e.source, e.direction,
                       count(*), count(DISTINCT e.message_id), avg(b.size),
                       percentile_cont(.5) WITHIN GROUP (ORDER BY b.size),
                       percentile_cont(.95) WITHIN GROUP (ORDER BY b.size)
                       FROM mail_events e JOIN messages m ON m.id=e.message_id
                       JOIN blobs b ON b.sha=m.original_sha
                       WHERE e.created_at > now()-interval '7 days'
                       GROUP BY 1,2,3 ORDER BY 1 DESC LIMIT 1000""")
        return [dict(zip(("hour", "source", "direction", "events", "messages", "average", "median", "p95"), row, strict=True)) for row in cursor.fetchall()]


def service_snapshot():
    """Probe only fixed configured Parser endpoints, never request-supplied URLs."""
    rows = []
    with httpx.Client(timeout=1, trust_env=False, follow_redirects=False) as client:
        for name, url in (("Parser", settings.MICE_PARSER_URL), ("OCR Parser", settings.MICE_OCR_PARSER_URL)):
            state = "not configured"
            if url:
                try:
                    response = client.get(url.rstrip("/") + "/health")
                    state = "available" if response.status_code == 200 else "degraded"
                except httpx.HTTPError:
                    state = "unavailable"
            rows.append({"name": name, "state": state})
    return rows


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
        inspector = app.control.inspect(timeout=1)
        replies = inspector.ping() or {}
        stats = inspector.stats() or {}
        workers = {"available": bool(replies), "items": replies, "stats": {
            name: {"pid": row.get("pid"), "uptime": row.get("uptime"),
                   "rusage": row.get("rusage", {}), "pool": {
                       key: row.get("pool", {}).get(key) for key in ("max-concurrency", "processes")
                   }} for name, row in stats.items()
        }}
    except Exception:
        workers["error"] = "Celery workers unavailable"
    rows = []
    failures = {
        row["job__queue"]: row["count"]
        for row in Attempt.objects.filter(finished_at__gte=now - timedelta(hours=1)).exclude(error="")
        .values("job__queue").annotate(count=Count("id"))
    }
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
                "failed_attempts_hour": failures.get(group, 0),
                "broker": broker["queues"].get(group),
            }
        )
    return {
        "services": service_snapshot(),
        "messages": list(Message.objects.values("status").annotate(total=Count("pk")).order_by("status")),
        "queues": rows,
        "broker": broker,
        "workers": workers,
        "unpublished": Dispatch.objects.filter(published_at__isnull=True).count(),
        "publish_errors": Dispatch.objects.filter(published_at__isnull=True).exclude(error="").count(),
        "generated_at": now.isoformat(),
        "expired_leases": WorkItem.objects.filter(status="RUNNING", deadline__lt=now).count(),
        "delayed_retries": WorkItem.objects.filter(status="PENDING", available_at__gt=now).count(),
    }
