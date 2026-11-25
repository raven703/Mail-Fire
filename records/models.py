"""Django mappings of the frozen legacy schema; IDs and columns are preserved."""

import uuid

from django.db import models
from django.utils import timezone
from pgvector.django import VectorField


def record_id():
    return str(uuid.uuid4())


class SemanticChunk(models.Model):
    source_type = models.TextField()
    source_id = models.CharField(max_length=36)
    chunk_index = models.IntegerField()
    text = models.TextField()
    model = models.TextField()
    embedding = VectorField(dimensions=384)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "semantic_chunks"
        unique_together = [("source_type", "source_id", "chunk_index", "model")]


class Account(models.Model):
    username = models.CharField(unique=True)
    password_hash = models.CharField()
    role = models.CharField()
    originals = models.BooleanField(default=False)
    enabled = models.BooleanField(default=True)
    id = models.CharField(max_length=36, primary_key=True, default=record_id)
    created_at = models.DateTimeField(db_index=True, default=timezone.now)

    class Meta:
        db_table = "accounts"


class Audit(models.Model):
    actor = models.CharField()
    action = models.CharField()
    target = models.CharField()
    details = models.JSONField(default=dict)
    id = models.CharField(max_length=36, primary_key=True, default=record_id)
    created_at = models.DateTimeField(db_index=True, default=timezone.now)

    class Meta:
        db_table = "audit"


class Blob(models.Model):
    sha = models.CharField(max_length=64, primary_key=True)
    data = models.BinaryField()
    size = models.IntegerField()

    class Meta:
        db_table = "blobs"


class Content(models.Model):
    normalized_sha = models.CharField(max_length=64, unique=True)
    text = models.TextField()
    analysis = models.JSONField(default=dict)
    version = models.CharField(default="1")
    id = models.CharField(max_length=36, primary_key=True, default=record_id)
    created_at = models.DateTimeField(db_index=True, default=timezone.now)

    class Meta:
        db_table = "contents"


class Diagnostic(models.Model):
    service = models.CharField()
    level = models.CharField()
    event = models.CharField()
    details = models.JSONField(default=dict)
    id = models.CharField(max_length=36, primary_key=True, default=record_id)
    created_at = models.DateTimeField(db_index=True, default=timezone.now)

    class Meta:
        db_table = "diagnostics"


class Identity(models.Model):
    name = models.CharField()
    department = models.CharField(default="")
    id = models.CharField(max_length=36, primary_key=True, default=record_id)
    created_at = models.DateTimeField(db_index=True, default=timezone.now)

    class Meta:
        db_table = "identities"


class Job(models.Model):
    kind = models.CharField(db_index=True)
    payload = models.JSONField()
    status = models.CharField(db_index=True, default="PENDING")
    attempts = models.IntegerField(default=0)
    priority = models.IntegerField(default=10)
    available_at = models.DateTimeField(default=timezone.now)
    lease_until = models.DateTimeField(null=True)
    owner = models.CharField(null=True)
    error = models.TextField(null=True)
    finished_at = models.DateTimeField(null=True)
    id = models.CharField(max_length=36, primary_key=True, default=record_id)
    created_at = models.DateTimeField(db_index=True, default=timezone.now)

    class Meta:
        db_table = "jobs"


class Metric(models.Model):
    service = models.CharField()
    values = models.JSONField()
    id = models.CharField(max_length=36, primary_key=True, default=record_id)
    created_at = models.DateTimeField(db_index=True, default=timezone.now)

    class Meta:
        db_table = "metrics"
        indexes = [models.Index(fields=["service", "-created_at"], name="metrics_service_created_idx")]


class MLDataset(models.Model):
    name = models.CharField(max_length=160)
    source = models.CharField(max_length=120, default="external-llm")
    description = models.TextField(default="")
    version = models.IntegerField(default=1)
    status = models.CharField(max_length=20, default="DRAFT")
    fingerprint = models.CharField(max_length=64, default="")
    example_count = models.IntegerField(default=0)
    id = models.CharField(max_length=36, primary_key=True, default=record_id)
    created_at = models.DateTimeField(db_index=True, default=timezone.now)

    class Meta:
        db_table = "ml_datasets"


class Policy(models.Model):
    name = models.CharField()
    enabled = models.BooleanField(default=True)
    shadow = models.BooleanField(default=False)
    version = models.IntegerField(default=1)
    priority = models.IntegerField(default=10)
    conditions = models.JSONField()
    archived = models.BooleanField(default=False)
    id = models.CharField(max_length=36, primary_key=True, default=record_id)
    created_at = models.DateTimeField(db_index=True, default=timezone.now)

    class Meta:
        db_table = "policies"


