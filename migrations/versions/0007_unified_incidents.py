"""One incident per unique message, with immutable policy hit snapshots.

Existing incidents are merged before enforcing unique message_id. Merging keeps
comments, training examples, outbox records and review workflow of the earliest
incident. Take a DB backup before applying this migration to production.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
import json

revision = "0007"
down_revision = "0006"


def upgrade():
    op.add_column("policies", sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("incidents", sa.Column("message_id", sa.String(36), nullable=True))
    op.add_column("incidents", sa.Column("policy_hits", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")))
    op.alter_column("incidents", "policy_id", existing_type=sa.String(36), nullable=True)
    conn = op.get_bind()
    records = conn.execute(sa.text("""
        SELECT i.id, i.event_id, e.message_id, i.policy_id, i.risk, i.findings,
               i.status, i.assignee, i.created_at, p.name, p.version, p.conditions
        FROM incidents i JOIN mail_events e ON e.id=i.event_id
        LEFT JOIN policies p ON p.id=i.policy_id
        ORDER BY e.message_id, i.created_at, i.id
    """)).mappings().all()
    grouped = {}
    for row in records:
        grouped.setdefault(row["message_id"], []).append(row)
    for mid, group in grouped.items():
        winner = group[0]
        hits = []
        findings = []
        risk = 0
        for row in group:
            hits.append({"policy_id": row["policy_id"], "name": row["name"] or "Удалённая политика",
                         "version": row["version"], "conditions": row["conditions"] or {},
                         "risk": row["risk"], "findings": row["findings"] or []})
            risk = max(risk, row["risk"])
            for f in row["findings"] or []:
                if f not in findings:
                    findings.append(f)
        conn.execute(sa.text("""
            UPDATE incidents SET message_id=:mid, policy_hits=CAST(:hits AS jsonb),
            findings=CAST(:findings AS jsonb), risk=:risk WHERE id=:id
        """), {"mid":mid,"hits":json.dumps(hits,ensure_ascii=False),
                "findings":json.dumps(findings,ensure_ascii=False),"risk":risk,"id":winner["id"]})
        for old in group[1:]:
            conn.execute(sa.text("UPDATE comments SET incident_id=:win WHERE incident_id=:old"),{"win":winner["id"],"old":old["id"]})
            # Training examples preserve labels; only one can reference the winner.
            occupied = conn.execute(sa.text("SELECT 1 FROM training_examples WHERE source_incident_id=:id"),{"id":winner["id"]}).first()
            if occupied:
                conn.execute(sa.text("UPDATE training_examples SET source_incident_id=NULL WHERE source_incident_id=:old"),{"old":old["id"]})
            else:
                conn.execute(sa.text("UPDATE training_examples SET source_incident_id=:win WHERE source_incident_id=:old"),{"win":winner["id"],"old":old["id"]})
            conn.execute(sa.text("UPDATE outbox SET incident_id=:win WHERE incident_id=:old"),{"win":winner["id"],"old":old["id"]})
            conn.execute(sa.text("UPDATE audit SET target=:win WHERE target=:old"),{"win":winner["id"],"old":old["id"]})
            conn.execute(sa.text("DELETE FROM incidents WHERE id=:old"),{"old":old["id"]})
    op.alter_column("incidents", "message_id", existing_type=sa.String(36), nullable=False)
    op.create_foreign_key("fk_incident_message", "incidents", "messages", ["message_id"], ["id"])
    op.create_index("ix_incidents_message_id", "incidents", ["message_id"], unique=True)


def downgrade():
    raise RuntimeError("Downgrade blocked: reverting aggregated incidents would lose provenance")
