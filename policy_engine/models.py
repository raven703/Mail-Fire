import uuid

from django.db import models
from django.utils import timezone


class AnalysisRevision(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey("records.Message", on_delete=models.PROTECT)
    fingerprint = models.CharField(max_length=64)
    detector_version = models.CharField(max_length=160)
    message_status = models.CharField(max_length=24)
    results = models.JSONField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "mice_analysis_revisions"
        constraints = [
            models.UniqueConstraint(fields=["message", "fingerprint"], name="analysis_revision_unique")
        ]


class PolicyRevision(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Historical snapshots must outlive policy deletion.
    policy_id = models.CharField(max_length=36)
    version = models.PositiveIntegerField()
    fingerprint = models.CharField(max_length=64)
    snapshot = models.JSONField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "mice_policy_revisions"
        constraints = [
            models.UniqueConstraint(
                fields=["policy_id", "version", "fingerprint"], name="policy_revision_unique"
            )
        ]


class Evaluation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.OneToOneField("pipeline.WorkItem", on_delete=models.PROTECT)
    analysis = models.ForeignKey(AnalysisRevision, on_delete=models.PROTECT)
    policy_revisions = models.JSONField()
    policy_snapshot = models.JSONField()
    settings_snapshot = models.JSONField()
    hits = models.JSONField(default=list)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "mice_policy_evaluations"
