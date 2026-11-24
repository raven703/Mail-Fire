"""Conservative, reference-aware GC. No filesystem/source-directory mutations."""

from django.db import connection, transaction
from django.db.models import Exists, OuterRef

from pipeline.models import WorkItem
from pipeline.services import finish, locked_current
from records.models import Attachment, Audit, Blob, Content, Job, Message, Reference, SemanticChunk


def contains(value, identifier):
    """Check complete JSON string values, including nested parser/bundle outputs."""
    if isinstance(value, str):
        return value == identifier
    if isinstance(value, list):
        return any(contains(item, identifier) for item in value)
    if isinstance(value, dict):
        return any(key == identifier or contains(item, identifier) for key, item in value.items())
    return False


def durable_reference(identifier):
    # Terminal jobs can still be retried or consumed by a later stage. Retain
    # their referenced bytes too; job retention must explicitly release them.
    for payload, output in WorkItem.objects.values_list("payload", "output").iterator(chunk_size=100):
        if contains(payload, identifier) or contains(output, identifier):
            return True
    return any(contains(payload, identifier) for payload in Job.objects.values_list("payload", flat=True).iterator(chunk_size=100))


def collect(job):
    output = {"content": [], "blobs": [], "blocked": False, "dry_run": job.payload.get("dry_run", True)}
    # One bounded transaction. Lock writers as well as existing rows: FK checks
    # alone cannot protect JSON references or an absent/deduplicated blob.
    with transaction.atomic():
        locked_current(job.pk, job.token)
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL lock_timeout = '5s'")
            cursor.execute("LOCK TABLE mice_work_items, jobs, messages, attachments, \"references\", contents, blobs, semantic_chunks IN SHARE ROW EXCLUSIVE MODE")
        if WorkItem.objects.exclude(pk=job.pk).filter(status__in=["PENDING", "RUNNING"]).exists() or Job.objects.filter(status__in=["PENDING", "RUNNING"]).exists():
            output["blocked"] = True
        else:
            content = Content.objects.annotate(linked=Exists(Message.objects.filter(content_id=OuterRef("pk")))).filter(linked=False).order_by("pk")
            for row in list(content[:100]):
                if durable_reference(row.pk) or durable_reference(row.normalized_sha):
                    continue
                output["content"].append(row.pk)
                if not output["dry_run"]:
                    SemanticChunk.objects.filter(source_type="content", source_id=row.pk).delete()
                    row.delete()
            blobs = Blob.objects.annotate(
                mail=Exists(Message.objects.filter(original_sha_ref_id=OuterRef("pk"))),
                attachment=Exists(Attachment.objects.filter(blob_sha_ref_id=OuterRef("pk"))),
                reference=Exists(Reference.objects.filter(blob_sha_ref_id=OuterRef("pk"))),
            ).filter(mail=False, attachment=False, reference=False).order_by("pk")
            for row in list(blobs.only("sha")[:100]):
                if durable_reference(row.pk):
                    continue
                output["blobs"].append(row.pk)
                if not output["dry_run"]:
                    row.delete()
        Audit.objects.create(actor="gc", action="garbage_collection", target=str(job.pk), details=output)
        finish(job.pk, job.token, output)