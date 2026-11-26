import uuid

from django.db import models
from django.db.models.fields.json import KeyTextTransform
from django.utils import timezone

from pipeline.config import GROUPS


class WorkItem(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING"
        RUNNING = "RUNNING"
        DONE = "DONE"
        DEAD = "DEAD"
        CANCELLED = "CANCELLED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    deduplication_key = models.CharField(max_length=255, unique=True)
    kind = models.CharField(max_length=80)
    queue = models.CharField(max_length=24, choices=[(g, g) for g in GROUPS])
    # Payload stays in PostgreSQL. Broker messages carry the ID only.
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveIntegerField(default=0)
    deferrals = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=5)
    generation = models.PositiveIntegerField(default=0)
    token = models.UUIDField(null=True)
    created_at = models.DateTimeField(default=timezone.now)
    available_at = models.DateTimeField(default=timezone.now)
    started_at = models.DateTimeField(null=True)
    deadline = models.DateTimeField(null=True)
    finished_at = models.DateTimeField(null=True)
    error = models.CharField(max_length=160, blank=True)
    output = models.JSONField(default=dict)

    class Meta:
        db_table = "mice_work_items"
        indexes = [
            models.Index(fields=["status", "deadline"]),
            models.Index(fields=["queue", "status", "created_at"]),
            models.Index(KeyTextTransform("message_id", "payload"), models.F("created_at").desc(), models.F("id").desc(),
                         name="work_message_analysis_idx", condition=models.Q(kind__in=["analysis.analyze", "ingestion.parse"])),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(max_attempts__gte=1), name="work_attempts_positive")
        ]


class Dispatch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(WorkItem, on_delete=models.CASCADE, related_name="dispatches")
    generation = models.PositiveIntegerField()
    dead_letter = models.BooleanField(default=False)
    available_at = models.DateTimeField(default=timezone.now)
    published_at = models.DateTimeField(null=True)
    attempts = models.PositiveIntegerField(default=0)
    error = models.CharField(max_length=160, blank=True)

    class Meta:
        db_table = "mice_dispatch_outbox"
        constraints = [
            models.UniqueConstraint(
                fields=["job", "generation", "dead_letter"], name="dispatch_generation_unique"
            )
        ]
        indexes = [models.Index(fields=["published_at", "available_at"])]


class Attempt(models.Model):
    job = models.ForeignKey(WorkItem, on_delete=models.CASCADE, related_name="runs")
    number = models.PositiveIntegerField()
    token = models.UUIDField(unique=True)
    worker = models.CharField(max_length=255)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True)
    error = models.CharField(max_length=160, blank=True)

    class Meta:
        db_table = "mice_job_attempts"
        constraints = [models.UniqueConstraint(fields=["job", "number"], name="attempt_number_unique")]


class PeriodicSchedule(models.Model):
    id = models.UUIDField(primary_key=True)
    kind = models.CharField(max_length=80)
    interval_seconds = models.PositiveIntegerField()
    next_due = models.DateTimeField(default=timezone.now)
    enabled = models.BooleanField(default=True)

    class Meta:
        db_table = "mice_periodic_schedules"
