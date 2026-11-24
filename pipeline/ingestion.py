"""Durable acceptance; source identity and blob identity serialize independently."""

import hashlib

from django.conf import settings
from django.db import connection, transaction

from pipeline.services import enqueue, finish, locked_current
from records.models import Blob, ImportRecord, MailEvent, Message


@transaction.atomic
def accept(data, source, source_key, name, envelope=None):
    if not data or len(data) > settings.MICE_MAX_MESSAGE_BYTES:
        raise ValueError("Invalid message size")
    if not source_key or len(source_key) > 2048 or len(name) > 1024:
        raise ValueError("Invalid source identity")
    digest = hashlib.sha256(data).hexdigest()
    with connection.cursor() as cursor:
        for key in sorted({"source:" + source_key, "blob:" + digest}):
            cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", [key])
    existing = ImportRecord.objects.filter(source_key=source_key).first()
    if existing:
        if existing.message.original_sha_ref_id != digest:
            raise ValueError("Source identity reused with different content")
        return existing
    Blob.objects.get_or_create(sha=digest, defaults={"data": data, "size": len(data)})
    message, created = Message.objects.get_or_create(
        original_sha_ref_id=digest,
        defaults={
            "format": "msg" if data.startswith(bytes.fromhex("d0cf11e0a1b11ae1")) else "eml",
        },
    )
    event = MailEvent.objects.create(
        message=message, source=source, source_key=source_key, envelope=envelope or {}
    )
    record = ImportRecord.objects.create(
        source_key=source_key, name=name, status="SAVED", message=message, duplicate=not created
    )
    if created:
        enqueue("ingestion.parse", {"message_id": message.pk}, "parse:" + message.pk)
    elif message.status in {"ANALYZED", "PARTIAL"}:
        from policy_engine.service import request_evaluation

        request_evaluation(message.pk, "delivery:" + event.pk)
    return record


def parse(job):
    from pipeline.parser_client import call

    message = Message.objects.select_related("original_sha_ref").get(pk=job.payload["message_id"])
    parsed = call("mail", bytes(message.original_sha_ref.data))
    with transaction.atomic():
        locked_current(job.pk, job.token)
        message = Message.objects.select_for_update().get(pk=message.pk)
        for key in ("subject", "sender", "recipients", "headers"):
            setattr(message, key, parsed[key])
        message.status = "PENDING"
        message.error = None
        message.save()
        attachments = []
        for name, mime, data in parsed["attachments"]:
            digest = hashlib.sha256(data).hexdigest()
            Blob.objects.get_or_create(sha=digest, defaults={"data": data, "size": len(data)})
            attachments.append({"name": name, "mime": mime, "blob_sha": digest})
        finish(
            job.pk,
            job.token,
            {
                "text": parsed["text"],
                "attachments": attachments,
                "next_stage": "extraction",
            },
        )
        enqueue(
            "extraction.extract",
            {"message_id": message.pk, "parse_job_id": str(job.pk)},
            "extract:" + str(job.pk),
        )
