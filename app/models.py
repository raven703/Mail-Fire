import uuid
from datetime import UTC, datetime

from sqlalchemy import ForeignKey, Index, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def now():
    return datetime.now(UTC)


class IDMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime] = mapped_column(default=now, index=True)


class Blob(Base):
    __tablename__ = "blobs"
    sha: Mapped[str] = mapped_column(String(64), primary_key=True)
    data: Mapped[bytes] = mapped_column(LargeBinary)
    size: Mapped[int]


class Content(IDMixin, Base):
    __tablename__ = "contents"
    normalized_sha: Mapped[str] = mapped_column(String(64), unique=True)
    text: Mapped[str] = mapped_column(Text)
    analysis: Mapped[dict] = mapped_column(JSONB, default=dict)
    version: Mapped[str] = mapped_column(default="1")


class Message(IDMixin, Base):
    __tablename__ = "messages"
    original_sha: Mapped[str] = mapped_column(ForeignKey("blobs.sha"), unique=True)
    format: Mapped[str]
    subject: Mapped[str] = mapped_column(Text, default="")
    sender: Mapped[str] = mapped_column(default="")
    recipients: Mapped[list] = mapped_column(JSONB, default=list)
    headers: Mapped[dict] = mapped_column(JSONB, default=dict)
    content_id: Mapped[str | None] = mapped_column(ForeignKey("contents.id"))
    status: Mapped[str] = mapped_column(default="PENDING", index=True)
    error: Mapped[str | None] = mapped_column(Text)
    legal_hold: Mapped[bool] = mapped_column(default=False)


class MailEvent(IDMixin, Base):
    __tablename__ = "mail_events"
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id"), index=True)
    source: Mapped[str]
    source_key: Mapped[str] = mapped_column(Text, unique=True)
    direction: Mapped[str] = mapped_column(default="UNKNOWN")
    envelope: Mapped[dict] = mapped_column(JSONB, default=dict)


class Address(IDMixin, Base):
    __tablename__ = "addresses"
    email: Mapped[str] = mapped_column(unique=True)
    identity_id: Mapped[str | None] = mapped_column(ForeignKey("identities.id"))
    kind: Mapped[str] = mapped_column(default="unknown")


class Identity(IDMixin, Base):
    __tablename__ = "identities"
    name: Mapped[str]
    department: Mapped[str] = mapped_column(default="")


class Attachment(IDMixin, Base):
    __tablename__ = "attachments"
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id"), index=True)
    blob_sha: Mapped[str] = mapped_column(ForeignKey("blobs.sha"))
    name: Mapped[str] = mapped_column(Text)
    mime: Mapped[str]
    status: Mapped[str]
    text: Mapped[str] = mapped_column(Text, default="")
    details: Mapped[dict] = mapped_column(JSONB, default=dict)


