"""Persist isolated parser results atomically with fenced stage completion."""

from django.db import transaction

from pipeline.models import WorkItem
from pipeline.parser_client import call
from pipeline.services import finish, locked_current
from records.models import Attachment, Blob, Message


def extract(job):
    upstream = WorkItem.objects.get(pk=job.payload["parse_job_id"], status=WorkItem.Status.DONE)
    if upstream.kind != "ingestion.parse" or upstream.payload["message_id"] != job.payload["message_id"]:
        raise ValueError("Invalid extraction dependency")
    output = upstream.output
    results = []
    for attachment in output["attachments"]:
        blob = Blob.objects.get(pk=attachment["blob_sha"])
        result = call("extract", bytes(blob.data), attachment["name"])
        if (
            not isinstance(result.get("text"), str)
            or result.get("status") not in {"ANALYZED", "PARTIAL", "ENCRYPTED", "UNSUPPORTED", "FAILED"}
            or not isinstance(result.get("details"), dict)
        ):
            raise ValueError("Invalid extraction result")
        results.append((attachment, result))
    with transaction.atomic():
        locked_current(job.pk, job.token)
        message = Message.objects.select_for_update().get(pk=job.payload["message_id"])
        # All rows and completion commit together: redelivery cannot append duplicates.
        if Attachment.objects.filter(message=message).exists():
            raise ValueError("Attachment evidence already exists; refusing overwrite")
        identifiers = []
        for attachment, result in results:
            row = Attachment.objects.create(
                message=message,
                blob_sha_ref_id=attachment["blob_sha"],
                name=attachment["name"],
                mime=attachment["mime"],
                text=result["text"],
                status=result["status"],
                details=result["details"],
            )
            identifiers.append(row.pk)
        message.error = "Detection stage not yet connected"
        message.save(update_fields=["error"])
        finish(
            job.pk,
            job.token,
            {
                "attachment_ids": identifiers,
                "text": "\n".join([output["text"]] + [result["text"] for _, result in results]),
                "partial": any(result["status"] != "ANALYZED" for _, result in results),
                "next_stage": "detection-not-yet-connected",
            },
        )
