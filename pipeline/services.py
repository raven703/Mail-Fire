import random
import uuid
from datetime import timedelta

from django.db import transaction
from django.conf import settings
from django.db.models import Max
from django.db.models.fields.json import KeyTextTransform
from django.utils import timezone

from pipeline.config import limits
from pipeline.models import Attempt, Dispatch, WorkItem


class StaleAttempt(RuntimeError):
    pass


@transaction.atomic
def enqueue(kind, payload, deduplication_key, max_attempts=5):
    from pipeline.handlers import handlers

    group, _ = handlers[kind]
    job, created = WorkItem.objects.get_or_create(
        deduplication_key=deduplication_key,
        defaults={"kind": kind, "queue": group, "payload": payload, "max_attempts": max_attempts},
    )
    if not created and (job.kind != kind or job.payload != payload):
        raise ValueError("Deduplication key reused with different work")
    if created:
        Dispatch.objects.create(job=job, generation=job.generation)
    return job


def dispatch(job, dead=False):
    job.generation += 1
    job.save()
    Dispatch.objects.create(
        job=job, generation=job.generation, dead_letter=dead, available_at=job.available_at
    )


def analysis_message(job):
    """Called with the work item locked. Never mutate a newer analysis run."""
    if job.kind != "analysis.analyze":
        return None
    from records.models import Message

    message_id = job.payload.get("message_id")
    if not message_id:
        return None
    message = Message.objects.select_for_update().filter(pk=message_id).first()
    if message is None:
        return None
    latest = WorkItem.objects.filter(kind__in=["analysis.analyze", "ingestion.parse"]).alias(
        message_key=KeyTextTransform("message_id", "payload")
    ).filter(message_key=message_id).order_by("-created_at", "-pk").values_list("pk", flat=True).first()
    return message if latest == job.pk else None


def sync_terminal_analysis(job):
    message = analysis_message(job)
    if message is not None and message.status == "PENDING":
        # Prior evidence may remain after a failed reanalysis. It is not proof
        # of the completeness of the latest run.
        message.status = "FAILED"
        message.error = job.error or "Cancelled"
        message.save(update_fields=["status", "error"])


def failed(job, error):
    now = timezone.now()
    Attempt.objects.filter(job=job, token=job.token, finished_at__isnull=True).update(
        finished_at=now, error=error
    )
    job.error = error
    job.token = None
    job.deadline = None
    if job.attempts >= job.max_attempts:
        job.status = WorkItem.Status.DEAD
        job.finished_at = now
        job.available_at = now
        dispatch(job, dead=True)
        sync_terminal_analysis(job)
    else:
        job.status = WorkItem.Status.PENDING
        job.available_at = now + timedelta(seconds=min(300, 2**job.attempts) + random.uniform(0, 1))
        dispatch(job)


@transaction.atomic
def claim(job_id, worker):
    job = WorkItem.objects.select_for_update().get(pk=job_id)
    now = timezone.now()
    if job.status != WorkItem.Status.PENDING or job.available_at > now:
        return None
    if job.attempts >= job.max_attempts:
        failed(job, "AttemptsExhausted")
        return None
    job.status = WorkItem.Status.RUNNING
    job.attempts += 1
    job.token = uuid.uuid4()
    job.started_at = now
    # Hard task timeout is enforced by prefork; grace covers process termination.
    job.deadline = now + timedelta(seconds=limits(job.queue)["hard"] + 30)
    job.save()
    number = (job.runs.aggregate(n=Max("number"))["n"] or 0) + 1
    Attempt.objects.create(job=job, number=number, token=job.token, worker=worker)
    return job


def locked_current(job_id, token):
    """Call inside an atomic block before committing any handler's DB effects."""
    job = WorkItem.objects.select_for_update().get(pk=job_id)
    if job.status != WorkItem.Status.RUNNING or job.token != token or job.deadline <= timezone.now():
        raise StaleAttempt("Attempt no longer owns this job")
    return job


@transaction.atomic
def finish(job_id, token, output):
    job = locked_current(job_id, token)
    now = timezone.now()
    job.status = WorkItem.Status.DONE
    job.finished_at = now
    job.deadline = None
    job.output = output
    job.error = ""
    job.save()
    Attempt.objects.filter(job=job, token=token).update(finished_at=now)


