"""Deterministic detection adapter; optional/unported checks remain explicit."""

import hashlib

from django.db import transaction

from pipeline.models import WorkItem
from pipeline.parser_client import call
from pipeline.services import finish, locked_current
from policy_engine.service import request_evaluation
from records.models import Content, Message


def detect(job):
    upstream = WorkItem.objects.get(pk=job.payload["ocr_job_id"], status="DONE")
    if upstream.kind != "ocr.complete" or upstream.payload["message_id"] != job.payload["message_id"]:
        raise ValueError("Invalid detection dependency")
    text = upstream.output["text"]
    result = call("detect", text.encode())
    if not isinstance(result.get("findings"), list) or not isinstance(result.get("version"), str):
        raise ValueError("Invalid detection response")
    # Do not label a limited deterministic adapter as complete legacy analysis.
    errors = [
        {"engine": name, "error": "not_yet_ported"}
        for name in (
            "antivirus",
            "secrets_scan",
            "normalization",
            "category_rules",
            "references",
            "document_templates",
        )
    ]
    analysis = {"findings": result["findings"], "engine_errors": errors, "skipped_checks": ["ml", "llm"]}
    with transaction.atomic():
        locked_current(job.pk, job.token)
        message = Message.objects.select_for_update().get(pk=job.payload["message_id"])
        content, _ = Content.objects.get_or_create(
            normalized_sha=hashlib.sha256((str(job.pk) + "\0" + text).encode()).hexdigest(),
            defaults={"text": text, "analysis": analysis, "version": result["version"]},
        )
        message.content = content
        message.status = "PARTIAL"
        message.error = "Incomplete engine coverage; see engine_errors"
        message.save(update_fields=["content", "status", "error"])
        evaluation = request_evaluation(message.pk, "analysis:" + str(job.pk))
        finish(
            job.pk,
            job.token,
            {"content_id": content.pk, "policy_job_id": str(evaluation.pk), "status": "PARTIAL"},
        )
