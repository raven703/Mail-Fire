"""Policy-only evaluation of persisted evidence; no parser/OCR/inference imports."""

import hashlib
import json

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from pipeline.services import enqueue, finish, locked_current
from policy_engine.catalog import DETECTORS
from policy_engine.models import AnalysisRevision, Evaluation, PolicyRevision
from policy_engine.rules import classify_direction, policy_matches
from records.models import Category, Incident, MailEvent, Message, Outbox, Policy, Setting


class EvidenceUnavailable(ValueError):
    pass



def reevaluate_batch(job):
    identifiers = job.payload["message_ids"]
    progress = {"completed": 0, "queued": 0, "skipped": 0, **job.output}
    for message_id in identifiers[progress["completed"]:]:
        with transaction.atomic():
            current = locked_current(job.pk, job.token)
            try:
                request_evaluation(message_id, f"batch:{job.pk}")
            except (EvidenceUnavailable, Message.DoesNotExist):
                progress["skipped"] += 1
            else:
                progress["queued"] += 1
            progress["completed"] += 1
            current.output = progress
            current.save(update_fields=["output"])
    finish(job.pk, job.token, progress)

def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


@transaction.atomic
def request_evaluation(message_id, request_id):
    message = Message.objects.select_for_update(of=("self",)).select_related("content").get(pk=message_id)
    if not message.content_id or message.status not in {"ANALYZED", "PARTIAL"}:
        raise EvidenceUnavailable("Saved analysis is not available for policy-only evaluation")
    content = message.content
    if not isinstance(content.analysis, dict) or not isinstance(content.analysis.get("findings"), list):
        raise EvidenceUnavailable("Saved findings are missing")
    results = {
        "analysis": content.analysis,
        "content_id": content.pk,
        "sender": message.sender,
        "recipients": message.recipients,
        "detector_version": content.version,
        "status": message.status,
    }
    analysis, _ = AnalysisRevision.objects.get_or_create(
        message=message,
        fingerprint=digest(results),
        defaults={"detector_version": content.version, "message_status": message.status, "results": results},
    )
    snapshots, revision_ids = [], []
    for policy in Policy.objects.order_by("priority", "id"):
        snapshot = {
            "id": policy.pk,
            "name": policy.name,
            "version": policy.version,
            "enabled": policy.enabled,
            "archived": policy.archived,
            "shadow": policy.shadow,
            "priority": policy.priority,
            "conditions": policy.conditions,
        }
        revision, _ = PolicyRevision.objects.get_or_create(
            policy_id=policy.pk,
            version=policy.version,
            fingerprint=digest(snapshot),
            defaults={"snapshot": snapshot},
        )
        snapshots.append(snapshot)
        revision_ids.append(str(revision.pk))
    detector_config = Setting.objects.filter(pk="detectors").first()
    config = {
        "detectors": detector_config.value if detector_config else {},
        "active_categories": sorted(Category.objects.filter(active=True).values_list("id", flat=True)),
        "internal_domains": settings.MICE_INTERNAL_DOMAINS,
        "event_ids": sorted(MailEvent.objects.filter(message=message).values_list("id", flat=True)),
    }
    if not config["event_ids"]:
        raise EvidenceUnavailable("No delivery events available")
    job = enqueue(
        "policy.evaluate",
        {
            "message_id": message.pk,
            "analysis_id": str(analysis.pk),
            "policies": snapshots,
            "policy_revision_ids": revision_ids,
            "settings": config,
        },
        f"policy:{message.pk}:{request_id}",
    )
    return job


def enqueue_notifications(incident):
    row = Setting.objects.filter(pk="integrations").first()
    if row is None:
        return
    # Incident/message lock in caller serializes creation for all destinations.
    for destination in row.value.get("destinations", []):
        if not destination.get("enabled", True):
            continue
        target = destination["url"]
        notice, _ = Outbox.objects.get_or_create(
            incident=incident,
            destination=target,
            defaults={
                "payload": {
                    "class_uid": 2001,
                    "category_uid": 2,
                    "activity_id": 1,
                    "time": timezone.now().isoformat(),
                    "event_id": incident.event_id,
                    "incident_id": incident.pk,
                    "risk": incident.risk,
                    "categories": sorted({finding["category"] for finding in incident.findings}),
                    "url": "/incidents/" + incident.pk,
                }
            },
        )
        enqueue(
            "notifications.deliver", {"outbox_id": notice.pk}, f"notification:{notice.pk}", max_attempts=8
        )