@transaction.atomic
def fail(job_id, token, error):
    try:
        job = locked_current(job_id, token)
    except StaleAttempt:
        return
    failed(job, error)


@transaction.atomic
def defer(job_id, token, error, retry_after=0):
    """Release ownership and durably delay dependency failures without burning budget."""
    try:
        job = locked_current(job_id, token)
    except StaleAttempt:
        return
    now = timezone.now()
    Attempt.objects.filter(job=job, token=token).update(finished_at=now, error=error[:160])
    job.attempts = max(0, job.attempts - 1)
    job.deferrals += 1
    ceiling = min(120, 5 * 2 ** min(job.deferrals, 5))
    delay = max(min(300, retry_after), random.uniform(ceiling / 2, ceiling))
    job.status, job.token, job.deadline = WorkItem.Status.PENDING, None, None
    job.error = error[:160]
    if (now - job.created_at).total_seconds() >= getattr(settings, 'MICE_PARSER_MAX_WAIT_SECONDS', 86400):
        # Dependency outage is not malformed mail. Stop automatic retries and
        # retain a manually retryable job without exhausting processing attempts.
        job.status = WorkItem.Status.CANCELLED
        job.finished_at = now
        job.error = (error[:130] + ' wait_budget_exceeded')[:160]
        job.save()
        sync_terminal_analysis(job)
        return
    job.available_at = now + timedelta(seconds=delay)
    dispatch(job)


@transaction.atomic
def reject(job_id, token, error):
    try:
        job = locked_current(job_id, token)
    except StaleAttempt:
        return
    job.max_attempts = max(1, job.attempts)
    failed(job, error[:160])


@transaction.atomic
def recover(limit=100):
    """Recovery emits delivery intents only; never executes domain handlers."""
    now = timezone.now()
    count = 0
    for job in (
        WorkItem.objects.select_for_update(skip_locked=True)
        .filter(status=WorkItem.Status.RUNNING, deadline__lt=now)
        .order_by("deadline")[:limit]
    ):
        failed(job, "WorkerDeadlineExceeded")
        count += 1
    # Re-deliver confirmed but never completed work after broker loss/DLQ routing.
    # Pending outbox rows (including delayed retries) are already owned by publisher.
    for job in (
        WorkItem.objects.select_for_update(skip_locked=True)
        .filter(status=WorkItem.Status.PENDING, available_at__lte=now)
        .order_by("created_at")[:limit]
    ):
        latest = job.dispatches.filter(generation=job.generation, dead_letter=False).first()
        if latest and latest.published_at and latest.published_at < now - timedelta(minutes=5):
            dispatch(job)
            count += 1
    return count


@transaction.atomic
def cancel(job_id):
    job = WorkItem.objects.select_for_update().get(pk=job_id)
    if job.status in {WorkItem.Status.DONE, WorkItem.Status.DEAD, WorkItem.Status.CANCELLED}:
        return job
    Attempt.objects.filter(job=job, token=job.token, finished_at__isnull=True).update(
        finished_at=timezone.now(), error="Cancelled"
    )
    job.status = WorkItem.Status.CANCELLED
    job.error = "Cancelled"
    job.token = None
    job.deadline = None
    job.finished_at = timezone.now()
    job.save()
    sync_terminal_analysis(job)
    return job


@transaction.atomic
def retry(job_id):
    job = WorkItem.objects.select_for_update().get(pk=job_id)
    if job.status not in {WorkItem.Status.DEAD, WorkItem.Status.CANCELLED}:
        raise ValueError("Only dead or cancelled jobs may be retried")
    if job.kind == "analysis.analyze":
        message = analysis_message(job)
        if message is None:
            raise ValueError("Analysis has been superseded or message removed")
        if WorkItem.objects.filter(payload__message_id=message.pk, status__in=["PENDING", "RUNNING"]).exists():
            raise ValueError("Message already processing")
        message.status, message.error = "PENDING", None
        message.save(update_fields=["status", "error"])
    job.max_attempts += 5
    job.status = WorkItem.Status.PENDING
    job.finished_at = None
    job.available_at = timezone.now()
    dispatch(job)
    return job
