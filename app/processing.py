import hashlib
import re

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.config import settings
from app.db import transaction
from app.detectors import VERSION, detect
from app.mail import classify_direction, put_blob
from app.models import (
    Address,
    Attachment,
    Blob,
    Content,
    Incident,
    Job,
    MailEvent,
    Message,
    MLModel,
    Policy,
    Reference,
    Setting,
)
from app.sandbox import call


def assert_current_job(session, job_id=None, owner=None):
    """Prevent an expired worker lease from committing derived results."""
    if job_id is None:
        return
    from datetime import UTC

    from app.models import now

    job = session.get(Job, job_id, with_for_update=True)
    if not job or job.owner != owner or job.status != "RUNNING" or not job.lease_until:
        raise RuntimeError("Stale job lease: refusing writes")
    if job.lease_until.replace(tzinfo=UTC) <= now():
        raise RuntimeError("Expired job lease: refusing writes")


def analyze(message_id, job_id=None, owner=None):
    with transaction() as session:
        message = session.get(Message, message_id)
        raw = session.get(Blob, message.original_sha).data
    parsed = call("mail", raw)
    from app.antivirus import scan as antivirus_scan

    objects = []
    antivirus_states = []
    initial_av = antivirus_scan(raw, "message.eml")
    antivirus_states.append(initial_av["status"])
    attachment_findings = initial_av["findings"]
    text = parsed["text"]
    attachment_findings.extend(call("scan", text.encode(), "body.txt")["findings"])
    for name, mime, data in parsed["attachments"]:
        av_result = antivirus_scan(data, name)
        antivirus_states.append(av_result["status"])
        attachment_findings.extend(av_result["findings"])
        attachment_findings.extend(call("scan", data, name)["findings"])
        result = call("extract", data, name)
        extracted, status, details = result["text"], result["status"], result["details"]
        attachment_findings.extend(details.pop("findings", []))
        text += "\n" + extracted
        objects.append((name, mime, data, extracted, status, details))
    normalized = re.sub(r"\s+", " ", text).strip()
    # Binary evidence is not determined by extracted text alone (macros, executables).
    identity = (
        normalized.encode()
        + b"\0advanced-1\0"
        + b"\0".join(hashlib.sha256(data).digest() for _, _, data in parsed["attachments"])
    )
    digest = hashlib.sha256(identity).hexdigest()
    findings = detect(text)
    findings.extend(attachment_findings)
    from app.advanced_detectors import pii

    findings.extend(pii(text))
    reference_matches = []
    with transaction() as session:
        from app.fingerprints import compare

        for reference in session.scalars(select(Reference)):
            match = compare(text, reference.text, reference.fingerprint)
            if match["exact"] or (
                match["reference_coverage"] >= 0.3 and len(match["matched_fragments"]) >= 3
            ):
                reference_matches.append(
                    {
                        "reference_id": reference.id,
                        "confidence": match["reference_coverage"],
                        "excerpt": "\n".join(match["matched_fragments"])[:1000],
                    }
                )
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
    ml_scores = {}
    with transaction() as session:
        active_model = session.scalar(select(MLModel).where(MLModel.active.is_(True)))
        if active_model:
            from app.ml import infer

            try:
                predictions = infer(active_model.artifact, text)
            except Exception:
                # Preserve deterministic evidence when the model is unavailable.
                predictions = []
                active_model = None
            ml_scores = {p["category"]: p for p in predictions}
            # Custom categories are emitted only by their configured ML rule.
            from app.models import Category

            builtin_categories = set(
                session.scalars(
                    select(Category.id).where(Category.mode == "builtin", Category.active.is_(True))
                )
            )
            for prediction in predictions:
                if prediction["matched"] and prediction["category"] in builtin_categories:
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
        from app.categories import custom_findings

        findings.extend(
            custom_findings(
                session,
                text,
                references=reference_matches,
                ml_scores=ml_scores,
                available_engines={"keywords", "regex", "reference"} | ({"ml"} if active_model else set()),
            )
        )

    with transaction() as session:
        assert_current_job(session, job_id, owner)
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
        message.status = (
            "PARTIAL"
            if (
                any(o[4] != "ANALYZED" for o in objects)
                or any(state not in {"OK", "FOUND"} for state in antivirus_states)
            )
            else "ANALYZED"
        )
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
        events = list(session.scalars(select(MailEvent).where(MailEvent.message_id == message_id)))
        direction = classify_direction(parsed["sender"], parsed["recipients"], settings().internal_domains)
        for event in events:
            event.direction = direction
        event_ids = [event.id for event in events]
    for event_id in event_ids:
        evaluate(event_id, job_id, owner)
    from app.semantic import index_document, search

    with transaction() as session:
        assert_current_job(session, job_id, owner)
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
        from app.categories import custom_findings

        # Include semantic evidence in the same ANY/ALL category decision.
        semantic_refs = [
            {"reference_id": m["source_id"], "confidence": m["similarity"], "excerpt": m["text"][:1000]}
            for m in matches
        ]
        merged = custom_findings(
            session,
            text,
            references=reference_matches + semantic_refs,
            ml_scores=ml_scores,
            available_engines={"keywords", "regex", "reference"} | ({"ml"} if active_model else set()),
        )
        original = [f for f in findings if not str(f.get("source", "")).startswith("custom-")]
        current = session.get(Content, content.id)
        current.analysis = {"findings": original + merged + semantic_findings}
    for event_id in event_ids:
        evaluate(event_id, job_id, owner)


def policy_matches(findings, conditions):
    """Findings are counted individually; any/all applies to category coverage.

    min_risk is a per-finding threshold, min_count is a total finding count,
    and 'all' additionally needs one qualifying finding from every category.
    Existing policies default to 'any' for backward compatibility.
    """
    requested = set(conditions.get("categories") or [])
    result = [
        f for f in findings
        if f["risk"] >= conditions.get("min_risk", 0)
        and (not requested or f["category"] in requested)
    ]
    if len(result) < conditions.get("min_count", 1):
        return []
    if conditions.get("category_match", "any") == "all":
        if not requested or not requested.issubset({f["category"] for f in result}):
            return []
    return result


def evaluate(event_id, job_id=None, owner=None):
    with transaction() as session:
        assert_current_job(session, job_id, owner)
        event = session.get(MailEvent, event_id)
        if not event:
            return
        message = session.get(Message, event.message_id, with_for_update=True)
        event.direction = classify_direction(message.sender, message.recipients, settings().internal_domains)
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
        from app.models import Category

        active_categories = set(session.scalars(select(Category.id).where(Category.active.is_(True))))
        findings = [
            f
            for f in findings
            if f["category"] in active_categories
            and f["category"] not in disabled
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
            matches = policy_matches(findings, conditions)
            if not matches or policy.shadow:
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
