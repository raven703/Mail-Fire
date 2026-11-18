"""Read-only diagnostics; no Docker socket or arbitrary SQL execution."""

from fastapi import APIRouter, Depends
from sqlalchemy import select, text

from app.api import admin, db, serialize, user
from app.models import Job, Metric

router = APIRouter(prefix="/api/monitoring", tags=["Monitoring"])


@router.get("/jobs")
def job_details(account=Depends(admin), session=Depends(db)):
    rows = session.scalars(select(Job).order_by(Job.created_at.desc()).limit(100))
    return {
        "items": [
            {
                k: getattr(r, k)
                for k in ("id", "kind", "status", "attempts", "error", "created_at", "finished_at")
            }
            | {
                "progress": r.payload.get("progress"),
                "completed": r.payload.get("completed"),
                "total": len(r.payload.get("items", [])),
            }
            for r in rows
        ]
    }


@router.get("/alerts")
def alerts(account=Depends(admin), session=Depends(db)):
    rows = session.execute(
        text("""SELECT kind, count(*) AS count FROM jobs
        WHERE status='DEAD' OR (status='RUNNING' AND lease_until < now()) GROUP BY kind""")
    )
    return {"items": [dict(r._mapping) for r in rows], "scope": "dead jobs and expired leases"}


@router.get("/queues")
def queues(account=Depends(user), session=Depends(db)):
    rows = session.execute(
        text("""SELECT kind, status, count(*) AS count,
      max(attempts) AS max_attempts,
      extract(epoch from (now()-min(created_at))) AS oldest_age_seconds,
      avg(extract(epoch from(finished_at-created_at))) FILTER (WHERE finished_at IS NOT NULL) AS average_total_seconds,
      percentile_cont(0.95) WITHIN GROUP (ORDER BY extract(epoch from(finished_at-created_at))) FILTER (WHERE finished_at IS NOT NULL) AS p95_total_seconds,
      count(*) FILTER (WHERE status='RUNNING' AND lease_until < now()) AS expired_leases
      FROM jobs GROUP BY kind,status ORDER BY kind,status""")
    )
    return {"items": [dict(r._mapping) for r in rows]}


@router.get("/flow")
def flow(account=Depends(user), session=Depends(db)):
    rows = session.execute(
        text("""SELECT date_trunc('hour',e.created_at) AS hour,e.source,e.direction,
      count(*) AS events, count(DISTINCT e.message_id) AS unique_messages,
      avg(b.size) AS average_bytes, percentile_cont(.5) WITHIN GROUP(ORDER BY b.size) AS median_bytes,
      percentile_cont(.95) WITHIN GROUP(ORDER BY b.size) AS p95_bytes
      FROM mail_events e JOIN messages m ON m.id=e.message_id JOIN blobs b ON b.sha=m.original_sha
      WHERE e.created_at > now()-interval '7 days' GROUP BY 1,2,3 ORDER BY 1 DESC""")
    )
    return {"items": [dict(r._mapping) for r in rows]}


@router.get("/database")
def database(account=Depends(admin), session=Depends(db)):
    tables = session.execute(
        text("""SELECT relname,pg_total_relation_size(relid) AS total_bytes,
      pg_indexes_size(relid) AS index_bytes,n_live_tup,n_dead_tup,last_autovacuum,last_autoanalyze
      FROM pg_stat_user_tables ORDER BY pg_total_relation_size(relid) DESC""")
    )
    activity = session.execute(
        text("""SELECT pid,state,wait_event_type,wait_event,
      extract(epoch from(now()-query_start)) AS duration_seconds
      FROM pg_stat_activity WHERE datname=current_database()""")
    )
    return {
        "tables": [dict(r._mapping) for r in tables],
        "connections": [dict(r._mapping) for r in activity],
        "database_bytes": session.scalar(text("SELECT pg_database_size(current_database())")),
        "locks_waiting": session.scalar(text("SELECT count(*) FROM pg_locks WHERE NOT granted")),
    }


@router.get("/resources")
def resources(account=Depends(user), session=Depends(db)):
    rows = session.scalars(select(Metric).order_by(Metric.created_at.desc()).limit(500))
    return {
        "scope": "maintenance container / host-visible psutil; not per-container cgroup accounting",
        "items": [serialize(r) for r in rows],
    }