class Setting(models.Model):
    key = models.CharField(primary_key=True)
    value = models.JSONField()

    class Meta:
        db_table = "settings"


class Address(models.Model):
    email = models.CharField(unique=True)
    identity = models.ForeignKey(
        "Identity", on_delete=models.PROTECT, db_column="identity_id", related_name="+", null=True
    )
    kind = models.CharField(default="unknown")
    id = models.CharField(max_length=36, primary_key=True, default=record_id)
    created_at = models.DateTimeField(db_index=True, default=timezone.now)

    class Meta:
        db_table = "addresses"


class Message(models.Model):
    original_sha_ref = models.OneToOneField(
        "Blob", on_delete=models.PROTECT, to_field="sha", db_column="original_sha", related_name="+"
    )
    format = models.CharField()
    subject = models.TextField(default="")
    sender = models.CharField(default="")
    recipients = models.JSONField(default=list)
    headers = models.JSONField(default=dict)
    content = models.ForeignKey(
        "Content", on_delete=models.PROTECT, db_column="content_id", related_name="+", null=True
    )
    status = models.CharField(db_index=True, default="PENDING")
    error = models.TextField(null=True)
    legal_hold = models.BooleanField(default=False)
    id = models.CharField(max_length=36, primary_key=True, default=record_id)
    created_at = models.DateTimeField(db_index=True, default=timezone.now)

    class Meta:
        db_table = "messages"


class Reference(models.Model):
    name = models.CharField()
    blob_sha_ref = models.ForeignKey(
        "Blob", on_delete=models.PROTECT, to_field="sha", db_column="blob_sha", related_name="+"
    )
    text = models.TextField()
    fingerprint = models.JSONField()
    id = models.CharField(max_length=36, primary_key=True, default=record_id)
    created_at = models.DateTimeField(db_index=True, default=timezone.now)

    class Meta:
        db_table = "references"


class LoginSession(models.Model):
    token_hash = models.CharField(max_length=64, primary_key=True)
    account = models.ForeignKey("Account", on_delete=models.PROTECT, db_column="account_id", related_name="+")
    expires_at = models.DateTimeField()

    class Meta:
        db_table = "sessions"


class Attachment(models.Model):
    message = models.ForeignKey("Message", on_delete=models.PROTECT, db_column="message_id", related_name="+")
    blob_sha_ref = models.ForeignKey(
        "Blob", on_delete=models.PROTECT, to_field="sha", db_column="blob_sha", related_name="+"
    )
    name = models.TextField()
    mime = models.CharField()
    status = models.CharField()
    text = models.TextField(default="")
    details = models.JSONField(default=dict)
    id = models.CharField(max_length=36, primary_key=True, default=record_id)
    created_at = models.DateTimeField(db_index=True, default=timezone.now)

    class Meta:
        db_table = "attachments"


class Category(models.Model):
    id = models.CharField(max_length=64, primary_key=True)
    name = models.CharField(max_length=160, unique=True)
    group_name = models.CharField(max_length=120, default="Другое")
    description = models.TextField(default="")
    mode = models.CharField(max_length=24, default="ml")
    match_mode = models.CharField(max_length=8, default="any")
    active = models.BooleanField(default=True)
    keywords = models.JSONField(default=list)
    reference = models.ForeignKey(
        "Reference", on_delete=models.SET_NULL, db_column="reference_id", related_name="+", null=True
    )

    class Meta:
        db_table = "categories"


class ImportRecord(models.Model):
    source_key = models.TextField(unique=True)
    name = models.TextField()
    status = models.CharField()
    message = models.ForeignKey(
        "Message", on_delete=models.PROTECT, db_column="message_id", related_name="+", null=True
    )
    error = models.TextField(null=True)
    duplicate = models.BooleanField(default=False)
    id = models.CharField(max_length=36, primary_key=True, default=record_id)
    created_at = models.DateTimeField(db_index=True, default=timezone.now)

    class Meta:
        db_table = "imports"


class MailEvent(models.Model):
    message = models.ForeignKey("Message", on_delete=models.PROTECT, db_column="message_id", related_name="+")
    source = models.CharField()
    source_key = models.TextField(unique=True)
    direction = models.CharField(default="UNKNOWN")
    envelope = models.JSONField(default=dict)
    id = models.CharField(max_length=36, primary_key=True, default=record_id)
    created_at = models.DateTimeField(db_index=True, default=timezone.now)

    class Meta:
        db_table = "mail_events"


class LiveRuleManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class CategoryRule(models.Model):
    objects = LiveRuleManager()
    all_objects = models.Manager()
    deleted_at = models.DateTimeField(null=True, blank=True, editable=False, db_index=True)
    category = models.ForeignKey(
        "Category", on_delete=models.CASCADE, db_column="category_id", related_name="+"
    )
    kind = models.CharField(max_length=24)
    title = models.CharField(max_length=160, default="")
    enabled = models.BooleanField(default=True)
    risk = models.IntegerField(default=70)
    priority = models.IntegerField(default=100)
    config = models.JSONField(default=dict)
    id = models.CharField(max_length=36, primary_key=True, default=record_id)
    created_at = models.DateTimeField(db_index=True, default=timezone.now)

    class Meta:
        db_table = "category_rules"


class Incident(models.Model):
    event = models.ForeignKey("MailEvent", on_delete=models.PROTECT, db_column="event_id", related_name="+")
    message = models.OneToOneField(
        "Message", on_delete=models.PROTECT, db_column="message_id", related_name="+"
    )
    policy = models.ForeignKey(
        "Policy", on_delete=models.PROTECT, db_column="policy_id", related_name="+", null=True
    )
    policy_hits = models.JSONField(default=list)
    status = models.CharField(default="NEW")
    risk = models.IntegerField(default=0)
    findings = models.JSONField()
    assignee_ref = models.ForeignKey(
        "Account", on_delete=models.PROTECT, db_column="assignee", related_name="+", null=True
    )
    id = models.CharField(max_length=36, primary_key=True, default=record_id)
    created_at = models.DateTimeField(db_index=True, default=timezone.now)

    class Meta:
        db_table = "incidents"


class InferenceArtifact(models.Model):
    """Content-addressed immutable copies, independent of model publication rows."""

    sha256 = models.CharField(max_length=64, primary_key=True)
    data = models.BinaryField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "inference_artifacts"


class MLModel(models.Model):
    engine = models.CharField(max_length=24, default="tfidf")
    category = models.ForeignKey(
        "Category", on_delete=models.SET_NULL, db_column="category_id", related_name="+", null=True
    )
    dataset = models.ForeignKey(
        "MLDataset", on_delete=models.SET_NULL, db_column="dataset_id", related_name="+", null=True
    )
    name = models.CharField()
    artifact = models.BinaryField()
    metrics = models.JSONField()
    active = models.BooleanField(default=False)
    eligible = models.BooleanField(default=False)
    id = models.CharField(max_length=36, primary_key=True, default=record_id)
    created_at = models.DateTimeField(db_index=True, default=timezone.now)

    class Meta:
        db_table = "ml_models"


class Comment(models.Model):
    incident = models.ForeignKey(
        "Incident", on_delete=models.PROTECT, db_column="incident_id", related_name="+"
    )
    account = models.ForeignKey("Account", on_delete=models.PROTECT, db_column="account_id", related_name="+")
    text = models.TextField()
    id = models.CharField(max_length=36, primary_key=True, default=record_id)
    created_at = models.DateTimeField(db_index=True, default=timezone.now)

    class Meta:
        db_table = "comments"


class Outbox(models.Model):
    incident = models.ForeignKey(
        "Incident", on_delete=models.PROTECT, db_column="incident_id", related_name="+"
    )
    destination = models.CharField()
    payload = models.JSONField()
    status = models.CharField(default="PENDING")
    attempts = models.IntegerField(default=0)
    available_at = models.DateTimeField(default=timezone.now)
    error = models.CharField(null=True)
    id = models.CharField(max_length=36, primary_key=True, default=record_id)
    created_at = models.DateTimeField(db_index=True, default=timezone.now)

    class Meta:
        db_table = "outbox"


class OCRTestDocument(models.Model):
    id = models.CharField(max_length=36, primary_key=True, default=record_id)
    owner = models.CharField(max_length=36, db_index=True)
    data = models.BinaryField()
    name = models.CharField(max_length=40)
    expires_at = models.DateTimeField(db_index=True)


class TrainingExample(models.Model):
    dataset = models.ForeignKey(
        "MLDataset", on_delete=models.SET_NULL, db_column="dataset_id", related_name="+", null=True
    )
    source = models.CharField(max_length=80, default="manual")
    reviewed_by_ref = models.ForeignKey(
        "Account", on_delete=models.SET_NULL, db_column="reviewed_by", related_name="+", null=True
    )
    source_incident = models.OneToOneField(
        "Incident", on_delete=models.SET_NULL, db_column="source_incident_id", related_name="+", null=True
    )
    text = models.TextField()
    group_sha = models.CharField(max_length=64, db_index=True)
    labels = models.JSONField()
    approved = models.BooleanField(default=False)
    id = models.CharField(max_length=36, primary_key=True, default=record_id)
    created_at = models.DateTimeField(db_index=True, default=timezone.now)

    class Meta:
        db_table = "training_examples"
