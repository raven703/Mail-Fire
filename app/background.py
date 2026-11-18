"""Durable heavy-operation handlers. Publication is fenced by the job lease."""

from datetime import UTC

from sqlalchemy import select

from app.db import transaction
from app.ml import train
from app.models import Content, Job, MLModel, Reference, TrainingExample, now


def live(job, owner):
    return bool(
        job
        and job.status == "RUNNING"
        and job.owner == owner
        and job.lease_until
        and job.lease_until.replace(tzinfo=UTC) > now()
    )


def reindex_job(job_id, owner, payload):
    """One transaction per document; checkpoint and index commit atomically."""
    from app.semantic import index_document

    while True:
        with transaction() as session:
            job = session.get(Job, job_id, with_for_update=True)
            if not live(job, owner):
                return
            items = job.payload["items"]
            position = job.payload.get("completed", 0)
            if position >= len(items):
                job.status, job.finished_at, job.lease_until = "DONE", now(), None
                job.payload = {**job.payload, "progress": 100}
                return
            kind, row_id = items[position]
            row = session.get(Reference if kind == "reference" else Content, row_id)
            if row:
                index_document(session, kind, row.id, row.text)
            job.payload = {
                **job.payload,
                "completed": position + 1,
                "progress": round(100 * (position + 1) / max(1, len(items))),
            }


def train_job(job_id, owner, payload):
    with transaction() as session:
        examples = list(
            session.scalars(select(TrainingExample).where(TrainingExample.approved.is_(True)).limit(10001))
        )
        if len(examples) > 10000:
            raise ValueError("Training corpus exceeds configured limit")
        rows = [{"text": r.text, "labels": r.labels} for r in examples]
    artifact, metrics, eligible = train(rows, payload["min_f1"])
    with transaction() as session:
        job = session.get(Job, job_id, with_for_update=True)
        if not live(job, owner):
            return
        model = MLModel(name=payload["name"], artifact=artifact, metrics=metrics, eligible=eligible)
        session.add(model)
        session.flush()
        job.payload = {**job.payload, "progress": 100, "model_id": model.id}
        job.status, job.finished_at, job.lease_until = "DONE", now(), None
