import os
import socket
import time
import uuid
from datetime import timedelta

from sqlalchemy import and_, or_, select

from app.db import transaction
from app.models import Diagnostic, Job, Message, now
from app.processing import analyze, evaluate


def claim(owner):
    with transaction() as session:
        job = session.scalar(
            select(Job)
            .where(
                or_(
                    and_(Job.status == "PENDING", Job.available_at <= now()),
                    and_(Job.status == "RUNNING", Job.lease_until < now()),
                )
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
        job.lease_until = now() + timedelta(seconds=180)
        return job.id, job.kind, job.payload


def main():
    # Processing time must remain below lease. External parsers need a separate
    # sandbox before production use; see security limitations.
    owner = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex}"
    while True:
        try:
            item = claim(owner)
            if not item:
                time.sleep(2)
                continue
            job_id, kind, payload = item
            try:
                if kind == "analyze":
                    analyze(payload["message_id"])
                elif kind == "evaluate":
                    evaluate(payload["event_id"])
                else:
                    raise ValueError("Unknown job type")
                with transaction() as session:
                    job = session.get(Job, job_id, with_for_update=True)
                    if job.owner == owner:
                        job.status, job.finished_at = "DONE", now()
            except Exception as exc:
                with transaction() as session:
                    job = session.get(Job, job_id, with_for_update=True)
                    if job.owner != owner:
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
        except Exception:
            time.sleep(5)


if __name__ == "__main__":
    main()
