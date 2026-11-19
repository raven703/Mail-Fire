import os
import socket
import threading
import time
import uuid
from datetime import UTC, timedelta

from sqlalchemy import and_, or_, select, text, update

from app.config import settings
from app.db import transaction
from app.models import Diagnostic, Job, Message, now
from app.processing import analyze, evaluate


def claim(owner):
    with transaction() as session:
        # Serialize claims only, not processing; at most one live training lease.
        session.execute(text("SELECT pg_advisory_xact_lock(hashtext('job-claim'))"))
        training_busy = session.scalar(
            select(Job.id)
            .where(Job.kind == "ml_train", Job.status == "RUNNING", Job.lease_until > now())
            .limit(1)
        )
        job = session.scalar(
            select(Job)
            .where(
                Job.kind != "ml_train" if training_busy else True,
                (
                    (Job.kind == "ml_train")
                    & (__import__("sqlalchemy").func.coalesce(Job.payload["engine"].astext.in_(["setfit", "rubert"]), False))
                ) if os.getenv("ML_NEURAL_ONLY", "false").lower() == "true"
                else ~(
                    (Job.kind == "ml_train")
                    & (__import__("sqlalchemy").func.coalesce(Job.payload["engine"].astext.in_(["setfit", "rubert"]), False))
                ),
                or_(
                    and_(Job.status == "PENDING", Job.available_at <= now()),
                    and_(Job.status == "RUNNING", Job.lease_until < now()),
                ),
            )
            .order_by(Job.priority, Job.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not job:
            return None
        if job.attempts >= 5:
            job.status = "DEAD"
            return None
        job.status, job.owner = "RUNNING", owner
        job.attempts += 1
        job.lease_until = now() + timedelta(seconds=settings().job_lease_seconds)
        return job.id, job.kind, job.payload


def heartbeat(job_id, owner):
    """Only the current owner can extend a live lease; never resurrect an old one."""
    with transaction() as session:
        result = session.execute(
            update(Job)
            .where(Job.id == job_id, Job.owner == owner, Job.status == "RUNNING", Job.lease_until > now())
            .values(lease_until=now() + timedelta(seconds=settings().job_lease_seconds))
        )
        return result.rowcount == 1


def renew_loop(job_id, owner, stop):
    while not stop.wait(settings().job_heartbeat_seconds):
        try:
            if not heartbeat(job_id, owner):
                return
        except Exception:
            # A DB outage must not terminate the worker; completion is fenced below.
            continue


def complete(job_id, owner):
    with transaction() as session:
        result = session.execute(
            update(Job)
            .where(Job.id == job_id, Job.owner == owner, Job.status == "RUNNING", Job.lease_until > now())
            .values(status="DONE", finished_at=now(), lease_until=None)
        )
        return result.rowcount == 1


def main():
    owner = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex}"
    while True:
        try:
            item = claim(owner)
            if not item:
                time.sleep(2)
                continue
            job_id, kind, payload = item
            stop = threading.Event()
            renewer = threading.Thread(target=renew_loop, args=(job_id, owner, stop), daemon=True)
            renewer.start()
            try:
                if kind == "analyze":
                    analyze(payload["message_id"], job_id, owner)
                elif kind == "evaluate":
                    evaluate(payload["event_id"], job_id, owner)
                elif kind == "ml_train":
                    from app.background import train_job

                    train_job(job_id, owner, payload)
                elif kind == "semantic_reindex":
                    from app.background import reindex_job

                    reindex_job(job_id, owner, payload)
                else:
                    raise ValueError("Unknown job type")
                complete(job_id, owner)
            except Exception as exc:
                with transaction() as session:
                    job = session.get(Job, job_id, with_for_update=True)
                    if (
                        job.owner != owner
                        or job.status != "RUNNING"
                        or not job.lease_until
                        or job.lease_until.replace(tzinfo=UTC) <= now()
                    ):
                        continue
                    job.error = type(exc).__name__
                    job.status = "DEAD" if job.attempts >= 5 else "PENDING"
                    job.available_at = now() + timedelta(seconds=min(300, 2**job.attempts))
                    session.add(
                        Diagnostic(
                            service="worker",
                            level="ERROR",
                            event="job_failed",
                            details={"job_id": job.id, "exception": type(exc).__name__},
                        )
                    )
                    if kind == "analyze":
                        message = session.get(Message, payload["message_id"])
                        message.status, message.error = "FAILED", type(exc).__name__
            finally:
                stop.set()
                renewer.join(timeout=5)
        except Exception:
            time.sleep(5)


if __name__ == "__main__":
    main()
