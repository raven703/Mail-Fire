import hashlib
import re

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.db import transaction
from app.detectors import VERSION, detect
from app.mail import put_blob
from app.models import (
    Address,
    Attachment,
    Blob,
    Content,
    Incident,
    MailEvent,
    Message,
    MLModel,
    Policy,
    Reference,
    Setting,
)
from app.sandbox import call


def analyze(message_id):
    with transaction() as session:
        message = session.get(Message, message_id)
        raw = session.get(Blob, message.original_sha).data
    parsed = call("mail", raw)
    objects = []
    text = parsed["text"]
    for name, mime, data in parsed["attachments"]:
        result = call("extract", data, name)
        extracted, status, details = result["text"], result["status"], result["details"]
        text += "\n" + extracted
        objects.append((name, mime, data, extracted, status, details))
    normalized = re.sub(r"\s+", " ", text).strip()
    digest = hashlib.sha256(normalized.encode()).hexdigest()
    findings = detect(text)
    with transaction() as session:
        from app.fingerprints import compare

        for reference in session.scalars(select(Reference)):
            match = compare(text, reference.text, reference.fingerprint)
            if match["exact"] or (
                match["reference_coverage"] >= 0.3 and len(match["matched_fragments"]) >= 3
            ):
                findings.append(
                    {
                        "category": "REFERENCE_DOCUMENT",
                        "rule_id": reference.id,
                        "risk": 75,
                        "confidence": match["reference_coverage"],
                        "start": 0,
                        "end": 0,
                        "excerpt": "\n".join(match["matched_fragments"])[:1000],
                        "source": "fingerprint",
                        "version": "shingle5-minhash64-v1",
                        "reason": match["reason"],
                        "status": "ANALYZED",
                        "similarity": match,
                    }
                )
    with transaction() as session:
        active_model = session.scalar(select(MLModel).where(MLModel.active.is_(True)))
        if active_model:
            from app.ml import infer

            predictions = infer(active_model.artifact, text)
            for prediction in predictions:
                if prediction["matched"]:
                    findings.append(
                        {
                            "category": prediction["category"],
                            "rule_id": "ml-classification",
                            "risk": 50,
                            "confidence": prediction["confidence"],
                            "start": 0,
                            "end": 0,
                            "excerpt": "",
                            "source": "supervised-ml",
                            "version": active_model.id,
                            "reason": "Вероятностная классификация; не доказательство утечки",
                            "status": "ANALYZED",
                        }
                    )
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
        # Reanalysis must update results after detector/model changes.
        content.analysis = {"findings": findings}
        content.version = VERSION
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
    from app.semantic import index_document, search

    with transaction() as session:
        index_document(session, "content", content.id, text)
        matches = search(session, text[:10000], "reference", 10)
        semantic_findings = []
        for match in matches:
            if match["similarity"] >= 0.8:
                semantic_findings.append(
                    {
                        "category": "SEMANTIC_REFERENCE",
                        "rule_id": match["source_id"],
                        "risk": 50,
                        "confidence": match["similarity"],
                        "start": 0,
                        "end": 0,
                        "excerpt": match["text"][:1000],
                        "source": "semantic",
                        "version": match["model"],
                        "reason": "Семантическое сходство; не доказательство утечки",
                        "status": "ANALYZED",
                    }
                )
        current = session.get(Content, content.id)
        current.analysis = {"findings": findings + semantic_findings}
    for event_id in event_ids:
        evaluate(event_id)


def evaluate(event_id):
    with transaction() as session:
        event = session.get(MailEvent, event_id)
        message = session.get(Message, event.message_id)
        if not message.content_id:
            return
        findings = session.get(Content, message.content_id).analysis.get("findings", [])
        from app.catalog_api import DETECTORS

        config = session.get(Setting, "detectors")
        disabled = {
            category
            for key, value in DETECTORS.items()
            if config and not config.value.get(key, True)
            for category in value[2]
        }
        findings = [
            f
            for f in findings
            if f["category"] not in disabled
            and not (config and not config.value.get("ml", True) and f.get("source") == "supervised-ml")
        ]
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
            result = session.execute(
                insert(Incident)
                .values(
                    event_id=event.id,
                    policy_id=policy.id,
                    risk=max(f["risk"] for f in matches),
                    findings=matches,
                )
                .on_conflict_do_nothing()
                .returning(Incident.id)
            )
            incident_id = result.scalar_one_or_none()
            if incident_id:
                from app.integrations import enqueue

                enqueue(session, session.get(Incident, incident_id))
