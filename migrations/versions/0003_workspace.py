"""Search indexes for analyst workspace; preserve all application data."""

from alembic import op

revision = "0003"
down_revision = "0002"


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    for table, column in [
        ("messages", "subject"),
        ("messages", "sender"),
        ("contents", "text"),
        ("attachments", "name"),
    ]:
        op.execute(f"CREATE INDEX ix_{table}_{column}_trgm ON {table} USING gin ({column} gin_trgm_ops)")
    op.execute(
        "CREATE INDEX ix_messages_recipients_trgm ON messages USING gin ((recipients::varchar) gin_trgm_ops)"
    )
    op.execute("CREATE INDEX ix_incidents_event_risk ON incidents(event_id, risk)")
    op.execute("CREATE INDEX ix_incidents_status_created ON incidents(status, created_at)")
    op.execute("CREATE INDEX ix_mail_events_message_source ON mail_events(message_id, source, direction)")


def downgrade():
    for name in [
        "ix_messages_subject_trgm",
        "ix_messages_sender_trgm",
        "ix_contents_text_trgm",
        "ix_attachments_name_trgm",
        "ix_messages_recipients_trgm",
        "ix_incidents_event_risk",
        "ix_incidents_status_created",
        "ix_mail_events_message_source",
    ]:
        op.execute(f"DROP INDEX {name}")
