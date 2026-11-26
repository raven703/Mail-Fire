"""Reconcile historical unified failures and index the latest analysis lookup."""
from django.db import migrations, models
from django.db.models.fields.json import KeyTextTransform


def reconcile(apps, schema_editor):
    # Upgrade with workers drained. Never modify completed or newer legacy runs.
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("""
            UPDATE messages AS m SET status = 'FAILED', error = COALESCE(NULLIF(j.error, ''), 'AnalysisFailed')
            FROM (
                SELECT DISTINCT ON (payload->>'message_id')
                    payload->>'message_id' AS message_id, kind, status, error
                FROM mice_work_items
                WHERE kind IN ('analysis.analyze', 'ingestion.parse')
                ORDER BY payload->>'message_id', created_at DESC, id DESC
            ) AS j
            WHERE m.id = j.message_id AND m.status = 'PENDING'
              AND j.kind = 'analysis.analyze' AND j.status IN ('DEAD', 'CANCELLED')
              AND NOT EXISTS (
                SELECT 1 FROM mice_work_items a WHERE a.payload->>'message_id' = m.id
                  AND a.status IN ('PENDING', 'RUNNING')
              )
        """)


class Migration(migrations.Migration):
    dependencies = [("pipeline", "0006_analysis_queue"), ("records", "0006_ocrtestdocument")]
    operations = [
        migrations.AddIndex(
            model_name="workitem",
            index=models.Index(KeyTextTransform("message_id", "payload"), models.F("created_at").desc(),
                               models.F("id").desc(), name="work_message_analysis_idx",
                               condition=models.Q(kind__in=["analysis.analyze", "ingestion.parse"])),
        ),
        migrations.RunPython(reconcile, migrations.RunPython.noop),
    ]
