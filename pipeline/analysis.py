"""Unified analysis coordinator: remote-only parsing, fenced atomic persistence."""
import base64
import hashlib
import json
from types import SimpleNamespace

from django.conf import settings
from django.db import transaction

from pipeline.evidence import configuration
from pipeline.parser_client import call
from pipeline.services import finish, locked_current
from records.models import Address, Attachment, Blob, Content, Message


STATUSES = {"ANALYZED", "PARTIAL", "FAILED", "ENCRYPTED", "UNSUPPORTED"}


def validate(result):
    parsed = result["parsed"]
    if any(not isinstance(parsed[k], str) for k in ("subject", "sender", "text")):
        raise ValueError("Invalid parsed text")
    if not isinstance(parsed["recipients"], list) or not all(isinstance(a, str) for a in parsed["recipients"]):
        raise ValueError("Invalid recipients")
    if not isinstance(parsed["headers"], dict):
        raise ValueError("Invalid headers")
    rows = result["attachments"]
    if not isinstance(rows, list) or len(rows) > settings.MICE_IMPORT_MAX_OBJECTS:
        raise ValueError("Attachment count limit")
    seen = set()
    total = 0
    import uuid
    for row in rows:
        identifier = str(uuid.UUID(row["id"]))
        if identifier != row["id"] or identifier in seen:
            raise ValueError("Duplicate or invalid attachment identity")
        seen.add(identifier)
        if any(not isinstance(row[k], str) for k in ("name", "mime", "text")):
            raise ValueError("Invalid attachment")
        if row["status"] not in STATUSES or not isinstance(row["details"], dict):
            raise ValueError("Invalid extraction result")
        row["raw"] = base64.b64decode(row["data"], validate=True)
        total += len(row["raw"])
        if total > settings.MICE_IMPORT_MAX_BYTES:
            raise ValueError("Attachment bytes limit")
    evidence = result["evidence"]
    if not isinstance(evidence["findings"], list) or not isinstance(evidence["version"], str):
        raise ValueError("Invalid evidence")
    if not isinstance(evidence["engine_errors"], list) or not isinstance(evidence["skipped_checks"], list):
        raise ValueError("Invalid evidence status")
    if result["text"] != "\n".join([parsed["text"]] + [row["text"] for row in rows]):
        raise ValueError("Invalid combined text")
    return parsed, rows, evidence


def analyze(job):
    message = Message.objects.select_related("original_sha_ref").get(pk=job.payload["message_id"])
    original = bytes(message.original_sha_ref.data)
    config = configuration()
    from records.ocr_settings import configuration as ocr_configuration
    ocr = ocr_configuration()
    result = call("analyze_message", json.dumps({
        "original": base64.b64encode(original).decode(),
        "configuration": config,
        "ocr_enabled": ocr["enabled"], "ocr_provider": ocr["provider"],
    }).encode())
    parsed, rows, evidence = validate(result)
    errors = list(evidence["engine_errors"])
    findings = list(evidence["findings"])
    skipped = set(evidence["skipped_checks"]) | {"ml", "llm"}
    enabled = config["settings"].get("detectors", {})
    av_states = []
    if enabled.get("antivirus", True):
        from app.antivirus import scan
        av_config = SimpleNamespace(clamav_host=settings.MICE_CLAMAV_HOST, clamav_port=settings.MICE_CLAMAV_PORT)
        for name, data in [("message.eml", original)] + [(r["name"], r["raw"]) for r in rows]:
            try:
                av = scan(data, name, config=av_config)
                av_states.append(av["status"])
                findings.extend(av["findings"])
            except Exception as exc:
                av_states.append("FAILED")
                errors.append({"engine": "antivirus", "error": type(exc).__name__})
    else:
        skipped.add("antivirus")
    from app.evidence import unique_findings
    from app.analysis_status import classify_analysis
    from policy_engine.catalog import DETECTORS
    disabled = {category for key, value in DETECTORS.items() if not enabled.get(key, True) for category in value[2]}
    disabled.update(config.get("inactive_categories", []))
    findings = unique_findings(hit for hit in findings if hit["category"] not in disabled)
    config_sha = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    rules = {rule["id"] for group in config.get("groups", []) for rule in group["rules"]}
    for finding in findings:
        if finding.get("rule_id") in rules:
            finding["configuration_sha256"] = config_sha
    status, status_skipped = classify_analysis(
        [(r["status"], r["details"]) for r in rows], av_states, [], [],
        antivirus_enabled=enabled.get("antivirus", True), ml_enabled=False,
        ocr_enabled=ocr["enabled"],
    )
    if errors:
        status = "PARTIAL"
    analysis = {"findings": findings, "engine_errors": errors,
                "skipped_checks": sorted(skipped | set(status_skipped)),
                "normalization": evidence.get("normalization", {}),
                "configuration_snapshot": config, "configuration_sha256": config_sha}
    with transaction.atomic():
        locked_current(job.pk, job.token)
        message = Message.objects.select_for_update().get(pk=message.pk)
        if message.content_id or Attachment.objects.filter(message=message).exists():
            if not job.payload.get("reanalysis"):
                raise ValueError("Existing evidence; refusing overwrite")
            if message.content_id:
                previous = Content.objects.select_for_update().get(pk=message.content_id)
                snapshot = dict(previous.analysis)
                snapshot.setdefault("attachment_snapshot", list(
                    Attachment.objects.filter(message=message).order_by("pk").values(
                        "id", "blob_sha_ref_id", "name", "mime", "text", "status", "details",
                    )
                ))
                previous.analysis = snapshot
                previous.save(update_fields=["analysis"])
            Attachment.objects.filter(message=message).delete()
        identifiers = []
        for row in rows:
            data = row["raw"]
            digest = hashlib.sha256(data).hexdigest()
            Blob.objects.get_or_create(sha=digest, defaults={"data": data, "size": len(data)})
            Attachment.objects.create(pk=row["id"], message=message, blob_sha_ref_id=digest,
                                      name=row["name"], mime=row["mime"], text=row["text"],
                                      status=row["status"], details=row["details"])
            identifiers.append(row["id"])
        text = result["text"]
        content, _ = Content.objects.get_or_create(
            normalized_sha=hashlib.sha256((str(job.pk) + "\0" + text).encode()).hexdigest(),
            defaults={"text": text, "analysis": analysis, "version": evidence["version"]},
        )
        for key in ("subject", "sender", "recipients", "headers"):
            setattr(message, key, parsed[key])
        message.content = content
        message.status = status
        message.error = "Incomplete analysis; see engine_errors/attachments" if status == "PARTIAL" else None
        message.save(update_fields=["subject", "sender", "recipients", "headers", "content", "status", "error"])
        for address in set([message.sender] + message.recipients):
            if address:
                Address.objects.get_or_create(email=address.lower())
        from pipeline.inference import route
        evaluation = route(message, "analysis:" + str(job.pk))
        finish(job.pk, job.token, {"content_id": content.pk, "attachment_ids": identifiers,
                                   "policy_job_id": str(evaluation.pk), "status": status,
                                   "timings": result.get("timings", {})})
