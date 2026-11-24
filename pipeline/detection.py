"""Deterministic detection adapter; optional/unported checks remain explicit."""

import hashlib
import json
from types import SimpleNamespace

from django.conf import settings
from django.db import transaction

from pipeline.evidence import configuration
from pipeline.models import WorkItem
from pipeline.parser_client import call
from pipeline.services import finish, locked_current
from records.models import Address, Attachment, Content, Message


def detect(job):
    upstream = WorkItem.objects.get(pk=job.payload["ocr_job_id"], status="DONE")
    if upstream.kind != "ocr.complete" or upstream.payload["message_id"] != job.payload["message_id"]:
        raise ValueError("Invalid detection dependency")
    text = upstream.output["text"]
    message = Message.objects.select_related("original_sha_ref").get(pk=job.payload["message_id"])
    attachments = list(Attachment.objects.filter(
        pk__in=upstream.output["attachment_ids"], message=message,
    ).select_related("blob_sha_ref"))
    if len(attachments) != len(upstream.output["attachment_ids"]):
        raise ValueError("Missing detection attachment evidence")
    config = configuration()
    result = call("detection_evidence", json.dumps({
        "text": text, "configuration": config,
        "attachments": [{"name": row.name, "text": row.text, "status": row.status} for row in attachments],
    }).encode())
    if not isinstance(result.get("findings"), list) or not isinstance(result.get("version"), str):
        raise ValueError("Invalid detection response")
    errors = list(result.get("engine_errors", []))
    findings = list(result["findings"])
    enabled = config["settings"].get("detectors", {})
    skipped = set(result.get("skipped_checks", [])) | {"ml", "llm"}
    objects = [("message.eml", bytes(message.original_sha_ref.data))] + [
        (row.name, bytes(row.blob_sha_ref.data)) for row in attachments
    ]
    av_states = []
    if enabled.get("antivirus", True):
        from app.antivirus import scan

        av_config = SimpleNamespace(clamav_host=settings.MICE_CLAMAV_HOST, clamav_port=settings.MICE_CLAMAV_PORT)
        for name, data in objects:
            try:
                av = scan(data, name, config=av_config)
                av_states.append(av["status"])
                findings.extend(av["findings"])
            except Exception as exc:
                av_states.append("FAILED")
                errors.append({"engine": "antivirus", "error": type(exc).__name__})
    else:
        skipped.add("antivirus")
    for name, data in [("body.txt", text.encode())] + objects[1:]:
        try:
            scanned = call("scan", data, name)
            findings.extend(scanned["findings"])
            for engine, state in scanned["engines"].items():
                if state != "OK":
                    errors.append({"engine": engine, "error": state})
        except Exception as exc:
            errors.append({"engine": "static_scan", "error": type(exc).__name__})
    for row in attachments:
        findings.extend(row.details.get("findings", []))
    from app.analysis_status import classify_analysis

    status, status_skipped = classify_analysis(
        [(row.status, row.details) for row in attachments], av_states, [], [],
        antivirus_enabled=enabled.get("antivirus", True), ml_enabled=False,
        ocr_enabled=settings.MICE_OCR_ENABLED,
    )
    if errors:
        status = "PARTIAL"
    analysis = {
        "findings": findings, "engine_errors": errors,
        "skipped_checks": sorted(skipped | set(status_skipped)),
        "normalization": result.get("normalization", {}),
        "configuration_snapshot": config,
        "configuration_sha256": hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest(),
    }
    with transaction.atomic():
        locked_current(job.pk, job.token)
        message = Message.objects.select_for_update().get(pk=job.payload["message_id"])
        content, _ = Content.objects.get_or_create(
            normalized_sha=hashlib.sha256((str(job.pk) + "\0" + text).encode()).hexdigest(),
            defaults={"text": text, "analysis": analysis, "version": result["version"]},
        )
        message.content = content
        message.status = status
        message.error = "Incomplete analysis; see engine_errors/attachments" if status == "PARTIAL" else None
        message.save(update_fields=["content", "status", "error"])
        for address in set([message.sender] + message.recipients):
            if address:
                Address.objects.get_or_create(email=address.lower())
        from pipeline.inference import route

        evaluation = route(message, "analysis:" + str(job.pk))
        finish(
            job.pk,
            job.token,
            {"content_id": content.pk, "policy_job_id": str(evaluation.pk), "status": status},
        )
