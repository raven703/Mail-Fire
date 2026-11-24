"""At-least-once dispatch: confirm first, then commit the outbox marker."""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from kombu import Exchange, Producer

from mice.celery import app
from pipeline.config import limits
from pipeline.models import Dispatch, WorkItem


def declare_topology(connection):
    channel = connection.channel()
    try:
        for queue in app.conf.task_queues:
            queue(channel).declare()
    finally:
        channel.close()


@transaction.atomic
def publish_one(connection):
    row = (
        Dispatch.objects.select_for_update(skip_locked=True, of=("self",))
        .select_related("job")
        .filter(published_at__isnull=True, available_at__lte=timezone.now())
        .order_by("available_at")
        .first()
    )
    if not row:
        return False
    job = row.job
    row.attempts += 1
    if not row.dead_letter and job.status in {
        WorkItem.Status.DONE,
        WorkItem.Status.CANCELLED,
        WorkItem.Status.DEAD,
    }:
        row.published_at = timezone.now()
        row.save()
        return True
    try:
        producer = Producer(connection)
        if row.dead_letter:
            # An audit/dead-letter event, never consumed as executable work.
            producer.publish(
                {"job_id": str(job.pk)},
                exchange=Exchange("mice.dead", "direct", durable=True),
                routing_key=job.queue,
                serializer="json",
                delivery_mode=2,
                retry=False,
            )
        else:
            bound = limits(job.queue)
            app.send_task(
                "pipeline.execute",
                args=[str(job.pk)],
                queue=job.queue,
                routing_key=job.queue,
                producer=producer,
                task_id=str(row.pk),
                retry=False,
                time_limit=bound["hard"],
                soft_time_limit=bound["soft"],
            )
        row.published_at = timezone.now()
        row.error = ""
    except Exception as exc:
        row.error = type(exc).__name__
        row.available_at = timezone.now() + timedelta(seconds=min(60, 2 ** min(row.attempts, 6)))
        row.save()
        # Returning commits backoff; raising inside atomic would roll it back.
        return False
    row.save()
    return True
