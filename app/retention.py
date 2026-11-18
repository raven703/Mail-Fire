"""Reference-aware bounded cleanup. Legal hold and incident-specific retention."""

from datetime import timedelta

from sqlalchemy import delete, exists, select

from app.db import transaction
from app.models import (
    Attachment,
    Audit,
    Blob,
    Comment,
    Content,
    Diagnostic,
    ImportRecord,
    Incident,
    Job,
    MailEvent,
    Message,
    Metric,
    Outbox,
    Reference,
    Setting,
    now,
)

DEFAULTS = {
    "ordinary_days": 30,
    "unconfirmed_days": 365,
    "confirmed_days": 365,
    "audit_days": 365,
    "logs_days": 30,
    "metrics_days": 30,
    "paused": False,
}


def cleanup(dry_run=True, limit=100):
    with transaction() as session:
        session.execute(
            __import__("sqlalchemy").text("SELECT pg_advisory_xact_lock(hashtext('retention-cleanup'))")
        )
        setting = session.get(Setting, "retention")
        config = DEFAULTS | (setting.value if setting else {})
        if config["paused"]:
            return {"paused": True, "candidates": [], "deleted": 0}
        candidates = []
        rows = session.scalars(
            select(Message)
            .where(Message.legal_hold.is_(False))
            .order_by(Message.created_at, Message.id)
            .execution_options(yield_per=500)
        )
        for message in rows:
            incidents = list(
                session.scalars(
                    select(Incident)
                    .join(MailEvent, Incident.event_id == MailEvent.id)
                    .where(MailEvent.message_id == message.id)
                )
            )
            days = (
                config["confirmed_days"]
                if any(i.status == "CONFIRMED" for i in incidents)
                else config["unconfirmed_days"]
                if incidents
                else config["ordinary_days"]
            )
            if message.created_at > (now() - timedelta(days=days)).replace(tzinfo=None):
                continue
            active_jobs = session.scalar(
                select(Job.id)
                .where(Job.status.in_(["PENDING", "RUNNING"]), Job.payload["message_id"].astext == message.id)
                .limit(1)
            )
            if active_jobs:
                continue
            candidates.append(message.id)
            if len(candidates) >= limit:
                break
        if dry_run:
            return {"paused": False, "candidates": candidates, "deleted": 0}
        for message_id in candidates:
            session.execute(
                __import__("sqlalchemy").text(
                    "DELETE FROM semantic_chunks WHERE source_type='content' AND source_id IN (SELECT content_id FROM messages WHERE id=:id) AND source_id NOT IN (SELECT content_id FROM messages WHERE id<>:id AND content_id IS NOT NULL)"
                ),
                {"id": message_id},
            )
            events = select(MailEvent.id).where(MailEvent.message_id == message_id)
            incidents = select(Incident.id).where(Incident.event_id.in_(events))
            session.execute(delete(Comment).where(Comment.incident_id.in_(incidents)))
            session.execute(delete(Outbox).where(Outbox.incident_id.in_(incidents)))
            session.execute(delete(Incident).where(Incident.event_id.in_(events)))
            session.execute(delete(ImportRecord).where(ImportRecord.message_id == message_id))
            session.execute(delete(Attachment).where(Attachment.message_id == message_id))
            session.execute(delete(MailEvent).where(MailEvent.message_id == message_id))
            session.execute(delete(Job).where(Job.payload["message_id"].astext == message_id))
            session.execute(delete(Message).where(Message.id == message_id))
            session.add(
                Audit(
                    actor="retention", action="message_deleted", target=message_id, details={"policy": config}
                )
            )
        session.execute(
            delete(Content).where(~exists(select(Message.id).where(Message.content_id == Content.id)))
        )
        session.execute(
            delete(Blob).where(
                ~exists(select(Message.id).where(Message.original_sha == Blob.sha)),
                ~exists(select(Attachment.id).where(Attachment.blob_sha == Blob.sha)),
                ~exists(select(Reference.id).where(Reference.blob_sha == Blob.sha)),
            )
        )
        for model, days_key in [(Diagnostic, "logs_days"), (Metric, "metrics_days"), (Audit, "audit_days")]:
            session.execute(delete(model).where(model.created_at < now() - timedelta(days=config[days_key])))
        return {"paused": False, "candidates": candidates, "deleted": len(candidates)}
