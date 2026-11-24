"""OCR coordinator: model execution stays in a secret-free isolated service."""

from django.db import transaction

from pipeline.models import WorkItem
from pipeline.parser_client import call
from pipeline.services import enqueue, finish, locked_current
from records.models import Attachment, Message


def complete(job):
    upstream = WorkItem.objects.get(pk=job.payload["extraction_job_id"], status="DONE")
    if upstream.kind != "extraction.extract" or upstream.payload["message_id"] != job.payload["message_id"]:
        raise ValueError("Invalid OCR dependency")
    rows = list(
        Attachment.objects.filter(
            pk__in=upstream.output["attachment_ids"], message_id=job.payload["message_id"]
        ).select_related("blob_sha_ref")
    )
    if len(rows) != len(upstream.output["attachment_ids"]):
        raise ValueError("Missing attachment evidence")
    results = []
    for row in rows:
        if row.details.get("ocr_required"):
            result = call("extract", bytes(row.blob_sha_ref.data), row.name, ocr=True)
            if (
                not isinstance(result.get("text"), str)
                or not isinstance(result.get("details"), dict)
                or result.get("status") not in {"ANALYZED", "PARTIAL", "FAILED", "ENCRYPTED", "UNSUPPORTED"}
            ):
                raise ValueError("Invalid OCR result")
            results.append((row.pk, result))
    with transaction.atomic():
        locked_current(job.pk, job.token)
        message = Message.objects.select_for_update().get(pk=job.payload["message_id"])
        for identifier, result in results:
            Attachment.objects.filter(pk=identifier, message=message).update(
                text=result["text"], status=result["status"], details=result["details"]
            )
        parse_job = WorkItem.objects.get(pk=upstream.payload["parse_job_id"], status="DONE")
        ordered = {row.pk: row for row in Attachment.objects.filter(message=message)}
        attachments = [ordered[identifier] for identifier in upstream.output["attachment_ids"]]
        message.error = "Detection stage not yet connected"
        message.save(update_fields=["error"])
        finish(
            job.pk,
            job.token,
            {
                "text": "\n".join([parse_job.output["text"]] + [row.text for row in attachments]),
                "attachment_ids": upstream.output["attachment_ids"],
                "partial": any(row.status != "ANALYZED" for row in attachments),
                "next_stage": "detection-not-yet-connected",
            },
        )
        enqueue(
            "detection.detect", {"message_id": message.pk, "ocr_job_id": str(job.pk)}, "detect:" + str(job.pk)
        )