class Job(IDMixin, Base):
    __tablename__ = "jobs"
    kind: Mapped[str] = mapped_column(index=True)
    payload: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(default="PENDING", index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    priority: Mapped[int] = mapped_column(default=10)
    available_at: Mapped[datetime] = mapped_column(default=now)
    lease_until: Mapped[datetime | None]
    owner: Mapped[str | None]
    error: Mapped[str | None] = mapped_column(Text)
    finished_at: Mapped[datetime | None]
    __table_args__ = (Index("jobs_claim", "status", "available_at", "priority"),)


class ImportRecord(IDMixin, Base):
    __tablename__ = "imports"
    source_key: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    status: Mapped[str]
    message_id: Mapped[str | None] = mapped_column(ForeignKey("messages.id"))
    error: Mapped[str | None] = mapped_column(Text)
    duplicate: Mapped[bool] = mapped_column(default=False)


class Policy(IDMixin, Base):
    __tablename__ = "policies"
    name: Mapped[str]
    enabled: Mapped[bool] = mapped_column(default=True)
    shadow: Mapped[bool] = mapped_column(default=False)
    version: Mapped[int] = mapped_column(default=1)
    priority: Mapped[int] = mapped_column(default=10)
    conditions: Mapped[dict] = mapped_column(JSONB)


class Incident(IDMixin, Base):
    __tablename__ = "incidents"
    event_id: Mapped[str] = mapped_column(ForeignKey("mail_events.id"))
    policy_id: Mapped[str] = mapped_column(ForeignKey("policies.id"))
    status: Mapped[str] = mapped_column(default="NEW")
    risk: Mapped[int] = mapped_column(default=0)
    findings: Mapped[list] = mapped_column(JSONB)
    assignee: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"))
    __table_args__ = (UniqueConstraint("event_id", "policy_id"),)


class Comment(IDMixin, Base):
    __tablename__ = "comments"
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"))
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    text: Mapped[str] = mapped_column(Text)


class Account(IDMixin, Base):
    __tablename__ = "accounts"
    username: Mapped[str] = mapped_column(unique=True)
    password_hash: Mapped[str]
    role: Mapped[str]
    originals: Mapped[bool] = mapped_column(default=False)
    enabled: Mapped[bool] = mapped_column(default=True)


class LoginSession(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    expires_at: Mapped[datetime]


class Audit(IDMixin, Base):
    __tablename__ = "audit"
    actor: Mapped[str]
    action: Mapped[str]
    target: Mapped[str]
    details: Mapped[dict] = mapped_column(JSONB, default=dict)


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB)


class Diagnostic(IDMixin, Base):
    __tablename__ = "diagnostics"
    service: Mapped[str]
    level: Mapped[str]
    event: Mapped[str]
    details: Mapped[dict] = mapped_column(JSONB, default=dict)


class Metric(IDMixin, Base):
    __tablename__ = "metrics"
    service: Mapped[str]
    values: Mapped[dict] = mapped_column(JSONB)


class Reference(IDMixin, Base):
    __tablename__ = "references"
    name: Mapped[str]
    blob_sha: Mapped[str] = mapped_column(ForeignKey("blobs.sha"))
    text: Mapped[str] = mapped_column(Text)
    fingerprint: Mapped[dict] = mapped_column(JSONB)


class Category(Base):
    __tablename__ = "categories"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    group_name: Mapped[str] = mapped_column(String(120), default="Другое")
    description: Mapped[str] = mapped_column(Text, default="")
    mode: Mapped[str] = mapped_column(String(24), default="ml")
    match_mode: Mapped[str] = mapped_column(String(8), default="any")
    active: Mapped[bool] = mapped_column(default=True)
    keywords: Mapped[list] = mapped_column(JSONB, default=list)
    reference_id: Mapped[str | None] = mapped_column(
        ForeignKey("references.id", ondelete="SET NULL"), nullable=True
    )


class CategoryRule(IDMixin, Base):
    __tablename__ = "category_rules"
    category_id: Mapped[str] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(24))
    title: Mapped[str] = mapped_column(String(160), default="")
    enabled: Mapped[bool] = mapped_column(default=True)
    risk: Mapped[int] = mapped_column(default=70)
    priority: Mapped[int] = mapped_column(default=100)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)


class MLDataset(IDMixin, Base):
    __tablename__ = "ml_datasets"
    name: Mapped[str] = mapped_column(String(160))
    source: Mapped[str] = mapped_column(String(120), default="external-llm")
    description: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    fingerprint: Mapped[str] = mapped_column(String(64), default="")
    example_count: Mapped[int] = mapped_column(default=0)


class TrainingExample(IDMixin, Base):
    __tablename__ = "training_examples"
    dataset_id: Mapped[str | None] = mapped_column(
        ForeignKey("ml_datasets.id", ondelete="SET NULL"), index=True, nullable=True
    )
    source: Mapped[str] = mapped_column(String(80), default="manual")
    reviewed_by: Mapped[str | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    source_incident_id: Mapped[str | None] = mapped_column(
        ForeignKey("incidents.id", ondelete="SET NULL"), unique=True, nullable=True
    )
    text: Mapped[str] = mapped_column(Text)
    group_sha: Mapped[str] = mapped_column(String(64), index=True)
    labels: Mapped[list] = mapped_column(JSONB)
    approved: Mapped[bool] = mapped_column(default=False)


class MLModel(IDMixin, Base):
    __tablename__ = "ml_models"
    engine: Mapped[str] = mapped_column(String(24), default="tfidf")
    category_id: Mapped[str | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), index=True, nullable=True
    )
    dataset_id: Mapped[str | None] = mapped_column(
        ForeignKey("ml_datasets.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str]
    artifact: Mapped[bytes] = mapped_column(LargeBinary)
    metrics: Mapped[dict] = mapped_column(JSONB)
    active: Mapped[bool] = mapped_column(default=False)
    eligible: Mapped[bool] = mapped_column(default=False)


class Outbox(IDMixin, Base):
    __tablename__ = "outbox"
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"))
    destination: Mapped[str]
    payload: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(default="PENDING")
    attempts: Mapped[int] = mapped_column(default=0)
    available_at: Mapped[datetime] = mapped_column(default=now)
    error: Mapped[str | None]
