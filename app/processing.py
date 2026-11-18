import hashlib
import re

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.db import transaction
from app.detectors import VERSION, detect
from app.extraction import extract
from app.mail import parse_mail, put_blob
from app.models import (
    Address,
    Attachment,
    Blob,
    Content,
    Incident,
    MailEvent,
    Message,
    Policy,
)


def analyze(message_id):
    with transaction() as session:
        message = session.get(Message, message_id)
        raw = session.get(Blob, message.original_sha).data
    parsed = parse_mail(raw)
    objects = []
    text = parsed["text"]
    for name, mime, data in parsed["attachments"]:
        extracted, status, details = extract(data, name)
        text += "\n" + extracted
        objects.append((name, mime, data, extracted, status, details))
    normalized = re.sub(r"\s+", " ", text).strip()
    digest = hashlib.sha256(normalized.encode()).hexdigest()
    findings = detect(text)
    with transaction() as session:
        message = session.get(Message, message_id, with_for_update=True)
        content = session.scalar(select(Content).where(Content.normalized_sha == digest))
        if not content:
            session.execute(
                insert(Content)
                .values(
                    id=__import__("uuid").uuid4().hex,
                    normalized_sha=digest,
                    text=text,
                    analysis={"findings": findings},
                    version=VERSION,
                )
                .on_conflict_do_nothing()
            )
            content = session.scalar(select(Content).where(Content.normalized_sha == digest))
        message.content_id = content.id
        message.subject, message.sender = parsed["subject"], parsed["sender"]
        message.recipients, message.headers = parsed["recipients"], parsed["headers"]
        message.status = "PARTIAL" if any(o[4] != "ANALYZED" for o in objects) else "ANALYZED"
        for address in set([parsed["sender"]] + parsed["recipients"]):
            if address:
                session.execute(insert(Address).values(email=address.lower()).on_conflict_do_nothing())
        # Reanalysis replaces derived rows, not originals/events.
        session.query(Attachment).filter_by(message_id=message_id).delete()
        for name, mime, data, extracted, status, details in objects:
            session.add(
                Attachment(
                    message_id=message.id,
                    blob_sha=put_blob(session, data),
                    name=name,
                    mime=mime,
                    text=extracted,
                    status=status,
                    details=details,
                )
            )
        event_ids = list(session.scalars(select(MailEvent.id).where(MailEvent.message_id == message_id)))
    for event_id in event_ids:
        evaluate(event_id)


def evaluate(event_id):
    with transaction() as session:
        event = session.get(MailEvent, event_id)
        message = session.get(Message, event.message_id)
        if not message.content_id:
            return
        findings = session.get(Content, message.content_id).analysis.get("findings", [])
        for policy in session.scalars(
            select(Policy).where(Policy.enabled.is_(True)).order_by(Policy.priority)
        ):
            conditions = policy.conditions
            if conditions.get("direction") and event.direction not in conditions["direction"]:
                continue
            if conditions.get("senders") and message.sender not in conditions["senders"]:
                continue
            matches = [
                f
                for f in findings
                if f["risk"] >= conditions.get("min_risk", 0)
                and (not conditions.get("categories") or f["category"] in conditions["categories"])
            ]
            if len(matches) < conditions.get("min_count", 1) or policy.shadow:
                continue
            session.execute(
                insert(Incident)
                .values(
                    event_id=event.id,
                    policy_id=policy.id,
                    risk=max(f["risk"] for f in matches),
                    findings=matches,
                )
                .on_conflict_do_nothing()
            )
