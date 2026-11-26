from datetime import timedelta

from celery.exceptions import Reject
from django.db import OperationalError, transaction
from django.utils import timezone

from mice.celery import app
from pipeline.handlers import handlers
from pipeline.models import PeriodicSchedule, WorkItem
from pipeline.services import StaleAttempt, claim, enqueue, fail, defer, reject
from pipeline.parser_errors import ParserUnavailable, ParserRejected


@app.task(name="pipeline.purge_ocr_tests", ignore_result=True, soft_time_limit=15, time_limit=20)
def purge_ocr_tests():
    from records.ocr_settings import purge
    purge()


@app.task(bind=True, name="pipeline.execute", ignore_result=True)
def execute(self, job_id):
    job = None
    try:
        job = claim(job_id, self.request.hostname or "unknown")
        if job is None:
            return
        queue, handler = handlers[job.kind]
        if queue != job.queue:
            raise ValueError("Handler queue mismatch")
        handler(job)
        # A handler must commit effects and completion atomically, never return
        # implicitly successful work after losing its ownership token.
        if WorkItem.objects.filter(pk=job.pk, token=job.token, status=WorkItem.Status.RUNNING).exists():
            raise RuntimeError("Handler did not commit completion")
    except StaleAttempt:
        return
    except WorkItem.DoesNotExist:
        raise Reject("Unknown job identifier", requeue=False) from None
    except OperationalError as exc:
        raise Reject(type(exc).__name__, requeue=True) from exc
    except (ParserUnavailable, ParserRejected) as exc:
        if job is None:
            raise Reject("Parser failure without ownership", requeue=False) from None
        try:
            if isinstance(exc, ParserUnavailable):
                defer(job.pk, job.token, str(exc), exc.retry_after)
            elif job.kind == "analysis.analyze" and exc.reason in {"sandbox_timeout", "sandbox_failed"}:
                # A per-request failure is bounded by normal attempt limits,
                # not the dependency-outage deferral budget.
                fail(job.pk, job.token, str(exc))
            else:
                reject(job.pk, job.token, str(exc))
        except OperationalError as db_error:
            raise Reject(type(db_error).__name__, requeue=True) from db_error
    except Exception as exc:
        if job is None:
            raise Reject(type(exc).__name__, requeue=False) from exc
        try:
            fail(job.pk, job.token, type(exc).__name__)
        except OperationalError as db_error:
            raise Reject(type(db_error).__name__, requeue=True) from db_error


@app.task(name="pipeline.periodic", ignore_result=True, soft_time_limit=15, time_limit=20)
def periodic(schedule_id):
    # Beat publishes the schedule identifier only. Payloads live in PostgreSQL.
    with transaction.atomic():
        schedule = PeriodicSchedule.objects.select_for_update().get(pk=schedule_id)
        now = timezone.now()
        if not schedule.enabled or schedule.next_due > now:
            return
        enqueue(schedule.kind, {}, f"periodic:{schedule.pk}:{schedule.next_due.isoformat()}")
        schedule.next_due = now + timedelta(seconds=schedule.interval_seconds)
        schedule.save(update_fields=["next_due"])