@transaction.atomic
def evaluate(job):
    locked_current(job.pk, job.token)
    payload = job.payload
    analysis = AnalysisRevision.objects.get(pk=payload["analysis_id"], message_id=payload["message_id"])
    message = Message.objects.select_for_update().get(pk=payload["message_id"])
    # Serialized message lock prevents an older queued snapshot from replacing
    # newer incident decisions after out-of-order worker completion.
    if Evaluation.objects.filter(analysis__message=message, job__created_at__gt=job.created_at).exists():
        finish(job.pk, job.token, {"evaluation_complete": False, "superseded": True})
        return
    config = payload["settings"]
    evidence = analysis.results
    direction = classify_direction(evidence["sender"], evidence["recipients"], config["internal_domains"])
    events = list(MailEvent.objects.filter(message=message, pk__in=config["event_ids"]).order_by("id"))
    if not events:
        raise EvidenceUnavailable("Delivery context was removed")
    MailEvent.objects.filter(pk__in=[event.pk for event in events]).update(direction=direction)
    disabled = {
        category
        for key, value in DETECTORS.items()
        if not config["detectors"].get(key, True)
        for category in value[2]
    }
    findings = [
        finding
        for finding in evidence["analysis"]["findings"]
        if finding["category"] in config["active_categories"]
        and finding["category"] not in disabled
        and not (
            not config["detectors"].get("ml", True)
            and finding.get("source") in {"supervised-ml", "custom-ml"}
        )
    ]
    matched = []
    for policy in payload["policies"]:
        if not policy["enabled"] or policy["archived"]:
            continue
        conditions = policy["conditions"]
        if conditions.get("direction") and direction not in conditions["direction"]:
            continue
        if conditions.get("senders") and evidence["sender"] not in conditions["senders"]:
            continue
        matches = policy_matches(findings, conditions)
        if not matches or policy["shadow"]:
            continue
        matched.append(
            {
                "policy_id": policy["id"],
                "name": policy["name"],
                "version": policy["version"],
                "conditions": conditions,
                "risk": max(f["risk"] for f in matches),
                "findings": matches,
                "active": True,
                "event_ids": [event.pk for event in events],
            }
        )
    incident = Incident.objects.select_for_update().filter(message=message).first()
    if matched or incident:
        prior = {str(hit.get("policy_id")): dict(hit) for hit in incident.policy_hits} if incident else {}
        for hit in prior.values():
            hit["active"] = False
        prior.update({hit["policy_id"]: hit for hit in matched})
        history, combined = list(prior.values()), []
        for hit in history:
            for finding in hit.get("findings", []):
                if finding not in combined:
                    combined.append(finding)
        risk = max((hit.get("risk", 0) for hit in history), default=0)
        if incident:
            incident.policy_hits, incident.findings, incident.risk = history, combined, risk
            incident.save(update_fields=["policy_hits", "findings", "risk"])
        else:
            # The current policy may have been deleted after the snapshot.
            primary_id = matched[0]["policy_id"]
            incident = Incident.objects.create(
                message=message,
                event=events[0],
                policy_id=primary_id if Policy.objects.filter(pk=primary_id).exists() else None,
                policy_hits=history,
                findings=combined,
                risk=risk,
            )
            enqueue_notifications(incident)
    Evaluation.objects.create(
        job=job,
        analysis=analysis,
        policy_revisions=payload["policy_revision_ids"],
        policy_snapshot=payload["policies"],
        settings_snapshot=config,
        hits=matched,
    )
    # Never changes message completeness: PARTIAL remains PARTIAL.
    finish(
        job.pk,
        job.token,
        {
            "evaluation_complete": True,
            "matches": len(matched),
            "analysis_id": str(analysis.pk),
            "analysis_status": analysis.message_status,
        },
    )
